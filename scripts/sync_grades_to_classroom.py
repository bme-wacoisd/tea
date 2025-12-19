#!/usr/bin/env python3
"""
sync_grades_to_classroom.py - Import quiz grades from Google Forms to Classroom gradebook

WHY THIS EXISTS:
We use Assignment + attached Form (with quiz settings) instead of Classroom's Quiz Assignment.
This gives us more control but means form grades don't auto-sync to the Classroom gradebook.
This script bridges that gap.

WORKFLOW:
1. Gets unsynced quiz completions from the tracker spreadsheet (form responses with scores)
2. Finds the corresponding Classroom submission for each student
3. Applies the grade directly to the Classroom gradebook
4. Marks the completion as synced in the tracker

GRADE CALCULATION:
- Form quiz scores are raw (e.g., 8/8)
- Classroom assignments have max points (e.g., 100)
- Converts: (form_score / form_total) * assignment_max = percentage grade
- Example: 8/8 on form -> 100/100 in Classroom

NOTES:
- Direct grading works without turn-in (submission can stay in CREATED state)
- Classroom API doesn't allow teachers to turn in on behalf of students
- Uses Classroom User ID from student lookup CSV for reliable matching
- Verifies state against tracker and updates tracker when done

Usage:
    python scripts/sync_grades_to_classroom.py --dry-run   # Preview
    python scripts/sync_grades_to_classroom.py             # Execute
"""

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from sheets_tracker import GYOTracker

# OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_grade_sync.json'

