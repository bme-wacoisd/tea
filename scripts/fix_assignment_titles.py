#!/usr/bin/env python3
"""
Fix assignment titles in Google Classroom to use proper lesson names.
"""

import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_assignment.json'

EXPECTED_COURSES = {
    "1 Instructional Practices & Practicum",
    "2 Communications and Technology",
    "3 Instructional Practices & Practicum",
    "4 Communications and Technology",
    "5 Instructional Practices & Practicum",
    "6 Communications and Technology",
    "7 Instructional Practices & Practicum",
    "8 Communications and Technology",
}


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds


def main():
    if len(sys.argv) < 3:
        print("Usage: python fix_assignment_titles.py <old_title_contains> <new_title>")
        print("Example: python fix_assignment_titles.py 'GCI' 'Every Kid Needs a Champion'")
        sys.exit(1)

    old_contains = sys.argv[1]
    new_title = sys.argv[2]

    print(f"Searching for assignments containing: '{old_contains}'")
    print(f"Will rename to: '{new_title}'")

    creds = get_credentials()
    service = build('classroom', 'v1', credentials=creds)

    # Get courses
    courses = []
    page_token = None
    while True:
        response = service.courses().list(
            teacherId='me',
            courseStates=['ACTIVE'],
            pageToken=page_token
        ).execute()
        courses.extend(response.get('courses', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    courses = [c for c in courses if c['name'] in EXPECTED_COURSES]
    print(f"Found {len(courses)} courses")

    updated = 0
    for course in courses:
        course_id = course['id']
        course_name = course['name']

        # Get coursework
        try:
            response = service.courses().courseWork().list(courseId=course_id).execute()
            coursework_list = response.get('courseWork', [])
        except HttpError:
            continue

        for cw in coursework_list:
            if old_contains.lower() in cw['title'].lower():
                print(f"  {course_name}: '{cw['title']}' -> '{new_title}'")
                try:
                    service.courses().courseWork().patch(
                        courseId=course_id,
                        id=cw['id'],
                        updateMask='title',
                        body={'title': new_title}
                    ).execute()
                    updated += 1
                    time.sleep(0.2)
                except HttpError as e:
                    print(f"    ERROR: {e}")

    print(f"\nUpdated {updated} assignments")


if __name__ == '__main__':
    main()
