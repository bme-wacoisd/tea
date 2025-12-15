# Grow Texas Teachers - Educator Preparation Materials

Resources and lesson materials for the Grow Your Own educator preparation program.

## Overview

This repository contains:
1. **Lesson materials** for future educators (9th-12th grade students)
2. **Course content scraper** to download official curriculum resources

### Course Resources

Official curriculum materials scraped from:
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

## Lessons

Custom lesson materials are in the `lessons/` folder:

```
lessons/
├── templates/              # Lesson templates
│   ├── slides-template.md
│   ├── reading-template.md
│   ├── worksheet-template.md
│   ├── quiz-template.md
│   └── lesson-plan-template.md
└── XX-lesson-name/         # Individual lessons
    ├── slides.md           # Presentation slides
    ├── reading.md          # Read-aloud text (3-5 paragraphs)
    ├── worksheet.md        # Group discussion prompts
    ├── quiz.md             # Quiz for Automagical Forms
    └── lesson-plan.md      # Formal lesson plan
```

### Lesson Format

Each lesson is designed for 30-40 minutes and includes:
- **Slides**: "How to teach X" presentation for instructor
- **Reading**: Text for instructor to read aloud
- **Worksheet**: Discussion prompts (no blanks - verbal discussion, paper summaries)
- **Quiz**: Google Classroom quiz via [Automagical Forms](https://automagicalapps.com/forms)
- **Lesson Plan**: Documentation for administration

See [CLAUDE.md](CLAUDE.md) for detailed lesson creation guidelines.

## Scraper Features

- Downloads PowerPoint files with polite server delays
- Extracts all text content including tables and speaker notes
- Converts to clean, readable Markdown format
- Generates styled PDFs with proper formatting
- Creates combined documents for easy reference
- Skips already-downloaded files on re-runs

## License

See [LICENSE](LICENSE) file.
