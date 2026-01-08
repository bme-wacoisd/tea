#!/usr/bin/env python3
"""
Update the reading portion of a deployed lesson assignment without touching the worksheet.

This script:
1. Reads the updated reading.md from a lesson folder
2. Finds the existing Classroom assignments by title
3. Extracts the GROUP DISCUSSION section from current assignment
4. Rebuilds description with new reading + existing worksheet
5. Patches all 8 course assignments with updated description

SAFE: Uses API patch (no notifications sent, no deletion, preserves all other fields)
"""

import argparse
import os
import re
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add parent directory to path for shared utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
]

TOKEN_FILE = 'token_update_reading.json'
CREDENTIALS_FILE = 'credentials.json'

# Expected course names (used to validate we're updating the right courses)
EXPECTED_COURSES = [
    '1 Instructional Practices & Practicum',
    '2 Communications and Technology',
    '3 Instructional Practices & Practicum',
    '4 Communications and Technology',
    '5 Instructional Practices & Practicum',
    '6 Communications and Technology',
    '7 Instructional Practices & Practicum',
    '8 Communications and Technology',
]


def authenticate():
    """Authenticate with Google Classroom API."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                print(f"Please download OAuth credentials from Google Cloud Console.")
                sys.exit(1)

            print("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_FILE}")

    return build('classroom', 'v1', credentials=creds)


def load_lesson_files(lesson_path):
    """Load reading.md and extract title from quiz.md."""
    lesson_dir = Path(lesson_path)

    if not lesson_dir.exists():
        print(f"ERROR: Lesson directory not found: {lesson_dir}")
        sys.exit(1)

    reading_file = lesson_dir / 'reading.md'
    quiz_file = lesson_dir / 'quiz.md'

    if not reading_file.exists():
        print(f"ERROR: reading.md not found in {lesson_dir}")
        sys.exit(1)

    if not quiz_file.exists():
        print(f"ERROR: quiz.md not found in {lesson_dir}")
        sys.exit(1)

    with open(reading_file, 'r', encoding='utf-8') as f:
        reading_content = f.read().strip()

    # Extract title from quiz.md (format: "# Quiz: Title")
    with open(quiz_file, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if first_line.startswith('# Quiz:'):
            title = first_line.replace('# Quiz:', '').strip()
        else:
            print(f"ERROR: Could not extract title from quiz.md")
            print(f"Expected format: '# Quiz: Title'")
            print(f"Got: {first_line}")
            sys.exit(1)

    return {
        'title': title,
        'reading': reading_content,
    }


def find_assignments(service, title_search):
    """Find all assignments matching the title across all courses."""
    print(f"Searching for assignments matching: {title_search}")

    # Get all courses
    courses_result = service.courses().list().execute()
    courses = courses_result.get('courses', [])

    # Filter to expected courses
    course_map = {}
    for course in courses:
        if course['name'] in EXPECTED_COURSES:
            course_map[course['name']] = course

    if len(course_map) != 8:
        print(f"WARNING: Expected 8 courses, found {len(course_map)}")
        print(f"Found: {list(course_map.keys())}")

    # Find matching assignments
    found = []
    for course_name in sorted(course_map.keys()):
        course = course_map[course_name]
        course_id = course['id']

        try:
            coursework_result = service.courses().courseWork().list(
                courseId=course_id
            ).execute()

            for assignment in coursework_result.get('courseWork', []):
                if title_search.lower() in assignment.get('title', '').lower():
                    found.append({
                        'course_name': course_name,
                        'course_id': course_id,
                        'assignment_id': assignment['id'],
                        'title': assignment['title'],
                        'description': assignment.get('description', ''),
                    })
                    print(f"  Found in {course_name}: {assignment['title']}")

        except HttpError as e:
            print(f"  Error fetching assignments for {course_name}: {e}")

    return found


def extract_worksheet_section(description):
    """Extract the GROUP DISCUSSION section from assignment description."""
    # Pattern: everything from "GROUP DISCUSSION" onwards
    match = re.search(r'GROUP DISCUSSION\s*\n-+\n(.*)', description, re.DOTALL)

    if match:
        return match.group(0)  # Return entire section including header
    else:
        print("WARNING: Could not find GROUP DISCUSSION section in description")
        return None


def build_new_description(reading_content, worksheet_section):
    """Build new assignment description with updated reading."""
    if worksheet_section:
        return f"""READING
