#!/usr/bin/env python3
"""
backfill_tracker.py - Backfill tracking spreadsheet with existing assignments and completions

This script:
1. Scans Classroom for all existing assignments
2. Finds their associated Forms
3. Records them in the tracking spreadsheet
4. Fetches all form responses and records completions

Usage:
    python scripts/backfill_tracker.py --dry-run   # Preview
    python scripts/backfill_tracker.py             # Execute
"""

import argparse
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add scripts directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sheets_tracker import GYOTracker

# OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/forms.responses.readonly',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_backfill.json'

TARGET_COURSES = [
    '1 Instructional Practices & Practicum',
    '2 Communications and Technology',
    '3 Instructional Practices & Practicum',
    '4 Communications and Technology',
    '5 Instructional Practices & Practicum',
    '6 Communications and Technology',
    '7 Instructional Practices & Practicum',
    '8 Communications and Technology',
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


def main():
    parser = argparse.ArgumentParser(description='Backfill tracker with existing data')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    print("=" * 70)
    print("BACKFILL TRACKER")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Initialize services
    creds = get_credentials()
    classroom = build('classroom', 'v1', credentials=creds)
    forms = build('forms', 'v1', credentials=creds)

    # Initialize tracker
    tracker = GYOTracker(dry_run=args.dry_run)
    print(f"Tracker URL: {tracker.get_spreadsheet_url()}\n")

    # Get courses
    print("Fetching courses...")
    courses_result = classroom.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = {c['name']: c for c in courses_result.get('courses', []) if c['name'] in TARGET_COURSES}
    print(f"Found {len(courses)} target courses\n")

    # Build student email -> name mapping
    print("Building student roster...")
    student_by_email = {}
    student_by_id = {}

    for course_name, course in sorted(courses.items()):
        try:
            students_result = classroom.courses().students().list(courseId=course['id']).execute()
            for student in students_result.get('students', []):
                user_id = student['userId']
                profile = student.get('profile', {})
                email = profile.get('emailAddress', '')
                name = profile.get('name', {}).get('fullName', 'Unknown')
                if email:
                    student_by_email[email] = {'name': name, 'courses': [], 'user_id': user_id}
                    student_by_id[user_id] = {'name': name, 'email': email}
                student_by_email.get(email, {}).get('courses', []).append(course_name)
        except HttpError:
            pass

    print(f"Found {len(student_by_email)} students\n")

    # Find all assignments with forms
    print("Scanning assignments for forms...")
    assignments = {}  # title -> {form_id, slides_id, form_url, etc.}

    for course_name, course in courses.items():
        try:
            coursework_result = classroom.courses().courseWork().list(courseId=course['id']).execute()
            for cw in coursework_result.get('courseWork', []):
                title = cw['title']
                if title in assignments:
                    continue  # Already processed

                form_id = None
                form_url = None
                slides_id = None
                slides_url = None

                for material in cw.get('materials', []):
                    if 'form' in material:
                        form_url = material['form'].get('formUrl', '')
                        if '/d/' in form_url:
                            form_id = form_url.split('/d/')[1].split('/')[0]
                    elif 'driveFile' in material:
                        drive_file = material['driveFile'].get('driveFile', {})
                        file_url = drive_file.get('alternateLink', '')
                        if 'presentation' in file_url or '/p/' in file_url:
                            slides_url = file_url
                            if '/d/' in file_url:
                                slides_id = file_url.split('/d/')[1].split('/')[0]

                if form_id:
                    assignments[title] = {
                        'form_id': form_id,
                        'form_url': form_url,
                        'slides_id': slides_id or '',
                        'slides_url': slides_url or '',
                    }
        except HttpError:
            continue

    print(f"Found {len(assignments)} assignments with forms\n")

    # Record assignments in tracker
    print("=" * 70)
    print("RECORDING ASSIGNMENTS")
    print("=" * 70)

    for title, data in sorted(assignments.items()):
        # Get total points from form
        total_points = 0
        try:
            form_info = forms.forms().get(formId=data['form_id']).execute()
            for item in form_info.get('items', []):
                question_item = item.get('questionItem', {})
                question = question_item.get('question', {})
                grading = question.get('grading', {})
                points = grading.get('pointValue', 0)
                total_points += points
        except HttpError:
            total_points = 8  # Default assumption

        print(f"\n  {title}")
        print(f"    Form ID: {data['form_id'][:20]}...")
        print(f"    Total Points: {total_points}")

        tracker.record_assignment(
            assignment_title=title,
            form_id=data['form_id'],
            form_url=data['form_url'],
            slides_id=data['slides_id'],
            slides_url=data['slides_url'],
            total_points=total_points,
            status="ACTIVE"
        )

    # Fetch and record form responses
    print("\n" + "=" * 70)
    print("RECORDING QUIZ COMPLETIONS")
    print("=" * 70)

    completions_count = 0

    for title, data in sorted(assignments.items()):
        form_id = data['form_id']

        try:
            # Get form info for total points
            form_info = forms.forms().get(formId=form_id).execute()

            total_points = 0
            for item in form_info.get('items', []):
                question_item = item.get('questionItem', {})
                question = question_item.get('question', {})
                grading = question.get('grading', {})
                points = grading.get('pointValue', 0)
                total_points += points

            # Get responses
            responses_result = forms.forms().responses().list(formId=form_id).execute()
            responses = responses_result.get('responses', [])

            if responses:
                print(f"\n  {title}: {len(responses)} responses")

                for resp in responses:
                    response_id = resp.get('responseId', '')
                    respondent_email = resp.get('respondentEmail', '')
                    total_score = resp.get('totalScore')
                    submitted_at = resp.get('lastSubmittedTime', resp.get('createTime', ''))

                    # Look up student name
                    student_info = student_by_email.get(respondent_email, {'name': 'Unknown'})
                    student_name = student_info['name']

                    # Find which course they're in
                    course = student_info.get('courses', ['Unknown'])[0] if student_info.get('courses') else 'Unknown'

                    print(f"    - {student_name}: {total_score}/{total_points}")

                    tracker.record_quiz_completion(
                        response_id=response_id,
                        assignment_title=title,
                        form_id=form_id,
                        student_email=respondent_email if respondent_email else '(no email)',
                        student_name=student_name,
                        course=course,
                        score=total_score,
                        total_points=total_points,
                        submitted_at=submitted_at,
                        notes="Backfilled from existing data"
                    )
                    completions_count += 1

        except HttpError as e:
            print(f"  Error processing {title}: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Assignments recorded: {len(assignments)}")
    print(f"  Completions recorded: {completions_count}")
    print(f"\n  Tracker: {tracker.get_spreadsheet_url()}")

    if args.dry_run:
        print("\n  [DRY RUN - No changes were made]")


if __name__ == '__main__':
    main()