TARGET_COURSES = [
    '1 Instructional Practices & Practicum',
    '2 Communications and Technology',
    '3 Instructional Practices & Practicum',
    '4 Communications and Technology',
    '5 Instructional Practices & Practicum',
    '6 Communications and Technology',
    '7 Instructional Practices & Practicum',
    '8 Communications and Technology'
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


def load_student_lookup():
    """Load student lookup CSV with Classroom User IDs."""
    lookup = {}  # email/name -> {name, userId}
    student_lookup_path = PROJECT_ROOT / 'student_lookup' / 'students_latest.csv'

    if not student_lookup_path.exists():
        print(f"  Warning: Student lookup not found: {student_lookup_path}")
        print(f"  Run: python scripts/build_student_lookup.py")
        return lookup

    with open(student_lookup_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_email = row.get('ID Email', '').lower()
            name_email = row.get('Name Email', '').lower()
            name = row.get('Name (Classroom)', '')
            user_id = row.get('Classroom User ID', '')

            data = {'name': name, 'userId': user_id}

            if id_email:
                lookup[id_email] = data
            if name_email:
                lookup[name_email] = data
            if name:
                lookup[name.lower()] = data

    return lookup


def main():
    parser = argparse.ArgumentParser(description='Sync quiz grades from Forms to Classroom')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    print("=" * 70)
    print("SYNC QUIZ GRADES TO CLASSROOM")
    print("=" * 70)
    print("\nImporting grades from Google Forms into Classroom gradebook\n")

    if args.dry_run:
        print("[DRY RUN MODE - No changes will be made]\n")

    # Initialize services
    creds = get_credentials()
    classroom = build('classroom', 'v1', credentials=creds)

    # Initialize tracker
    tracker = GYOTracker(dry_run=args.dry_run)
    print(f"Tracker: {tracker.get_spreadsheet_url()}\n")

    # Load student lookup
    print("Loading student lookup...")
    student_lookup = load_student_lookup()
    print(f"  {len(student_lookup)} entries loaded\n")

    # Get unsynced completions from tracker
    print("Fetching unsynced quiz completions from tracker...")
    completions = tracker.get_unsynced_completions()
    print(f"  {len(completions)} unsynced completions\n")

    if not completions:
        print("All quiz completions are already synced!")
        return

    # Get courses
    print("Fetching courses...")
    courses_result = classroom.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = {c['name']: c for c in courses_result.get('courses', []) if c['name'] in TARGET_COURSES}
    print(f"  {len(courses)} target courses\n")

    # Build student roster from Classroom
    print("Building student roster from Classroom...")
    student_map = {}  # course_id -> {email/name/userId -> student_info}

    for course_name, course in courses.items():
        course_id = course['id']
        student_map[course_id] = {}

        try:
            students = classroom.courses().students().list(courseId=course_id).execute().get('students', [])
            for s in students:
                user_id = s['userId']
                email = s.get('profile', {}).get('emailAddress', '').lower()
                name = s.get('profile', {}).get('name', {}).get('fullName', '')

                info = {'userId': user_id, 'name': name, 'email': email}

                if email:
                    student_map[course_id][email] = info
                if name:
                    student_map[course_id][name.lower()] = info
                # Also index by userId for lookups from our CSV
                student_map[course_id][user_id] = info

        except HttpError as e:
            print(f"  Error fetching students for {course_name}: {e}")

    # Build assignment mapping
    print("Building assignment mapping...")
    assignment_map = {}  # course_id -> {title -> coursework}

    for course_name, course in courses.items():
        course_id = course['id']
        assignment_map[course_id] = {}

        try:
            coursework = classroom.courses().courseWork().list(courseId=course_id).execute().get('courseWork', [])
            for cw in coursework:
                title = cw['title']
                assignment_map[course_id][title] = cw
        except HttpError as e:
            print(f"  Error fetching coursework for {course_name}: {e}")

    # Process each completion
    print("\n" + "=" * 70)
    print("SYNCING GRADES")
    print("=" * 70)

    graded = 0
    already_graded = 0
    not_found = 0
    errors = 0

    for completion in completions:
        student_email = completion.get('Student Email', '').lower()
        student_name = completion.get('Student Name', '')
        assignment_title = completion.get('Assignment Title', '')
        score = completion.get('Score', '')
        total_points = completion.get('Total Points', '')
        response_id = completion.get('Response ID', '')

        print(f"\n{student_name or student_email} - {assignment_title}")
        print(f"  Score: {score}/{total_points}")

        # Get Classroom User ID from our lookup
        csv_user_id = None
        if student_email and student_email != '(no email)':
            csv_data = student_lookup.get(student_email)
            if csv_data:
                csv_user_id = csv_data.get('userId')
        if not csv_user_id and student_name:
            csv_data = student_lookup.get(student_name.lower())
            if csv_data:
                csv_user_id = csv_data.get('userId')

        # Find the student's submission across courses
        found = False

        for course_name, course in courses.items():
            course_id = course['id']

            # Find student in this course
            student_info = None

            # Method 1: By Classroom User ID from CSV
            if csv_user_id:
                student_info = student_map[course_id].get(csv_user_id)

            # Method 2: By email
            if not student_info and student_email and student_email != '(no email)':
                student_info = student_map[course_id].get(student_email)

            # Method 3: By name
            if not student_info and student_name:
                student_info = student_map[course_id].get(student_name.lower())

            if not student_info:
                continue

            user_id = student_info['userId']

            # Find assignment in this course
            coursework = assignment_map[course_id].get(assignment_title)
            if not coursework:
                continue

            cw_id = coursework['id']
            max_points = coursework.get('maxPoints', 100)  # Assignment max points in Classroom

            # Get student's submission
            try:
                submissions = classroom.courses().courseWork().studentSubmissions().list(
                    courseId=course_id,
                    courseWorkId=cw_id,
                    userId=user_id
                ).execute().get('studentSubmissions', [])

                if not submissions:
                    continue

                sub = submissions[0]
                sub_id = sub['id']
                state = sub.get('state', '')
                current_grade = sub.get('assignedGrade')

                print(f"  Found in {course_name} (state: {state})")

                # Check if already graded
                if current_grade is not None:
                    print(f"  Already graded: {current_grade}")
                    tracker.mark_synced_to_classroom(response_id, sub_id, notes="Already graded")
                    already_graded += 1
                    found = True
                    break

                # Calculate percentage grade
                # Form gives raw score (e.g., 8/8), Classroom expects percentage of max_points (e.g., 100/100)
                try:
                    form_score = float(score) if score else 0
                    form_total = float(total_points) if total_points else 1
                    percentage = form_score / form_total  # e.g., 8/8 = 1.0
                    grade_value = percentage * max_points  # e.g., 1.0 * 100 = 100
                except (ValueError, ZeroDivisionError):
                    grade_value = 0
                    print(f"  Warning: Could not calculate grade from {score}/{total_points}")

                # Apply grade
                if args.dry_run:
                    print(f"  [DRY RUN] Would grade: {form_score}/{form_total} = {percentage:.0%} -> {grade_value}/{max_points}")
                else:
                    try:
                        classroom.courses().courseWork().studentSubmissions().patch(
                            courseId=course_id,
                            courseWorkId=cw_id,
                            id=sub_id,
                            updateMask='assignedGrade,draftGrade',
                            body={
                                'assignedGrade': grade_value,
                                'draftGrade': grade_value
                            }
                        ).execute()
                        print(f"  Graded: {form_score}/{form_total} = {percentage:.0%} -> {grade_value}/{max_points}")
                        graded += 1

                        # Update tracker
                        tracker.mark_synced_to_classroom(response_id, sub_id)

                    except HttpError as e:
                        print(f"  Error grading: {e}")
                        errors += 1

                found = True
                break

            except HttpError as e:
                if e.resp.status != 404:
                    print(f"  Error: {e}")
                continue

        if not found:
            print(f"  NOT FOUND: Could not find submission in any course")
            not_found += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Completions processed: {len(completions)}")
    print(f"  Grades applied: {graded}")
    print(f"  Already graded: {already_graded}")
    print(f"  Not found: {not_found}")
    print(f"  Errors: {errors}")
    print(f"\n  Tracker: {tracker.get_spreadsheet_url()}")

    if args.dry_run:
        print("\n  [DRY RUN - No changes were made]")


if __name__ == '__main__':
    main()