-------
{reading_content}

{worksheet_section}"""
    else:
        # Fallback if we couldn't extract worksheet
        return f"""READING
-------
{reading_content}

MATERIALS
---------
After reading and discussing, complete the quiz to check your understanding."""


def update_assignments(service, assignments, new_description, dry_run=True):
    """Update assignment descriptions via API patch."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Updating {len(assignments)} assignments...")

    for assignment in assignments:
        course_id = assignment['course_id']
        assignment_id = assignment['assignment_id']
        course_name = assignment['course_name']

        if dry_run:
            print(f"  [DRY RUN] Would update: {course_name}")
        else:
            try:
                service.courses().courseWork().patch(
                    courseId=course_id,
                    id=assignment_id,
                    updateMask='description',
                    body={'description': new_description}
                ).execute()
                print(f"  UPDATED: {course_name}")

            except HttpError as e:
                print(f"  ERROR updating {course_name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Update reading.md in deployed lesson assignments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry run)
  python update_lesson_reading.py lessons/23-samr-technology

  # Apply changes
  python update_lesson_reading.py lessons/23-samr-technology --apply

  # Apply without confirmation
  python update_lesson_reading.py lessons/23-samr-technology --apply -y

SAFETY NOTES:
  - Uses API patch (no student notifications sent)
  - Only updates description field (preserves materials, due dates, etc.)
  - Dry run by default (use --apply to execute)
  - Extracts and preserves GROUP DISCUSSION section
"""
    )
    parser.add_argument('lesson_path', help='Path to lesson folder (e.g., lessons/23-samr-technology)')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    # Dry run mode
    dry_run = not args.apply

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)

    # Load lesson files
    print(f"\nLoading lesson files from: {args.lesson_path}")
    lesson_data = load_lesson_files(args.lesson_path)

    print(f"Lesson title: {lesson_data['title']}")
    print(f"Reading length: {len(lesson_data['reading'])} characters")

    # Authenticate
    print("\nAuthenticating...")
    service = authenticate()

    # Find existing assignments
    print()
    assignments = find_assignments(service, lesson_data['title'])

    if not assignments:
        print(f"\nERROR: No assignments found matching '{lesson_data['title']}'")
        sys.exit(1)

    print(f"\nFound {len(assignments)} assignments")

    # Extract worksheet section from first assignment (should be same across all)
    first_assignment = assignments[0]
    worksheet_section = extract_worksheet_section(first_assignment['description'])

    if not worksheet_section and not dry_run:
        print("\nWARNING: Could not extract GROUP DISCUSSION section.")
        print("This may result in losing the worksheet content.")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # Build new description
    new_description = build_new_description(lesson_data['reading'], worksheet_section)

    print(f"\nNew description length: {len(new_description)} characters")
    print("\nPreview of new description (first 500 chars):")
    print("-" * 60)
    print(new_description[:500])
    print("-" * 60)

    # Confirm if not dry run and not auto-confirmed
    if not dry_run and not args.yes:
        print(f"\nThis will update {len(assignments)} assignments across all 8 courses.")
        print("No student notifications will be sent (API updates are silent).")
        response = input("\nProceed with update? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # Update assignments
    update_assignments(service, assignments, new_description, dry_run=dry_run)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE - No changes were made")
        print("=" * 60)
        print("\nTo apply changes, run with --apply flag")
    else:
        print("\n" + "=" * 60)
        print("UPDATE COMPLETE")
        print("=" * 60)
        print(f"\nUpdated {len(assignments)} assignments")
        print("Students will see the new reading next time they open the assignment.")


if __name__ == '__main__':
    main()
