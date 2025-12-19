#!/usr/bin/env python3
"""Fix materials titles in Google Classroom assignments."""

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

print("Fixing materials titles...")

for course in sorted(courses, key=lambda c: c['name']):
    course_id = course['id']
    course_name = course['name']

    response = service.courses().courseWork().list(courseId=course_id).execute()
    for cw in response.get('courseWork', []):
        if cw['title'] == 'Every Kid Needs a Champion':
            print(f"\n{course_name}:")

            # Get current materials
            materials = cw.get('materials', [])
            new_materials = []

            for mat in materials:
                if 'link' in mat:
                    url = mat['link']['url']
                    old_title = mat['link'].get('title', 'Unknown')

                    # Determine new title based on URL
                    if 'forms.google.com' in url or 'forms/d/e' in url:
                        new_title = "Quiz: Every Kid Needs a Champion"
                    else:
                        new_title = old_title

                    print(f"  Link: '{old_title}' -> '{new_title}'")
                    new_materials.append({
                        'link': {
                            'url': url,
                            'title': new_title
                        }
                    })
                elif 'driveFile' in mat:
                    # Keep drive files as-is, they have correct titles
                    old_title = mat['driveFile']['driveFile'].get('title', 'Unknown')
                    print(f"  Drive: '{old_title}' (keeping)")
                    new_materials.append(mat)
                else:
                    new_materials.append(mat)

            # Update the coursework with fixed materials
            try:
                service.courses().courseWork().patch(
                    courseId=course_id,
                    id=cw['id'],
                    updateMask='materials',
                    body={'materials': new_materials}
                ).execute()
                print(f"  Updated!")
            except Exception as e:
                print(f"  ERROR: {e}")

            time.sleep(0.3)

print("\nDone!")
