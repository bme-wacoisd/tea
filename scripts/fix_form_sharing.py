#!/usr/bin/env python3
"""
Fix Google Form sharing settings so it shows proper title in Classroom.
"""

from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent
TOKEN_PATH = PROJECT_ROOT / 'token_assignment.json'

# Form ID from the URL
FORM_ID = "1FAIpQLSexex0qV_HrS9P2jeXLcCZo-hySoAigLHrLatjrZSjDjBZgYw"

# Try to extract the actual form ID (the part before /viewform)
# The URL is: https://docs.google.com/forms/d/e/1FAIpQLSexex0qV_HrS9P2jeXLcCZo-hySoAigLHrLatjrZSjDjBZgYw/viewform
# But we need the internal form ID which is different

creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
drive_service = build('drive', 'v3', credentials=creds)
forms_service = build('forms', 'v1', credentials=creds)

# First, let's list recent forms to find the one we created
print("Listing recent Google Forms...")

# Search for files that are Google Forms
results = drive_service.files().list(
    q="mimeType='application/vnd.google-apps.form'",
    spaces='drive',
    fields="files(id, name, createdTime)",
    orderBy="createdTime desc",
    pageSize=10
).execute()

files = results.get('files', [])

print(f"\nFound {len(files)} forms:")
for f in files:
    print(f"  {f['name']} - ID: {f['id']}")

# Find our form
target_form = None
for f in files:
    if 'Every Kid' in f['name'] or 'Champion' in f['name']:
        target_form = f
        break

if target_form:
    form_id = target_form['id']
    print(f"\nFound target form: {target_form['name']} (ID: {form_id})")

    # Get form details
    form = forms_service.forms().get(formId=form_id).execute()
    print(f"\nForm title: {form['info']['title']}")
    print(f"Responder URI: {form.get('responderUri', 'N/A')}")

    # Check current permissions
    print("\nCurrent permissions:")
    try:
        perms = drive_service.permissions().list(fileId=form_id, fields="permissions(id,type,role,emailAddress,domain)").execute()
        for p in perms.get('permissions', []):
            print(f"  {p.get('type')}: {p.get('emailAddress') or p.get('domain') or 'N/A'} ({p.get('role')})")
    except Exception as e:
        print(f"  Error getting permissions: {e}")

    # Share with wacoisd.org domain
    print("\nSharing with wacoisd.org domain...")
    try:
        drive_service.permissions().create(
            fileId=form_id,
            body={
                'type': 'domain',
                'role': 'reader',
                'domain': 'wacoisd.org'
            },
            fields='id'
        ).execute()
        print("  Done!")
    except Exception as e:
        print(f"  Error: {e}")

else:
    print("\nCould not find the target form!")
    print("Available forms:", [f['name'] for f in files])
