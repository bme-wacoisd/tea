#!/usr/bin/env python3
"""
lesson_plans_to_drive.py - Convert lesson plans to PDF and upload to Google Drive

Converts all lesson-plan.md files to nicely formatted PDFs and uploads them
to a "Lesson Plans" folder in Google Drive.

Usage:
    python lesson_plans_to_drive.py

Does NOT touch slides - only lesson plans.
"""

import pickle
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Paths
PROJECT_ROOT = Path(__file__).parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token.pickle'
LESSONS_DIR = PROJECT_ROOT / 'lessons'

# Professional color scheme
COLORS = {
    'primary': colors.HexColor('#1e3a5f'),      # Deep navy
    'secondary': colors.HexColor('#2d6a4f'),    # Forest green
    'accent': colors.HexColor('#d4a843'),       # Gold
    'text': colors.HexColor('#2d3748'),         # Dark gray
    'light_text': colors.HexColor('#4a5568'),   # Medium gray
    'table_header': colors.HexColor('#1e3a5f'), # Navy
    'table_alt': colors.HexColor('#f7fafc'),    # Light gray
    'divider': colors.HexColor('#e2e8f0'),      # Border gray
}


def get_credentials():
    """Get valid user credentials for Google Drive."""
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"ERROR: {CREDENTIALS_PATH} not found!")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def get_or_create_folder(drive_service, folder_name):
    """Get or create a folder in Google Drive root."""
    # Check if folder exists
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])

    if files:
        folder_id = files[0]['id']
        print(f"  Found existing folder: {folder_name}")
        return folder_id

    # Create folder
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = drive_service.files().create(body=file_metadata, fields='id').execute()
    folder_id = folder.get('id')
    print(f"  Created folder: {folder_name}")
    return folder_id


def upload_to_drive(drive_service, file_path, folder_id, display_name=None):
    """Upload a file to Google Drive folder."""
    file_name = display_name or file_path.name

    # Check if file already exists in folder
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
    existing = results.get('files', [])

    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(str(file_path), mimetype='application/pdf')

    if existing:
        # Update existing file
        file_id = existing[0]['id']
        drive_service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        print(f"  Updated: {file_name}")
        return file_id
    else:
        # Create new file
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"  Uploaded: {file_name}")
        return file.get('id')


def process_inline_formatting(text: str) -> str:
    """Convert markdown inline formatting to reportlab XML."""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Checkbox items
    text = text.replace('[ ]', '☐')
    text = text.replace('[x]', '☑')
    text = text.replace('[X]', '☑')
    return text


def create_styles():
    """Create custom paragraph styles for the PDF."""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=6,
        spaceBefore=0,
        textColor=COLORS['primary'],
        alignment=TA_CENTER
    ))

    # Subtitle/metadata style
    styles.add(ParagraphStyle(
        name='Metadata',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=3,
        textColor=COLORS['light_text'],
        alignment=TA_CENTER
    ))

    # Section headers (##)
    styles.add(ParagraphStyle(
        name='Section',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=8,
        textColor=COLORS['primary'],
        borderWidth=0,
        borderPadding=0,
        borderColor=COLORS['divider'],
    ))

    # Subsection headers (###)
    styles.add(ParagraphStyle(
        name='Subsection',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=COLORS['secondary'],
    ))

    # Body text
    styles.add(ParagraphStyle(
        name='Body',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14,
        textColor=COLORS['text']
    ))

    # Bullet points
    styles.add(ParagraphStyle(
        name='BulletItem',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        spaceAfter=4,
        leading=14,
        textColor=COLORS['text'],
        bulletIndent=0
    ))

    # Nested bullet
    styles.add(ParagraphStyle(
        name='BulletNested',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=30,
        spaceAfter=3,
        leading=13,
        textColor=COLORS['light_text']
    ))

    # Numbered items
    styles.add(ParagraphStyle(
        name='Numbered',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        spaceAfter=4,
        leading=14,
        textColor=COLORS['text']
    ))

    # Time markers (0:00 - 0:05)
    styles.add(ParagraphStyle(
        name='TimeMarker',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=8,
        spaceAfter=4,
        textColor=COLORS['accent'],
        fontName='Helvetica-Bold'
    ))

    return styles


def parse_table(lines, start_idx):
    """Parse a markdown table starting at start_idx. Returns (table_data, end_idx)."""
    table_data = []
    i = start_idx

    while i < len(lines):
        line = lines[i].strip()
        if not line or not '|' in line:
            break
        # Skip separator row (|---|---|)
        if re.match(r'^\|[\s\-:|]+\|$', line):
            i += 1
            continue
        # Parse cells
        cells = [c.strip() for c in line.split('|')]
        cells = [c for c in cells if c]  # Remove empty strings from edges
        if cells:
            table_data.append(cells)
        i += 1

    return table_data, i


