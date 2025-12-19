#!/usr/bin/env python3
"""Test if we can update grades on UI-created assignments."""

import os
import sys
from pathlib import Path

os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Need write scope for grades
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
]

SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'token_grade_write.json'


def authenticate():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds


def main():
    creds = authenticate()
    service = build('classroom', 'v1', credentials=creds)

    # Find Period 4 Communications and Technology
    courses = service.courses().list(teacherId='me', courseStates=['ACTIVE']).execute().get('courses', [])
    target_course = next((c for c in courses if '4' in c['name'] and 'Communications' in c['name']), None)

    if not target_course:
        print("Course not found")
        return

    print(f"Course: {target_course['name']}")

    # Find the Grant Sanderson assignment
    coursework = service.courses().courseWork().list(courseId=target_course['id']).execute().get('courseWork', [])
    target_work = next((w for w in coursework if 'Grant Sanderson' in w.get('title', '')), None)

    if not target_work:
        print("Assignment not found")
        return

    print(f"Assignment: {target_work['title']}")
    print(f"  associatedWithDeveloper: {target_work.get('associatedWithDeveloper', 'NOT SET')}")

    # Get the TURNED_IN submission
    submissions = service.courses().courseWork().studentSubmissions().list(
        courseId=target_course['id'],
        courseWorkId=target_work['id']
    ).execute().get('studentSubmissions', [])

    turned_in = [s for s in submissions if s.get('state') == 'TURNED_IN']

    if not turned_in:
        print("\nNo turned-in submissions to test with")
        return

    sub = turned_in[0]
    print(f"\nTesting grade update on submission: {sub['id'][:20]}...")
    print(f"  Current assignedGrade: {sub.get('assignedGrade')}")
    print(f"  Current draftGrade: {sub.get('draftGrade')}")

    # Try to set a draft grade (8 points to match the Form score)
    try:
        result = service.courses().courseWork().studentSubmissions().patch(
            courseId=target_course['id'],
            courseWorkId=target_work['id'],
            id=sub['id'],
            updateMask='draftGrade,assignedGrade',
            body={
                'draftGrade': 8,
                'assignedGrade': 8
            }
        ).execute()

        print("\n*** SUCCESS! Grade updated! ***")
        print(f"  New assignedGrade: {result.get('assignedGrade')}")
        print(f"  New draftGrade: {result.get('draftGrade')}")

    except HttpError as e:
        print(f"\n*** FAILED: {e.resp.status} ***")
        print(f"  Error: {e.error_details}")
        print(f"\n  This means we CANNOT update grades on UI-created assignments.")


if __name__ == '__main__':
    main()
