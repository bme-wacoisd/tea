#!/usr/bin/env python3
"""
enable_form_email_collection.py - Enable email collection on existing quiz forms

Updates all quiz forms to collect respondent emails so we can identify who
completed quizzes.

Usage:
    python scripts/enable_form_email_collection.py --dry-run   # Preview
    python scripts/enable_form_email_collection.py             # Apply changes
"""

import argparse
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/forms.body',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_assignment.json'

TARGET_COURSES = [
    '1 Instructional Practices & Practicum',
    '2 Communications and Technology',
    '3 Instructional Practices & Practicum',
    '4 Communications and Technology',
    '5 Instructional Practices & Practicum',
    '6 Communications and Technology',
    '7 Instructional Practices & Practicum',
    '8 Communications and Technology',
]


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"ERROR: {CREDENTIALS_PATH} not found!")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds


def main():
    parser = argparse.ArgumentParser(description='Enable email collection on quiz forms')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    print("=" * 60)
    print("ENABLE EMAIL COLLECTION ON QUIZ FORMS")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    creds = get_credentials()
    classroom = build('classroom', 'v1', credentials=creds)
    forms = build('forms', 'v1', credentials=creds)

    # Get courses
    courses_result = classroom.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = {c['name']: c for c in courses_result.get('courses', []) if c['name'] in TARGET_COURSES}

    print(f"Found {len(courses)} courses")

    # Find all forms
    form_ids = {}  # form_id -> assignment_title

    for course_name, course in sorted(courses.items()):
        try:
            coursework_result = classroom.courses().courseWork().list(courseId=course['id']).execute()
            for cw in coursework_result.get('courseWork', []):
                for material in cw.get('materials', []):
                    if 'form' in material:
                        form_url = material['form'].get('formUrl', '')
                        if '/d/' in form_url:
                            form_id = form_url.split('/d/')[1].split('/')[0]
                            if form_id not in form_ids:
                                form_ids[form_id] = cw['title']
        except HttpError as e:
            print(f"Error processing {course_name}: {e}")

    print(f"\nFound {len(form_ids)} unique forms\n")

    # Update each form
    updated = 0
    already_enabled = 0
    errors = 0

    for form_id, title in sorted(form_ids.items(), key=lambda x: x[1]):
        try:
            # Get current settings
            form_info = forms.forms().get(formId=form_id).execute()
            settings = form_info.get('settings', {})
            email_collection = settings.get('emailCollectionType', 'DO_NOT_COLLECT')

            if email_collection == 'VERIFIED':
                print(f"  [OK] {title} - already collecting emails")
                already_enabled += 1
                continue

            print(f"  [UPDATE] {title} - {email_collection} -> VERIFIED")

            if not args.dry_run:
                forms.forms().batchUpdate(
                    formId=form_id,
                    body={
                        'requests': [
                            {
                                'updateSettings': {
                                    'settings': {
                                        'emailCollectionType': 'VERIFIED'
                                    },
                                    'updateMask': 'emailCollectionType'
                                }
                            }
                        ]
                    }
                ).execute()
            updated += 1

        except HttpError as e:
            print(f"  [ERROR] {title}: {e}")
            errors += 1

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Already collecting emails: {already_enabled}")
    print(f"  Updated: {updated}")
    print(f"  Errors: {errors}")

    if args.dry_run and updated > 0:
        print(f"\nRun without --dry-run to apply {updated} updates")


if __name__ == '__main__':
    main()
