#!/usr/bin/env python3
"""List all assignments in courses."""

from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent
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

creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
service = build('classroom', 'v1', credentials=creds)

courses = []
response = service.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
courses = [c for c in response.get('courses', []) if c['name'] in EXPECTED_COURSES]

for course in sorted(courses, key=lambda c: c['name']):
    print(f"\n{course['name']}:")
    try:
        response = service.courses().courseWork().list(courseId=course['id']).execute()
        for cw in response.get('courseWork', []):
            due = cw.get('dueDate', {})
            due_time = cw.get('dueTime', {})
            print(f"  - {cw['title']}")
            print(f"    Due: {due.get('month')}/{due.get('day')}/{due.get('year')} {due_time.get('hours')}:{due_time.get('minutes', 0):02d}")
    except Exception as e:
        print(f"  Error: {e}")
