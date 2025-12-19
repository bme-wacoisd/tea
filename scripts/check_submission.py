#!/usr/bin/env python3
"""Check submission details for a specific assignment."""

import os
import sys
from pathlib import Path

os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
]

SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'token_quiz_grades.json'


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

    target_course = None
    for c in courses:
        if '4' in c['name'] and 'Communications' in c['name']:
            target_course = c
            break

    if not target_course:
        print("Course not found")
        return

    print(f"Course: {target_course['name']} (ID: {target_course['id']})")

    # Find the Grant Sanderson assignment
    coursework = service.courses().courseWork().list(courseId=target_course['id']).execute().get('courseWork', [])

    target_work = None
    for w in coursework:
        if 'Grant Sanderson' in w.get('title', '') or 'math' in w.get('title', '').lower():
            target_work = w
            break

    if not target_work:
        print("Assignment not found")
        return

    print(f"\nAssignment: {target_work['title']}")
    print(f"  ID: {target_work['id']}")
    print(f"  workType: {target_work.get('workType', 'N/A')}")
    print(f"  maxPoints: {target_work.get('maxPoints', 'N/A')}")
    print(f"  state: {target_work.get('state', 'N/A')}")

    # Check materials/attachments
    materials = target_work.get('materials', [])
    print(f"  materials: {len(materials)}")
    for i, mat in enumerate(materials):
        print(f"    [{i}] {list(mat.keys())}")
        if 'form' in mat:
            print(f"        Form: {mat['form'].get('title', 'N/A')}")
            print(f"        formUrl: {mat['form'].get('formUrl', 'N/A')}")
        if 'driveFile' in mat:
            print(f"        DriveFile: {mat['driveFile'].get('driveFile', {}).get('title', 'N/A')}")

    # Get submissions
    print("\nSubmissions:")
    submissions = service.courses().courseWork().studentSubmissions().list(
        courseId=target_course['id'],
        courseWorkId=target_work['id']
    ).execute().get('studentSubmissions', [])

    for sub in submissions:
        state = sub.get('state', 'N/A')
        assigned = sub.get('assignedGrade')
        draft = sub.get('draftGrade')
        late = sub.get('late', False)
        user_id = sub.get('userId', 'N/A')

        # Get submission attachments
        attachments = sub.get('assignmentSubmission', {}).get('attachments', [])

        print(f"\n  User: {user_id[:8]}...")
        print(f"    state: {state}")
        print(f"    assignedGrade: {assigned}")
        print(f"    draftGrade: {draft}")
        print(f"    late: {late}")
        print(f"    attachments: {len(attachments)}")

        # Show all fields for debugging
        other_fields = {k: v for k, v in sub.items()
                       if k not in ['userId', 'state', 'assignedGrade', 'draftGrade', 'late',
                                   'assignmentSubmission', 'courseId', 'courseWorkId', 'id',
                                   'creationTime', 'updateTime', 'alternateLink', 'courseWorkType']}
        if other_fields:
            print(f"    other: {other_fields}")


if __name__ == '__main__':
    main()
