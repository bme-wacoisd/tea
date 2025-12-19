#!/usr/bin/env python3
"""
sync_quiz_completions.py - Sync quiz completions from Forms to tracker and Classroom

This script:
1. Fetches form responses for all tracked assignments
2. Records new completions in the tracker spreadsheet
3. Looks up student info using the Students sheet
4. Reports anomalies (e.g., students taking quizzes they're not enrolled in)

Usage:
    python scripts/sync_quiz_completions.py --dry-run   # Preview
    python scripts/sync_quiz_completions.py             # Execute
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from datetime import datetime

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
    'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/forms.responses.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_sync.json'

# Student lookup file
STUDENT_LOOKUP = PROJECT_ROOT / 'student_lookup' / 'students_latest.csv'


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
    """Load student lookup table for email -> name/course mapping."""
    students = {}  # email (both formats) -> student data

    if not STUDENT_LOOKUP.exists():
        print(f"  Warning: Student lookup file not found: {STUDENT_LOOKUP}")
        print(f"  Run: python scripts/build_student_lookup.py")
        return students

    with open(STUDENT_LOOKUP, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            student_data = {
                'student_id': row.get('Student ID', ''),
                'name': row.get('Name (Classroom)', ''),
                'frontline_name': row.get('Name (Frontline)', ''),
                'periods': row.get('Periods', ''),
                'course_types': row.get('Course Types', ''),
            }

            # Index by both email types
            id_email = row.get('ID Email', '')
            name_email = row.get('Name Email', '')

            if id_email:
                students[id_email.lower()] = student_data
            if name_email:
                students[name_email.lower()] = student_data

    return students


def extract_student_id(email):
    """Extract student ID from email like s30020013@student.wacoisd.org"""
    if not email:
        return None
    match = re.match(r's(\d+)@student\.wacoisd\.org', email.lower())
    if match:
        return match.group(1)
    return None


def get_course_type_from_title(title):
    """Determine course type from assignment title pattern."""
    # Could be enhanced with actual mapping logic
    return "Unknown"


def main():
    parser = argparse.ArgumentParser(description='Sync quiz completions to tracker')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    print("=" * 70)
    print("SYNC QUIZ COMPLETIONS")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Initialize services
    creds = get_credentials()
    forms = build('forms', 'v1', credentials=creds)

    # Initialize tracker
    tracker = GYOTracker(dry_run=args.dry_run)
    print(f"Tracker: {tracker.get_spreadsheet_url()}\n")

    # Load student lookup
    print("Loading student lookup...")
    student_lookup = load_student_lookup()
    print(f"  {len(student_lookup)} email entries loaded\n")

    # Get all active assignments from tracker
    print("Fetching assignments from tracker...")
    assignments = tracker.get_all_assignments(include_deleted=False)
    print(f"  {len(assignments)} active assignments\n")

    if not assignments:
        print("No assignments to sync!")
        return

    # Get existing completions to check for duplicates
    existing_completions = tracker.get_all_completions()
    existing_response_ids = {c.get('Response ID') for c in existing_completions}
    print(f"  {len(existing_response_ids)} existing completions in tracker\n")

    # Process each assignment
    print("=" * 70)
    print("FETCHING FORM RESPONSES")
    print("=" * 70)

    new_completions = 0
    anomalies = []

    for assignment in assignments:
        title = assignment.get('Assignment Title', '')
        form_id = assignment.get('Form ID', '')
        total_points_str = assignment.get('Total Points', '0')

        try:
            total_points = int(total_points_str) if total_points_str else 0
        except ValueError:
            total_points = 0

        if not form_id:
            continue

        print(f"\n{title}")
        print(f"  Form ID: {form_id[:20]}...")

        try:
            # Get form responses
            responses_result = forms.forms().responses().list(formId=form_id).execute()
            responses = responses_result.get('responses', [])

            if not responses:
                print(f"  No responses")
                continue

            print(f"  {len(responses)} response(s)")

            for resp in responses:
                response_id = resp.get('responseId', '')
                respondent_email = resp.get('respondentEmail', '')
                total_score = resp.get('totalScore')
                submitted_at = resp.get('lastSubmittedTime', resp.get('createTime', ''))

                # Skip if already tracked
                if response_id in existing_response_ids:
                    continue

                # Look up student
                student_info = student_lookup.get(respondent_email.lower(), {})
                student_name = student_info.get('name', 'Unknown')
                student_periods = student_info.get('periods', '')
                student_course_types = student_info.get('course_types', '')

                # Determine which course this quiz is for
                # (This would need assignment -> course mapping)
                course = "Unknown"

                # Check for anomalies
                if respondent_email and not student_info:
                    anomalies.append({
                        'type': 'UNKNOWN_STUDENT',
                        'email': respondent_email,
                        'assignment': title,
                        'message': f"Email not in student lookup: {respondent_email}"
                    })
                elif student_info and not respondent_email:
                    anomalies.append({
                        'type': 'NO_EMAIL',
                        'assignment': title,
                        'message': "Form response has no email (old form without email collection)"
                    })

                print(f"    NEW: {student_name} ({respondent_email or 'no email'}) - {total_score}/{total_points}")

                # Record completion
                tracker.record_quiz_completion(
                    response_id=response_id,
                    assignment_title=title,
                    form_id=form_id,
                    student_email=respondent_email or '(no email)',
                    student_name=student_name,
                    course=course,
                    score=total_score,
                    total_points=total_points,
                    submitted_at=submitted_at,
                    notes="Synced by sync_quiz_completions.py"
                )
                new_completions += 1

        except HttpError as e:
            print(f"  Error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Assignments processed: {len(assignments)}")
    print(f"  New completions recorded: {new_completions}")
    print(f"  Anomalies detected: {len(anomalies)}")

    if anomalies:
        print("\n" + "=" * 70)
        print("ANOMALIES")
        print("=" * 70)
        for a in anomalies:
            print(f"  [{a['type']}] {a['assignment']}")
            print(f"    {a['message']}")

    print(f"\n  Tracker: {tracker.get_spreadsheet_url()}")

    if args.dry_run:
        print("\n  [DRY RUN - No changes were made]")


if __name__ == '__main__':
    main()
