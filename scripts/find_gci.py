#!/usr/bin/env python3
"""Find anything with 'GCI' in Google Classroom."""

import json
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

print("Searching for 'GCI' in all assignment data...\n")

for course in sorted(courses, key=lambda c: c['name']):
    course_id = course['id']
    course_name = course['name']

    response = service.courses().courseWork().list(courseId=course_id).execute()
    for cw in response.get('courseWork', []):
        # Convert to JSON string and search
        cw_json = json.dumps(cw)
        if 'GCI' in cw_json or 'gci' in cw_json.lower():
            print(f"FOUND in {course_name}:")
            print(json.dumps(cw, indent=2))
            print("-" * 60)

        # Also print the full structure for the first course to see what's there
        if course_name == "1 Instructional Practices & Practicum":
            print(f"\nFull assignment data for {course_name}:")
            print(json.dumps(cw, indent=2))
            break  # Just first assignment
