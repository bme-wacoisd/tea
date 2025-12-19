#!/usr/bin/env python3
"""Update assignment description in Google Classroom."""

import re
import sys
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


def main():
    if len(sys.argv) < 3:
        print("Usage: python update_assignment_description.py <assignment_title> <lesson_folder>")
        print("Example: python update_assignment_description.py 'Every Kid Needs a Champion' lessons/08-every-kid-needs-champion/")
        sys.exit(1)

    assignment_title = sys.argv[1]
    lesson_path = Path(sys.argv[2])

    reading_path = lesson_path / 'reading.md'
    worksheet_path = lesson_path / 'worksheet.md'

    if not reading_path.exists() or not worksheet_path.exists():
        print(f"ERROR: reading.md or worksheet.md not found in {lesson_path}")
        sys.exit(1)

    # Read content
    reading_content = reading_path.read_text(encoding='utf-8')
    worksheet_content = worksheet_path.read_text(encoding='utf-8')

    # Strip markdown headers
    reading_content = re.sub(r'^#.*\n+', '', reading_content).strip()
    worksheet_content = re.sub(r'^#.*\n+', '', worksheet_content).strip()

    # Build description
    description = f"""READING
-------
{reading_content}

GROUP DISCUSSION
----------------
{worksheet_content}

MATERIALS
---------
After reading and discussing, complete the quiz to check your understanding."""

    print(f"Updating assignments titled: '{assignment_title}'")
    print(f"Reading: {len(reading_content)} chars")
    print(f"Worksheet: {len(worksheet_content)} chars")

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    service = build('classroom', 'v1', credentials=creds)

    # Get courses
    response = service.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = [c for c in response.get('courses', []) if c['name'] in EXPECTED_COURSES]

    updated = 0
    for course in sorted(courses, key=lambda c: c['name']):
        course_id = course['id']
        course_name = course['name']

        response = service.courses().courseWork().list(courseId=course_id).execute()
        for cw in response.get('courseWork', []):
            if cw['title'] == assignment_title:
                print(f"  {course_name}: Updating...")
                try:
                    service.courses().courseWork().patch(
                        courseId=course_id,
                        id=cw['id'],
                        updateMask='description',
                        body={'description': description}
                    ).execute()
                    updated += 1
                except Exception as e:
                    print(f"    ERROR: {e}")
                time.sleep(0.2)

    print(f"\nUpdated {updated} assignments")


if __name__ == '__main__':
    main()
