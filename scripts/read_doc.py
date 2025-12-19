#!/usr/bin/env python3
"""
Read a Google Doc using the Google Docs API.

Usage:
    python read_doc.py <document_id_or_url>
"""

import sys
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes for reading Google Docs
SCOPES = [
    'https://www.googleapis.com/auth/documents.readonly',
]

SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'token_docs.json'


def extract_doc_id(url_or_id):
    """Extract document ID from a Google Docs URL or return as-is if already an ID."""
    # Match /d/<id>/ pattern in URLs
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    # Assume it's already an ID
    return url_or_id


def authenticate():
    """Handle Google OAuth 2.0 authentication."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: {CREDENTIALS_FILE} not found!")
                print("\nSet up OAuth credentials at https://console.cloud.google.com/")
                sys.exit(1)

            print("Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def extract_text(content):
    """Extract plain text from document content."""
    text = []

    for element in content:
        if 'paragraph' in element:
            for para_element in element['paragraph'].get('elements', []):
                if 'textRun' in para_element:
                    text.append(para_element['textRun'].get('content', ''))
        elif 'table' in element:
            for row in element['table'].get('tableRows', []):
                row_text = []
                for cell in row.get('tableCells', []):
                    cell_text = extract_text(cell.get('content', []))
                    row_text.append(cell_text.strip())
                text.append(' | '.join(row_text) + '\n')
        elif 'sectionBreak' in element:
            text.append('\n---\n')

    return ''.join(text)


def read_document(doc_id):
    """Read and display a Google Doc."""
    creds = authenticate()
    service = build('docs', 'v1', credentials=creds)

    try:
        doc = service.documents().get(documentId=doc_id).execute()

        title = doc.get('title', 'Untitled')
        print(f"# {title}\n")
        print("=" * 60)

        body = doc.get('body', {})
        content = body.get('content', [])

        text = extract_text(content)
        print(text)

    except HttpError as error:
        if error.resp.status == 404:
            print(f"Document not found: {doc_id}")
        elif error.resp.status == 403:
            print(f"Access denied. Make sure you have permission to view this document.")
        else:
            print(f"API Error: {error}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        # Default to the document from the user's request
        doc_url = "https://docs.google.com/document/d/1qimi7bTUy7k5NiN3mWqXqXSNCoHaZ8VjaX5HauL_9AY/edit?tab=t.0"
    else:
        doc_url = sys.argv[1]

    doc_id = extract_doc_id(doc_url)
    print(f"Reading document: {doc_id}\n")
    read_document(doc_id)


if __name__ == '__main__':
    main()
