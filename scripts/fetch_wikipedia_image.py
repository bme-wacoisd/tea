#!/usr/bin/env python3
"""
fetch_wikipedia_image.py - Fetch portrait images from Wikipedia/Wikimedia Commons

Usage:
    python scripts/fetch_wikipedia_image.py "Rita Pierson" --output lessons/08-every-kid-needs-champion/assets/

Features:
    - Searches Wikipedia for the person
    - Downloads their main portrait image
    - Resizes if needed
    - Saves to specified output directory
"""

import argparse
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path


def fetch_wikipedia_image(person_name: str, output_dir: Path, filename: str = None) -> Path | None:
    """
    Fetch the main image from a person's Wikipedia page.

    Args:
        person_name: Name to search for (e.g., "Rita Pierson")
        output_dir: Directory to save the image
        filename: Optional filename (defaults to person_name.jpg)

    Returns:
        Path to downloaded image, or None if not found
    """
    # Normalize the search term
    search_term = person_name.strip().replace(' ', '_')

    # Wikipedia API endpoint for getting page images
    api_url = "https://en.wikipedia.org/w/api.php"

    # First, search for the page
    search_params = {
        'action': 'query',
        'titles': search_term,
        'prop': 'pageimages',
        'format': 'json',
        'pithumbsize': 500,  # Request 500px thumbnail
        'redirects': '1'  # Follow redirects
    }

    query_string = urllib.parse.urlencode(search_params)
    request_url = f"{api_url}?{query_string}"

    print(f"  Searching Wikipedia for: {person_name}")

    try:
        req = urllib.request.Request(
            request_url,
            headers={'User-Agent': 'EducatorLessonBot/1.0 (brian.edwards@wacoisd.org)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            import json
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"  ERROR: Wikipedia API failed: {e}")
        return None

    # Parse the response
    pages = data.get('query', {}).get('pages', {})

    for page_id, page_data in pages.items():
        if page_id == '-1':
            print(f"  No Wikipedia page found for: {person_name}")
            return None

        thumbnail = page_data.get('thumbnail', {})
        image_url = thumbnail.get('source')

        if not image_url:
            print(f"  No image found for: {person_name}")
            return None

        # Download the image
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            # Create filename from person name
            safe_name = re.sub(r'[^\w\s-]', '', person_name.lower())
            safe_name = re.sub(r'[\s]+', '-', safe_name)
            filename = f"{safe_name}.jpg"

        output_path = output_dir / filename

        print(f"  Downloading image...")
        try:
            req = urllib.request.Request(
                image_url,
                headers={'User-Agent': 'EducatorLessonBot/1.0 (brian.edwards@wacoisd.org)'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(output_path, 'wb') as f:
                    f.write(response.read())
        except Exception as e:
            print(f"  ERROR: Failed to download image: {e}")
            return None

        print(f"  Saved to: {output_path}")
        return output_path

    return None


def fetch_wikimedia_commons_image(search_term: str, output_dir: Path, filename: str = None) -> Path | None:
    """
    Search Wikimedia Commons for an image.

    Useful when Wikipedia doesn't have a good image or for non-people subjects.
    """
    api_url = "https://commons.wikimedia.org/w/api.php"

    search_params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': f'filetype:bitmap {search_term}',
        'gsrlimit': '1',
        'prop': 'imageinfo',
        'iiprop': 'url',
        'iiurlwidth': 500,
        'format': 'json'
    }

    query_string = urllib.parse.urlencode(search_params)
    request_url = f"{api_url}?{query_string}"

    print(f"  Searching Wikimedia Commons for: {search_term}")

    try:
        req = urllib.request.Request(
            request_url,
            headers={'User-Agent': 'EducatorLessonBot/1.0 (brian.edwards@wacoisd.org)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            import json
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"  ERROR: Wikimedia API failed: {e}")
        return None

    pages = data.get('query', {}).get('pages', {})

    for page_id, page_data in pages.items():
        if page_id.startswith('-'):
            continue

        imageinfo = page_data.get('imageinfo', [{}])[0]
        image_url = imageinfo.get('thumburl') or imageinfo.get('url')

        if not image_url:
            continue

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            safe_name = re.sub(r'[^\w\s-]', '', search_term.lower())
            safe_name = re.sub(r'[\s]+', '-', safe_name)
            filename = f"{safe_name}.jpg"

        output_path = output_dir / filename

        print(f"  Downloading from Commons...")
        try:
            req = urllib.request.Request(
                image_url,
                headers={'User-Agent': 'EducatorLessonBot/1.0 (brian.edwards@wacoisd.org)'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(output_path, 'wb') as f:
                    f.write(response.read())
        except Exception as e:
            print(f"  ERROR: Failed to download: {e}")
            return None

        print(f"  Saved to: {output_path}")
        return output_path

    print(f"  No Commons image found for: {search_term}")
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Fetch portrait images from Wikipedia/Wikimedia Commons'
    )
    parser.add_argument('name', help='Person or subject to search for')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--filename', '-f', help='Output filename (default: derived from name)')
    parser.add_argument('--commons', action='store_true', help='Search Wikimedia Commons instead of Wikipedia')

    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.commons:
        result = fetch_wikimedia_commons_image(args.name, output_dir, args.filename)
    else:
        result = fetch_wikipedia_image(args.name, output_dir, args.filename)

        # Fall back to Commons if Wikipedia fails
        if result is None:
            print("  Trying Wikimedia Commons as fallback...")
            result = fetch_wikimedia_commons_image(args.name, output_dir, args.filename)

    if result:
        print(f"\nSuccess: {result}")
        sys.exit(0)
    else:
        print("\nFailed to find image")
        sys.exit(1)


if __name__ == '__main__':
    main()
