#!/usr/bin/env python3
"""
Process large PDF files by extracting text and splitting into manageable chunks.

Usage:
    python scripts/process_large_pdf.py <pdf_path> [--output-dir DIR] [--pages-per-chunk N]

Examples:
    python scripts/process_large_pdf.py teks/knight-lesson-plans.pdf
    python scripts/process_large_pdf.py teks/knight-lesson-plans.pdf --output-dir teks/knight-chunks --pages-per-chunk 20

Notes:
    - Uses pdftotext (from poppler-utils) when available for better text extraction
    - Falls back to PyPDF2 if pdftotext is not installed
    - pdftotext handles scanned/image-based PDFs much better
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# Check for pdftotext
HAS_PDFTOTEXT = shutil.which('pdftotext') is not None


def get_pdf_metadata(pdf_path: str) -> dict:
    """Extract metadata from PDF without reading full content."""
    if not HAS_PYPDF2:
        # Minimal metadata without PyPDF2
        return {
            'num_pages': 0,
            'title': 'Unknown',
            'author': 'Unknown',
            'subject': '',
            'creator': '',
        }
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        metadata = reader.metadata or {}
        return {
            'num_pages': len(reader.pages),
            'title': metadata.get('/Title', 'Unknown'),
            'author': metadata.get('/Author', 'Unknown'),
            'subject': metadata.get('/Subject', ''),
            'creator': metadata.get('/Creator', ''),
        }


def extract_text_pdftotext(pdf_path: str, first_page: int = None, last_page: int = None) -> str:
    """Extract text using pdftotext (poppler-utils). Much better for most PDFs."""
    cmd = ['pdftotext']
    if first_page is not None:
        cmd.extend(['-f', str(first_page)])
    if last_page is not None:
        cmd.extend(['-l', str(last_page)])
    cmd.extend([pdf_path, '-'])  # Output to stdout

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def extract_full_text(pdf_path: str) -> str:
    """Extract all text from PDF using best available method."""
    if HAS_PDFTOTEXT:
        return extract_text_pdftotext(pdf_path)
    elif HAS_PYPDF2:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            texts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                texts.append(f"--- Page {i + 1} ---\n{page_text}")
            return "\n\n".join(texts)
    else:
        return "Error: No PDF extraction tool available. Install pdftotext or PyPDF2."


def extract_page_text(pdf_path: str, page_num: int) -> str:
    """Extract text from a single page."""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        if page_num < len(reader.pages):
            return reader.pages[page_num].extract_text() or ""
    return ""


def extract_text_range(pdf_path: str, start_page: int, end_page: int) -> str:
    """Extract text from a range of pages."""
    texts = []
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for i in range(start_page, min(end_page, len(reader.pages))):
            page_text = reader.pages[i].extract_text() or ""
            texts.append(f"--- Page {i + 1} ---\n{page_text}")
    return "\n\n".join(texts)


def extract_toc_or_outline(pdf_path: str) -> list:
    """Try to extract table of contents/outline if available."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            outlines = reader.outline
            if outlines:
                return _flatten_outline(outlines)
    except Exception:
        pass
    return []


def _flatten_outline(outlines, level=0) -> list:
    """Flatten nested outline structure."""
    result = []
    for item in outlines:
        if isinstance(item, list):
            result.extend(_flatten_outline(item, level + 1))
        else:
            try:
                title = item.title if hasattr(item, 'title') else str(item)
                result.append(('  ' * level) + title)
            except Exception:
                pass
    return result


