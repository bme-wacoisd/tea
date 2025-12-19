#!/usr/bin/env python3
"""Fix due time for assignments to 8:00 AM."""

import time
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

print("Updating due times to 8:00 AM...")

for course in sorted(courses, key=lambda c: c['name']):
    course_id = course['id']
    course_name = course['name']

    response = service.courses().courseWork().list(courseId=course_id).execute()
    for cw in response.get('courseWork', []):
        if cw['title'] == 'Every Kid Needs a Champion':
            print(f"  {course_name}: Updating due time...")
            service.courses().courseWork().patch(
                courseId=course_id,
                id=cw['id'],
                updateMask='dueDate,dueTime',
                body={
                    'dueDate': {'year': 2026, 'month': 2, 'day': 13},
                    'dueTime': {'hours': 8, 'minutes': 0}
                }
            ).execute()
            time.sleep(0.2)

print("\nDone! Verifying...")

# Verify
for course in sorted(courses, key=lambda c: c['name']):
    response = service.courses().courseWork().list(courseId=course['id']).execute()
    for cw in response.get('courseWork', []):
        if cw['title'] == 'Every Kid Needs a Champion':
            due_time = cw.get('dueTime', {})
            print(f"  {course['name']}: {due_time.get('hours')}:{due_time.get('minutes', 0):02d}")
