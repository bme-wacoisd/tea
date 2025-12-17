#!/usr/bin/env python3
"""
Download all materials from growtexasteachers.org course pages.
Responsible crawler with rate limiting to avoid overloading the server.
"""

import argparse
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from collections import deque

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Missing required package: {e}")
    print("\nPlease install required packages:")
    print("pip install --user requests beautifulsoup4")
    sys.exit(1)


# File extensions we want to download
DOWNLOADABLE_EXTENSIONS = {
    # Documents
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.txt', '.rtf', '.odt', '.ods', '.odp',
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp',
    # Media
    '.mp3', '.mp4', '.wav', '.webm', '.mov',
    # Archives
    '.zip', '.rar', '.7z',
}


class MaterialDownloader:
    """Downloads course materials from growtexasteachers.org responsibly."""

    def __init__(self, output_dir: str, delay: float = 1.5, max_pages: int = 100):
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded files
            delay: Seconds to wait between requests (be polite!)
            max_pages: Maximum number of pages to crawl (safety limit)
        """
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.max_pages = max_pages

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        # Track what we've visited and downloaded
        self.visited_pages = set()
        self.downloaded_files = set()
        self.failed_downloads = []

        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'files_downloaded': 0,
            'files_skipped': 0,
            'bytes_downloaded': 0,
            'errors': 0,
        }

    def _polite_wait(self):
        """Wait between requests to be respectful of the server."""
        time.sleep(self.delay)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        # Remove trailing slashes and fragments
        path = parsed.path.rstrip('/')
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _is_same_domain(self, url: str, base_url: str) -> bool:
        """Check if URL is on the same domain as base."""
        return urlparse(url).netloc == urlparse(base_url).netloc

    def _get_file_extension(self, url: str) -> str:
        """Extract file extension from URL."""
        path = urlparse(url).path
        # Handle URLs with query parameters
        path = path.split('?')[0]
        ext = os.path.splitext(path)[1].lower()
        return ext

    def _is_downloadable(self, url: str) -> bool:
        """Check if URL points to a downloadable file."""
        ext = self._get_file_extension(url)
        return ext in DOWNLOADABLE_EXTENSIONS

    def _get_safe_filename(self, url: str) -> str:
        """Generate a safe filename from URL."""
        path = urlparse(url).path
        path = path.split('?')[0]  # Remove query params
        filename = unquote(os.path.basename(path))

        # Clean up filename
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')

        if not filename:
            # Generate filename from URL hash
            filename = hashlib.md5(url.encode()).hexdigest()[:12]
            ext = self._get_file_extension(url)
            if ext:
                filename += ext

        return filename

    def _fetch_page(self, url: str) -> BeautifulSoup | None:
        """Fetch and parse a page."""
        try:
            print(f"  Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            self.stats['errors'] += 1
            return None

    def _download_file(self, url: str, subdir: str = "") -> bool:
        """Download a file to the output directory."""
        filename = self._get_safe_filename(url)

        # Create subdirectory if specified
        if subdir:
            file_dir = self.output_dir / subdir
        else:
            file_dir = self.output_dir

        file_dir.mkdir(parents=True, exist_ok=True)
        filepath = file_dir / filename

        # Skip if already downloaded
        if filepath.exists():
            print(f"  Skipping (exists): {filename}")
            self.stats['files_skipped'] += 1
            return True

        try:
            print(f"  Downloading: {filename}")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()

            # Get file size if available
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                print(f"    Size: {size_mb:.2f} MB")

            # Write file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = filepath.stat().st_size
            self.stats['files_downloaded'] += 1
            self.stats['bytes_downloaded'] += file_size
            self.downloaded_files.add(url)

            print(f"    Saved: {filepath}")
            return True

        except requests.RequestException as e:
            print(f"  Error downloading {url}: {e}")
            self.failed_downloads.append({'url': url, 'error': str(e)})
            self.stats['errors'] += 1
            return False

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> tuple[list[str], list[str]]:
        """Extract page links and file links from a page."""
        page_links = []
        file_links = []

        for link in soup.find_all('a', href=True):
            href = link['href']

            # Skip empty, javascript, and anchor links
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            # Make absolute URL
            full_url = urljoin(base_url, href)

            # Check if it's a downloadable file
            if self._is_downloadable(full_url):
                if full_url not in self.downloaded_files:
                    file_links.append(full_url)
            # Check if it's a page on the same domain
            elif self._is_same_domain(full_url, base_url):
                normalized = self._normalize_url(full_url)
                if normalized not in self.visited_pages:
                    # Only follow links that seem to be course content
                    path = urlparse(full_url).path.lower()
                    if any(x in path for x in ['practices', 'practicum', 'lesson', 'module', 'unit', 'chapter']):
                        page_links.append(full_url)

        return list(set(page_links)), list(set(file_links))

    def crawl(self, start_url: str):
        """
        Crawl starting from a URL and download all materials.

        Uses breadth-first search to crawl pages and download files.
        """
        print(f"\n{'='*60}")
        print(f"Material Downloader")
        print(f"{'='*60}")
        print(f"Start URL: {start_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"Request delay: {self.delay}s")
        print(f"{'='*60}\n")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Queue of pages to visit
        to_visit = deque([start_url])

        while to_visit and self.stats['pages_crawled'] < self.max_pages:
            current_url = to_visit.popleft()
            normalized = self._normalize_url(current_url)

            if normalized in self.visited_pages:
                continue

            self.visited_pages.add(normalized)
            self.stats['pages_crawled'] += 1

            print(f"\n[Page {self.stats['pages_crawled']}] {current_url}")

            # Fetch the page
            soup = self._fetch_page(current_url)
            if not soup:
                continue

            self._polite_wait()

            # Extract links
            page_links, file_links = self._extract_links(soup, current_url)

            print(f"  Found: {len(page_links)} pages, {len(file_links)} files")

            # Download files
            for file_url in file_links:
                if file_url not in self.downloaded_files:
                    self._download_file(file_url)
                    self._polite_wait()

            # Add new pages to queue
            for page_url in page_links:
                if self._normalize_url(page_url) not in self.visited_pages:
                    to_visit.append(page_url)

        self._print_summary()

    def download_from_page(self, url: str):
        """
        Download all materials linked from a single page (no crawling).
        More conservative approach - only downloads from the specified page.
        """
        print(f"\n{'='*60}")
        print(f"Material Downloader (Single Page Mode)")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Output directory: {self.output_dir}")
        print(f"Request delay: {self.delay}s")
        print(f"{'='*60}\n")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Fetch the page
        soup = self._fetch_page(url)
        if not soup:
            print("Failed to fetch page. Exiting.")
            return

        self.stats['pages_crawled'] = 1
        self._polite_wait()

        # Find all downloadable links
        file_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue

            full_url = urljoin(url, href)
            if self._is_downloadable(full_url):
                file_links.append({
                    'url': full_url,
                    'text': link.get_text(strip=True)
                })

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in file_links:
            if f['url'] not in seen:
                seen.add(f['url'])
                unique_files.append(f)

        print(f"Found {len(unique_files)} downloadable files:\n")
        for i, f in enumerate(unique_files, 1):
            ext = self._get_file_extension(f['url'])
            print(f"  {i}. [{ext.upper()[1:] if ext else 'FILE'}] {f['text'][:60]}")

        print(f"\n{'='*60}")
        print("Starting downloads...")
        print(f"{'='*60}\n")

        # Download each file
        for i, f in enumerate(unique_files, 1):
            print(f"[{i}/{len(unique_files)}]", end=" ")
            self._download_file(f['url'])
            self._polite_wait()

        self._print_summary()

    def _print_summary(self):
        """Print download summary."""
        print(f"\n{'='*60}")
        print("Download Summary")
        print(f"{'='*60}")
        print(f"Pages crawled:     {self.stats['pages_crawled']}")
        print(f"Files downloaded:  {self.stats['files_downloaded']}")
        print(f"Files skipped:     {self.stats['files_skipped']}")
        print(f"Total downloaded:  {self.stats['bytes_downloaded'] / (1024*1024):.2f} MB")
        print(f"Errors:            {self.stats['errors']}")

        if self.failed_downloads:
            print(f"\nFailed downloads:")
            for item in self.failed_downloads:
                print(f"  - {item['url']}")
                print(f"    Error: {item['error']}")

        print(f"{'='*60}")
        print(f"Files saved to: {self.output_dir.absolute()}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Download materials from growtexasteachers.org responsibly',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Download from practices page (single page mode - recommended)
  python download_materials.py --url https://www.growtexasteachers.org/practices

  # Crawl and download (follows links)
  python download_materials.py --url https://www.growtexasteachers.org/practices --crawl

  # Custom output directory and delay
  python download_materials.py --url URL --output ./my_materials --delay 2.0

Rate Limiting:
  This script is designed to be respectful of the server:
  - Default 1.5 second delay between requests
  - Single-threaded (no parallel downloads)
  - User-Agent identifies as a normal browser
  - Stops after 100 pages max (configurable)
        '''
    )

    parser.add_argument(
        '--url', '-u',
        default='https://www.growtexasteachers.org/practices',
        help='URL to download from (default: practices page)'
    )

    parser.add_argument(
        '--output', '-o',
        default='./teks/practices',
        help='Output directory (default: ./teks/practices)'
    )

    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=1.5,
        help='Delay between requests in seconds (default: 1.5)'
    )

    parser.add_argument(
        '--crawl', '-c',
        action='store_true',
        help='Crawl linked pages (default: single page only)'
    )

    parser.add_argument(
        '--max-pages', '-m',
        type=int,
        default=100,
        help='Maximum pages to crawl (default: 100)'
    )

    args = parser.parse_args()

    downloader = MaterialDownloader(
        output_dir=args.output,
        delay=args.delay,
        max_pages=args.max_pages
    )

    if args.crawl:
        downloader.crawl(args.url)
    else:
        downloader.download_from_page(args.url)


if __name__ == "__main__":
    main()