def create_table_flowable(table_data, styles):
    """Create a styled table flowable from table data."""
    if not table_data:
        return None

    # Process cell content
    processed_data = []
    for row in table_data:
        processed_row = []
        for cell in row:
            # Wrap in Paragraph for text formatting
            text = process_inline_formatting(cell)
            processed_row.append(Paragraph(text, styles['Body']))
        processed_data.append(processed_row)

    # Calculate column widths
    num_cols = len(table_data[0]) if table_data else 1
    available_width = 7 * inch
    col_width = available_width / num_cols

    table = Table(processed_data, colWidths=[col_width] * num_cols)

    # Style the table
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['table_header']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]

    # Alternating row colors
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), COLORS['table_alt']))

    table.setStyle(TableStyle(style_commands))
    return table


def md_to_pdf(md_path: Path, pdf_path: Path):
    """Convert a lesson-plan.md to a nicely formatted PDF."""
    content = md_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )

    styles = create_styles()
    story = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped == '---':
            story.append(Spacer(1, 8))
            i += 1
            continue

        # Title (# )
        if stripped.startswith('# '):
            text = stripped[2:].strip()
            story.append(Paragraph(text, styles['DocTitle']))
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Section header (## )
        if stripped.startswith('## '):
            text = stripped[3:].strip()
            story.append(Spacer(1, 6))
            story.append(Paragraph(text, styles['Section']))
            i += 1
            continue

        # Subsection header (### )
        if stripped.startswith('### '):
            text = stripped[4:].strip()
            story.append(Paragraph(text, styles['Subsection']))
            i += 1
            continue

        # Table detection
        if '|' in stripped and not stripped.startswith('|---'):
            table_data, end_idx = parse_table(lines, i)
            if table_data:
                table = create_table_flowable(table_data, styles)
                if table:
                    story.append(Spacer(1, 6))
                    story.append(table)
                    story.append(Spacer(1, 6))
            i = end_idx
            continue

        # Time markers (**0:00 - 0:05**)
        time_match = re.match(r'^\*\*(\d+:\d+\s*-\s*\d+:\d+)\*\*$', stripped)
        if time_match:
            story.append(Paragraph(time_match.group(1), styles['TimeMarker']))
            i += 1
            continue

        # Nested bullet (starts with spaces + -)
        if re.match(r'^(\s{2,})-\s+', line):
            text = process_inline_formatting(re.sub(r'^\s+-\s+', '', line))
            story.append(Paragraph(f"◦ {text}", styles['BulletNested']))
            i += 1
            continue

        # Regular bullet point
        if stripped.startswith('- '):
            text = process_inline_formatting(stripped[2:])
            story.append(Paragraph(f"• {text}", styles['BulletItem']))
            i += 1
            continue

        # Numbered list
        num_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if num_match:
            num, text = num_match.groups()
            text = process_inline_formatting(text)
            story.append(Paragraph(f"{num}. {text}", styles['Numbered']))
            i += 1
            continue

        # Regular paragraph
        if stripped:
            text = process_inline_formatting(stripped)
            story.append(Paragraph(text, styles['Body']))

        i += 1

    doc.build(story)
    print(f"  Created PDF: {pdf_path.name}")
    return pdf_path


def main():
    print("=" * 60)
    print("LESSON PLAN PDF GENERATOR & DRIVE UPLOADER")
    print("=" * 60)

    # Find all lesson plans
    lesson_dirs = sorted(LESSONS_DIR.glob('*/'))
    lesson_plans = []

    print("\nFinding lesson plans...")
    for lesson_dir in lesson_dirs:
        lesson_plan = lesson_dir / 'lesson-plan.md'
        if lesson_plan.exists():
            lesson_plans.append(lesson_plan)
            print(f"  Found: {lesson_dir.name}/lesson-plan.md")

    if not lesson_plans:
        print("No lesson plans found!")
        return

    # Convert to PDFs
    print(f"\nConverting {len(lesson_plans)} lesson plans to PDF...")
    pdf_files = []

    for md_path in lesson_plans:
        pdf_path = md_path.parent / 'lesson-plan.pdf'
        pdf_files.append(md_to_pdf(md_path, pdf_path))

    # Upload to Google Drive
    print("\nConnecting to Google Drive...")
    creds = get_credentials()
    if not creds:
        print("ERROR: Could not authenticate with Google Drive")
        print("PDFs were created locally but not uploaded.")
        return

    drive_service = build('drive', 'v3', credentials=creds)

    # Get or create folder
    print("\nSetting up Drive folder...")
    folder_id = get_or_create_folder(drive_service, "Lesson Plans")

    # Upload PDFs with unique names
    print("\nUploading PDFs to Google Drive...")
    for pdf_path in pdf_files:
        # Create display name from lesson folder: "01-james-baldwin-civil-rights" -> "01 James Baldwin Civil Rights.pdf"
        lesson_name = pdf_path.parent.name
        parts = lesson_name.split('-')
        if parts[0].isdigit():
            num = parts[0]
            name_parts = [p.title() for p in parts[1:]]
            display_name = f"{num} {' '.join(name_parts)}.pdf"
        else:
            display_name = f"{lesson_name}.pdf"
        upload_to_drive(drive_service, pdf_path, folder_id, display_name)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"PDFs created: {len(pdf_files)}")
    print(f"Uploaded to: Google Drive > Lesson Plans")


if __name__ == '__main__':
    main()
