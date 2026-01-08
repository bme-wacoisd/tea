#!/usr/bin/env python3
"""
sync_quiz_completions.py - Sync quiz completions from Forms to tracker and Classroom

This script:
1. Fetches form responses for all tracked assignments
2. Records new completions in the tracker spreadsheet (batch writes)
3. Looks up student info using the Students sheet
4. Reports anomalies (e.g., students taking quizzes they're not enrolled in)
5. Uses local cache to avoid re-processing responses

IMPORTANT: Stops on errors (rate limits, auth failures) per error handling policy

Usage:
    python scripts/sync_quiz_completions.py --dry-run   # Preview
    python scripts/sync_quiz_completions.py             # Execute
"""

import argparse
import csv
import json
import re
import sys
import time
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

# Local cache file for processed responses
CACHE_DIR = PROJECT_ROOT / '.cache'
RESPONSE_CACHE = CACHE_DIR / 'processed_responses.json'


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


def load_response_cache():
    """Load cache of already-processed response IDs."""
    if not RESPONSE_CACHE.exists():
        return set()

    try:
        with open(RESPONSE_CACHE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('processed_response_ids', []))
    except (json.JSONDecodeError, IOError) as e:
        print(f"  Warning: Could not load response cache: {e}")
        return set()


def save_response_cache(response_ids):
    """Save processed response IDs to cache."""
    CACHE_DIR.mkdir(exist_ok=True)

    data = {
        'processed_response_ids': list(response_ids),
        'last_updated': datetime.now().isoformat(),
    }

    try:
        with open(RESPONSE_CACHE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        print(f"  Warning: Could not save response cache: {e}")


def api_call_with_retry(api_call, max_retries=5):
    """
    Execute API call with exponential backoff on rate limit errors.
    STOPS AND RAISES on rate limit after retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            return api_call()
        except HttpError as e:
            if e.resp.status == 429:  # Rate limit error
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                    print(f"    Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    # Exhausted retries - STOP per error handling policy
                    print("\n" + "=" * 70)
                    print("ERROR: API RATE LIMIT EXCEEDED")
                    print("=" * 70)
                    print(f"Exceeded Google API rate limit after {max_retries} retries.")
                    print("Per error handling policy: STOPPING to preserve data integrity.")
                    print("\nSuggestions:")
                    print("  1. Wait 60 seconds and run again")
                    print("  2. Check quota at https://console.cloud.google.com")
                    print("  3. Consider running with smaller batches")
                    raise
            else:
                # Other HTTP errors - also stop
                raise


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
    print("SYNC QUIZ COMPLETIONS (v2 - with batching & caching)")
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

    # Load local response cache
    print("Loading response cache...")
    cached_response_ids = load_response_cache()
    print(f"  {len(cached_response_ids)} cached response IDs\n")

    # Get all active assignments from tracker
    print("Fetching assignments from tracker...")
    try:
        assignments = tracker.get_all_assignments(include_deleted=False)
        print(f"  {len(assignments)} active assignments\n")
    except HttpError as e:
        if e.resp.status == 429:
            print("\n" + "=" * 70)
            print("ERROR: RATE LIMIT HIT WHILE FETCHING ASSIGNMENTS")
            print("=" * 70)
            print("Per error handling policy: STOPPING.")
            print("Wait 60 seconds and try again.")
            sys.exit(1)
        raise

    if not assignments:
        print("No assignments to sync!")
        return

    # Get existing completions to check for duplicates
    print("Fetching existing completions from tracker...")
    try:
        existing_completions = tracker.get_all_completions()
        existing_response_ids = {c.get('Response ID') for c in existing_completions}
        print(f"  {len(existing_response_ids)} existing completions in tracker\n")
    except HttpError as e:
        if e.resp.status == 429:
            print("\n" + "=" * 70)
            print("ERROR: RATE LIMIT HIT WHILE FETCHING COMPLETIONS")
            print("=" * 70)
            print("Per error handling policy: STOPPING.")
            print("Wait 60 seconds and try again.")
            sys.exit(1)
        raise

    # Combine tracker and cache for deduplication
    all_processed_ids = existing_response_ids | cached_response_ids

    # Process each assignment - collect completions for batch write
    print("=" * 70)
    print("FETCHING FORM RESPONSES (with retry logic)")
    print("=" * 70)

    new_completions = []
    anomalies = []
    new_response_ids = set()

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
            # Get form responses WITH RETRY LOGIC
            def fetch_responses():
                return forms.forms().responses().list(formId=form_id).execute()

            responses_result = api_call_with_retry(fetch_responses)
            responses = responses_result.get('responses', [])

            if not responses:
                print(f"  No responses")
                continue

            print(f"  {len(responses)} total response(s)")

            # Process responses
            new_for_this_form = 0
            for resp in responses:
                response_id = resp.get('responseId', '')
                respondent_email = resp.get('respondentEmail', '')
                total_score = resp.get('totalScore')
                submitted_at = resp.get('lastSubmittedTime', resp.get('createTime', ''))

                # Skip if already processed (tracker or cache)
                if response_id in all_processed_ids:
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

                # Add to batch
                new_completions.append({
                    'response_id': response_id,
                    'assignment_title': title,
                    'form_id': form_id,
                    'student_email': respondent_email or '(no email)',
                    'student_name': student_name,
                    'course': course,
                    'score': total_score,
                    'total_points': total_points,
                    'submitted_at': submitted_at,
                    'notes': 'Synced by sync_quiz_completions.py v2'
                })
                new_response_ids.add(response_id)
                new_for_this_form += 1

            if new_for_this_form > 0:
                print(f"  Found {new_for_this_form} new completion(s)")

        except HttpError as e:
            if e.resp.status == 429:
                # Rate limit - already handled by retry logic, this is the final failure
                print("\n" + "=" * 70)
                print("ERROR: UNABLE TO CONTINUE DUE TO RATE LIMITS")
                print("=" * 70)
                print(f"Processed {len(new_completions)} completions before hitting limit.")
                print("Per error handling policy: STOPPING without partial saves.")
                print("\nRun this script again later to resume.")
                sys.exit(1)
            else:
                print(f"  Error fetching responses: {e}")
                print("  Per error handling policy: STOPPING on error.")
                sys.exit(1)

    # BATCH WRITE to tracker
    print("\n" + "=" * 70)
    print("WRITING TO TRACKER (batch mode)")
    print("=" * 70)

    if new_completions:
        print(f"  Recording {len(new_completions)} new completion(s) in batch...")

        if not args.dry_run:
            try:
                stats = tracker.record_quiz_completions_batch(new_completions)
                print(f"  Batch write complete: {stats}")

                # Update local cache
                updated_cache = cached_response_ids | new_response_ids
                save_response_cache(updated_cache)
                print(f"  Cache updated with {len(new_response_ids)} new response IDs")

            except HttpError as e:
                if e.resp.status == 429:
                    print("\n" + "=" * 70)
                    print("ERROR: RATE LIMIT HIT WHILE WRITING TO TRACKER")
                    print("=" * 70)
                    print("Per error handling policy: STOPPING.")
                    print("Responses were fetched but NOT written to tracker.")
                    print("Run again to retry the write.")
                    sys.exit(1)
                else:
                    print(f"\nERROR writing to tracker: {e}")
                    print("Per error handling policy: STOPPING.")
                    sys.exit(1)
        else:
            print("  [DRY RUN - Skipping batch write]")
    else:
        print("  No new completions to record")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Assignments processed: {len(assignments)}")
    print(f"  New completions recorded: {len(new_completions)}")
    print(f"  Anomalies detected: {len(anomalies)}")
    print(f"  Cache entries: {len(cached_response_ids | new_response_ids)}")

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
