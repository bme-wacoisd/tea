#!/usr/bin/env python3
"""
doc.py - Create Google Docs from markdown

Usage:
    python doc.py <markdown_file>
    python doc.py lessons/01-james-baldwin-civil-rights/reading.md

Supports:
    - # Heading 1
    - ## Heading 2
    - **bold** and *italic*
    - Bullet points (- item)
    - Regular paragraphs
"""

import sys
import pickle
import re
from pathlib import Path
from typing import Optional

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive.file'
]

TOKEN_PATH = Path('token_docs.pickle')
CREDS_PATH = Path('credentials.json')


class DocError(Exception):
    """Document creation error."""
    pass


def verify_markdown(content: str) -> tuple[bool, list[str]]:
    """
    Verify markdown file has content.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    content = content.strip()
    if not content:
        errors.append("File is empty")
        return False, errors

    # Check for title
    if not re.search(r'^#\s+.+', content, re.MULTILINE):
        errors.append("Missing document title (# Title)")

    # Check reasonable length
    word_count = len(content.split())
    if word_count < 10:
        errors.append(f"Very short content ({word_count} words)")

    return len(errors) == 0, errors


def get_credentials() -> Optional[Credentials]:
    """Get or refresh Google API credentials."""
    if not GOOGLE_API_AVAILABLE:
        raise DocError("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")

    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_PATH.exists():
                raise DocError(f"Credentials file not found: {CREDS_PATH}\nDownload from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def md_to_doc_requests(content: str) -> list[dict]:
    """Convert markdown to Google Docs API requests."""
    requests = []
    lines = content.strip().split('\n')
    index = 1

    for line in lines:
        line = line.rstrip()

        # Skip horizontal rules
        if line == '---':
            continue

        # H1
        if line.startswith('# '):
            text = line[2:] + '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': index + len(text)},
                    'paragraphStyle': {'namedStyleType': 'HEADING_1'},
                    'fields': 'namedStyleType'
                }
            })
            index += len(text)

        # H2
        elif line.startswith('## '):
            text = line[3:] + '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': index + len(text)},
                    'paragraphStyle': {'namedStyleType': 'HEADING_2'},
                    'fields': 'namedStyleType'
                }
            })
            index += len(text)

        # H3
        elif line.startswith('### '):
            text = line[4:] + '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': index + len(text)},
                    'paragraphStyle': {'namedStyleType': 'HEADING_3'},
                    'fields': 'namedStyleType'
                }
            })
            index += len(text)

        # Bullet points
        elif line.startswith('- '):
            text = line[2:] + '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            requests.append({
                'createParagraphBullets': {
                    'range': {'startIndex': index, 'endIndex': index + len(text)},
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                }
            })
            index += len(text)

        # Regular text
        elif line:
            text = line + '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            index += len(text)

        # Empty line = paragraph break
        else:
            text = '\n'
            requests.append({
                'insertText': {'location': {'index': index}, 'text': text}
            })
            index += len(text)

    return requests


def create_google_doc(title: str, content: str) -> str:
    """
    Create Google Doc from markdown content.
    Returns edit URL.
    """
    print("Authenticating with Google...")
    creds = get_credentials()

    docs_service = build('docs', 'v1', credentials=creds)

    print(f"Creating document: {title}")
    doc = docs_service.documents().create(body={'title': title}).execute()
    doc_id = doc['documentId']

    print("Adding content...")
    requests = md_to_doc_requests(content)

    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    md_path = Path(sys.argv[1])

    # Verify file exists
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        sys.exit(1)

    content = md_path.read_text(encoding='utf-8')

    # Verify content
    print(f"Verifying: {md_path.name}")
    is_valid, errors = verify_markdown(content)

    if not is_valid:
        print("\nVERIFICATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("Verification passed.")

    # Extract title
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else md_path.stem

    # Create doc
    url = create_google_doc(title, content)

    print(f"\n{'='*60}")
    print("DOCUMENT CREATED SUCCESSFULLY!")
    print('='*60)
    print(f"\n{url}\n")


if __name__ == '__main__':
    main()