def split_pdf_to_chunks(pdf_path: str, output_dir: str, pages_per_chunk: int = 10):
    """Split PDF text into multiple markdown files."""
    os.makedirs(output_dir, exist_ok=True)

    metadata = get_pdf_metadata(pdf_path)
    num_pages = metadata['num_pages']

    # Write metadata file
    with open(os.path.join(output_dir, '00-metadata.md'), 'w', encoding='utf-8') as f:
        f.write(f"# PDF Metadata: {os.path.basename(pdf_path)}\n\n")
        f.write(f"- **Total Pages**: {num_pages}\n")
        f.write(f"- **Title**: {metadata['title']}\n")
        f.write(f"- **Author**: {metadata['author']}\n")
        f.write(f"- **Subject**: {metadata['subject']}\n")
        f.write(f"- **Creator**: {metadata['creator']}\n\n")

        # Try to extract TOC
        toc = extract_toc_or_outline(pdf_path)
        if toc:
            f.write("## Table of Contents\n\n")
            for item in toc:
                f.write(f"- {item}\n")

    # Split into chunks
    chunk_files = []
    chunk_num = 1

    for start in range(0, num_pages, pages_per_chunk):
        end = min(start + pages_per_chunk, num_pages)
        chunk_text = extract_text_range(pdf_path, start, end)

        chunk_filename = f"{chunk_num:02d}-pages-{start+1}-to-{end}.md"
        chunk_path = os.path.join(output_dir, chunk_filename)

        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(f"# Pages {start + 1} to {end}\n\n")
            f.write(chunk_text)

        chunk_files.append(chunk_filename)
        print(f"Created: {chunk_filename}")
        chunk_num += 1

    # Write index file
    with open(os.path.join(output_dir, 'index.md'), 'w', encoding='utf-8') as f:
        f.write(f"# Index: {os.path.basename(pdf_path)}\n\n")
        f.write(f"Total pages: {num_pages}\n\n")
        f.write("## Chunks\n\n")
        for cf in chunk_files:
            f.write(f"- [{cf}]({cf})\n")

    return chunk_files


def extract_first_n_pages(pdf_path: str, n: int = 5) -> str:
    """Quick extraction of first N pages for preview."""
    return extract_text_range(pdf_path, 0, n)


def main():
    parser = argparse.ArgumentParser(description='Process large PDF files')
    parser.add_argument('pdf_path', help='Path to the PDF file')
    parser.add_argument('--output-dir', '-o', help='Output directory for chunks')
    parser.add_argument('--pages-per-chunk', '-p', type=int, default=10,
                        help='Number of pages per chunk (default: 10)')
    parser.add_argument('--metadata-only', '-m', action='store_true',
                        help='Only show metadata, do not extract text')
    parser.add_argument('--preview', '-v', type=int, metavar='N',
                        help='Preview first N pages')
    parser.add_argument('--extract', '-e', action='store_true',
                        help='Extract full text to single markdown file (recommended)')

    args = parser.parse_args()

    # Show available tools
    print(f"\n=== Available Tools ===")
    print(f"pdftotext: {'Yes' if HAS_PDFTOTEXT else 'No (install poppler-utils)'}")
    print(f"PyPDF2: {'Yes' if HAS_PYPDF2 else 'No'}")

    if not os.path.exists(args.pdf_path):
        print(f"Error: File not found: {args.pdf_path}")
        sys.exit(1)

    # Show metadata
    print(f"\n=== PDF Metadata ===")
    metadata = get_pdf_metadata(args.pdf_path)
    print(f"File: {args.pdf_path}")
    print(f"Size: {os.path.getsize(args.pdf_path) / 1024 / 1024:.1f} MB")
    print(f"Pages: {metadata['num_pages']}")
    print(f"Title: {metadata['title']}")
    print(f"Author: {metadata['author']}")

    if args.metadata_only:
        return

    # Simple full extraction mode (recommended)
    if args.extract:
        print(f"\n=== Extracting Full Text ===")
        text = extract_full_text(args.pdf_path)

        # Determine output path
        pdf_name = Path(args.pdf_path).stem
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            output_path = os.path.join(args.output_dir, f"{pdf_name}.md")
        else:
            output_path = str(Path(args.pdf_path).with_suffix('.md'))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {pdf_name}\n\n")
            f.write(text)

        print(f"Extracted to: {output_path}")
        print(f"Size: {os.path.getsize(output_path) / 1024:.1f} KB")
        return

    if args.preview:
        print(f"\n=== Preview (First {args.preview} pages) ===\n")
        print(extract_first_n_pages(args.pdf_path, args.preview))
        return

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        pdf_name = Path(args.pdf_path).stem
        output_dir = os.path.join(os.path.dirname(args.pdf_path), f"{pdf_name}-extracted")

    print(f"\n=== Splitting PDF ===")
    print(f"Output directory: {output_dir}")
    print(f"Pages per chunk: {args.pages_per_chunk}")

    chunks = split_pdf_to_chunks(args.pdf_path, output_dir, args.pages_per_chunk)
    print(f"\nDone! Created {len(chunks)} chunk files in {output_dir}")


if __name__ == '__main__':
    main()
