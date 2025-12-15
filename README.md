# Grow Texas Teachers - Course Materials Scraper

A Python tool to download and convert PowerPoint presentations from the Grow Texas Teachers website into Markdown and PDF formats.

## Overview

This tool scrapes course materials from:
- **Instructional Practices**: https://www.growtexasteachers.org/practices
- **Practicum**: https://www.growtexasteachers.org/practicum

It downloads all PowerPoint presentations and converts them to searchable Markdown and PDF formats, with options for individual files and combined documents.

## Requirements

Python 3.8+ with the following packages:

```bash
pip install --user requests beautifulsoup4 python-pptx markdown reportlab
```

## Usage

### Basic Usage

Download and convert all course materials:

```bash
python scrape_and_convert.py
```

### Options

```bash
python scrape_and_convert.py [OPTIONS]

Options:
  --output, -o PATH    Output directory (default: ./output)
  --delay, -d SECONDS  Delay between requests (default: 0.5)
  --url URL NAME       Process specific URL with given name (repeatable)
```

### Examples

```bash
# Process everything with defaults
python scrape_and_convert.py

# Custom output directory
python scrape_and_convert.py --output ./my_output

# Process only one course
python scrape_and_convert.py --url https://www.growtexasteachers.org/practices practices

# Slower requests (be nice to the server)
python scrape_and_convert.py --delay 2.0
```

## Output Structure

```
output/
├── practices/
│   ├── pptx/                    # Original PowerPoint files
│   ├── markdown/                # Individual Markdown files
│   ├── pdf/                     # Individual PDF files
│   └── practices_combined.md    # All practices lessons combined
├── practicum/
│   ├── pptx/
│   ├── markdown/
│   ├── pdf/
│   └── practicum_combined.md
├── all_classes_combined.md      # Everything combined
└── all_classes_combined.pdf

all_courses_combined.pdf         # Master PDF in project root
```

## Features

- Downloads PowerPoint files with polite server delays
- Extracts all text content including tables and speaker notes
- Converts to clean, readable Markdown format
- Generates styled PDFs with proper formatting
- Creates combined documents for easy reference
- Skips already-downloaded files on re-runs

## License

See [LICENSE](LICENSE) file.
