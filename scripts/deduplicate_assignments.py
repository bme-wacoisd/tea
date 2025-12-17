#!/usr/bin/env python3
"""
deduplicate_assignments.py - Remove duplicate Google Classroom assignments for multi-period students

When you assign work to multiple class periods at once, students enrolled in more than one
period receive the same assignment multiple times. This script identifies those duplicates
and removes all but one, distributing assignments evenly across each student's periods.

Usage:
    python deduplicate_assignments.py              # Dry run (shows what would change)
    python deduplicate_assignments.py --apply      # Actually make changes
    python deduplicate_assignments.py --apply -y   # Apply without confirmation

Requirements:
    pip install google-auth-oauthlib google-api-python-client

Setup:
    1. Enable Google Classroom API in Google Cloud Console
    2. Create OAuth 2.0 Desktop credentials
    3. Download as credentials.json in project root
    4. Run script - browser will open for authorization on first run

Security:
    - credentials.json and token.json must be in .gitignore (they are)
    - Student data (names, IDs, enrollments) is ONLY held in memory
    - NO student PII is ever written to disk
    - All data is discarded when script exits
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes required for this script
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
]

# Look for credentials in project root
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_dedup.json'

# API rate limiting
API_DELAY = 0.1  # seconds between API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries


def api_call_with_retry(func, *args, **kwargs):
    """Execute an API call with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(API_DELAY)
            return func(*args, **kwargs).execute()
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:  # Rate limit or server errors
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    print(f"    API error, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
            raise
    return None


def get_credentials():
    """Get valid user credentials, refreshing or initiating OAuth flow as needed."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"ERROR: {CREDENTIALS_PATH} not found!")
                print("Download OAuth credentials from Google Cloud Console.")
                sys.exit(1)
            print("Opening browser for authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_PATH}")

    return creds


def get_active_courses(service):
    """Get all active courses where user is a teacher."""
    print("\nFetching active courses...")
    courses = []
    page_token = None

    while True:
        response = api_call_with_retry(
            service.courses().list,
            teacherId='me',
            courseStates=['ACTIVE'],
            pageToken=page_token
        )
        if not response:
            break

        courses.extend(response.get('courses', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    # Sort by course name for consistent ordering
    courses.sort(key=lambda c: c['name'])

    print(f"  Found {len(courses)} active courses")
    for course in courses:
        print(f"    - {course['name']}")

    return courses


def get_students_for_course(service, course_id):
    """Get all students enrolled in a course."""
    students = []
    page_token = None

    while True:
        try:
            response = api_call_with_retry(
                service.courses().students().list,
                courseId=course_id,
                pageToken=page_token
            )
            if not response:
                break

            students.extend(response.get('students', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError:
            break

    return students


def get_coursework_for_course(service, course_id):
    """Get all coursework (assignments) for a course."""
    coursework = []
    page_token = None

    while True:
        try:
            response = api_call_with_retry(
                service.courses().courseWork().list,
                courseId=course_id,
                pageToken=page_token
            )
            if not response:
                break

            coursework.extend(response.get('courseWork', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError:
            break

    return coursework


def find_multi_period_students(service, courses):
    """Find students enrolled in more than one course."""
    print("\nFinding multi-period students...")

    # Map student ID -> list of courses they're in
    student_courses = defaultdict(list)
    # Map student ID -> profile info
    student_profiles = {}

    for i, course in enumerate(courses):
        course_id = course['id']
        course_name = course['name']
        print(f"  [{i+1}/{len(courses)}] Checking enrollment in {course_name}...")

        students = get_students_for_course(service, course_id)
        for student in students:
            user_id = student['userId']
            profile = student.get('profile', {})
            name = profile.get('name', {}).get('fullName', f'User {user_id}')

            student_courses[user_id].append({
                'course_id': course_id,
                'course_name': course_name
            })
            student_profiles[user_id] = name

    # Filter to only multi-period students
    multi_period = {
        user_id: sorted(courses_list, key=lambda c: c['course_name'])
        for user_id, courses_list in student_courses.items()
        if len(courses_list) > 1
    }

    print(f"\n  Found {len(multi_period)} students in multiple periods")

    return multi_period, student_profiles


def find_duplicate_assignments(service, courses):
    """Find assignments with the same title across multiple courses."""
    print("\nFinding duplicate assignments...")

    # Map title -> list of (course_id, coursework_id, coursework_data)
    assignments_by_title = defaultdict(list)

    for i, course in enumerate(courses):
        course_id = course['id']
        course_name = course['name']
        print(f"  [{i+1}/{len(courses)}] Fetching assignments from {course_name}...")

        coursework_list = get_coursework_for_course(service, course_id)
        for cw in coursework_list:
            title = cw['title']
            assignments_by_title[title].append({
                'course_id': course_id,
                'course_name': course_name,
                'coursework_id': cw['id'],
                'coursework': cw
            })

    # Filter to only duplicates (same title in 2+ courses)
    duplicates = {
        title: assignments
        for title, assignments in assignments_by_title.items()
        if len(assignments) > 1
    }

    print(f"\n  Found {len(duplicates)} assignments appearing in multiple courses:")
    for title, assignments in sorted(duplicates.items()):
        course_names = sorted([a['course_name'] for a in assignments])
        print(f"    - \"{title}\" in {len(course_names)} courses")

    return duplicates


class AssigneeCache:
    """Cache for assignment assignee data to reduce API calls."""

    def __init__(self, service):
        self.service = service
        self.cache = {}  # (course_id, coursework_id) -> (is_all_students, student_ids)

    def get(self, course_id, coursework_id, course_students):
        """Get assignees for an assignment, using cache when available."""
        key = (course_id, coursework_id)
        if key in self.cache:
            return self.cache[key]

        try:
            cw = api_call_with_retry(
                self.service.courses().courseWork().get,
                courseId=course_id,
                id=coursework_id
            )
            if not cw:
                return False, []

            assignee_mode = cw.get('assigneeMode', 'ALL_STUDENTS')

            if assignee_mode == 'ALL_STUDENTS':
                student_ids = [s['userId'] for s in course_students]
                result = (True, student_ids)
            else:
                individual = cw.get('individualStudentsOptions', {})
                student_ids = individual.get('studentIds', [])
                result = (False, student_ids)

            self.cache[key] = result
            return result

        except HttpError as e:
            print(f"      ERROR getting assignees: {e}")
            return False, []

    def invalidate(self, course_id, coursework_id):
        """Remove an entry from cache after modification."""
        key = (course_id, coursework_id)
        if key in self.cache:
            del self.cache[key]


def remove_student_from_assignment(service, course_id, coursework_id, student_id,
                                   is_all_students, all_student_ids, cache, dry_run=True):
    """
    Remove a student from an assignment.
    If assignment is set to 'all students', converts to individual mode first.
    """
    if is_all_students:
        # Need to convert to individual student mode, excluding this student
        new_student_ids = [sid for sid in all_student_ids if sid != student_id]

        body = {
            'assigneeMode': 'INDIVIDUAL_STUDENTS',
            'modifyIndividualStudentsOptions': {
                'addStudentIds': new_student_ids
            }
        }
    else:
        # Already in individual mode, just remove this student
        body = {
            'assigneeMode': 'INDIVIDUAL_STUDENTS',
            'modifyIndividualStudentsOptions': {
                'removeStudentIds': [student_id]
            }
        }

    if dry_run:
        return True, "DRY RUN"

    try:
        api_call_with_retry(
            service.courses().courseWork().modifyAssignees,
            courseId=course_id,
            id=coursework_id,
            body=body
        )
        # Invalidate cache since we modified this assignment
        cache.invalidate(course_id, coursework_id)
        return True, "DONE"
    except HttpError as e:
        error_msg = str(e)
        if 'notFound' in error_msg.lower():
            return True, "ALREADY REMOVED"
        return False, f"ERROR: {e}"


def deduplicate_for_student(service, student_id, student_name, student_courses,
                           duplicate_assignments, course_students, cache, dry_run=True):
    """
    For one student, distribute their duplicate assignments across periods using round-robin.
    Returns (changes_made, errors_encountered).

    Handles "EmptyAssignees" errors by trying alternate periods - if removing from period A
    would leave no assignees, we keep the assignment there and remove from the original
    "keep" period instead.
    """
    enrolled_course_ids = [c['course_id'] for c in student_courses]
    enrolled_course_names = {c['course_id']: c['course_name'] for c in student_courses}

    changes = 0
    errors = 0

    # Sort assignments by title for consistent ordering
    sorted_titles = sorted(duplicate_assignments.keys())

    # Round-robin index for this student
    rr_index = 0

    for title in sorted_titles:
        assignments = duplicate_assignments[title]

        # Filter to assignments in courses this student is enrolled in
        student_assignments = [
            a for a in assignments
            if a['course_id'] in enrolled_course_ids
        ]

        if len(student_assignments) <= 1:
            continue

        # Determine which period keeps this assignment (round-robin)
        keep_index = rr_index % len(enrolled_course_ids)
        keep_course_id = enrolled_course_ids[keep_index]
        rr_index += 1

        print(f"    \"{title}\"")
        print(f"      Keep in: {enrolled_course_names[keep_course_id]}")

        # Track which course actually ends up keeping it (may change if we hit EmptyAssignees)
        actual_keep_course_id = keep_course_id
        courses_to_remove_from = []

        # First pass: identify which courses we can remove from
        for assignment in student_assignments:
            course_id = assignment['course_id']
            if course_id != keep_course_id:
                courses_to_remove_from.append(assignment)

        # Remove from all other periods, with fallback logic
        for assignment in courses_to_remove_from:
            course_id = assignment['course_id']
            coursework_id = assignment['coursework_id']
            course_name = assignment['course_name']

            if course_id == actual_keep_course_id:
                continue

            # Get current assignees
            students_in_course = course_students.get(course_id, [])
            is_all_students, all_student_ids = cache.get(
                course_id, coursework_id, students_in_course
            )

            # Check if student is actually assigned
            if student_id not in all_student_ids:
                print(f"      Remove from {course_name}: SKIP (not assigned)")
                continue

            # Try to remove student
            success, status = remove_student_from_assignment(
                service, course_id, coursework_id, student_id,
                is_all_students, all_student_ids, cache, dry_run
            )

            # If we got EmptyAssignees error, try to keep this one and remove from original keep instead
            if not success and 'EmptyAssignees' in status:
                print(f"      Remove from {course_name}: SWAP (would empty, keeping here instead)")

                # Try to remove from the original keep course instead
                orig_keep_assignment = next(
                    (a for a in student_assignments if a['course_id'] == actual_keep_course_id),
                    None
                )

                if orig_keep_assignment:
                    orig_course_id = orig_keep_assignment['course_id']
                    orig_coursework_id = orig_keep_assignment['coursework_id']
                    orig_course_name = orig_keep_assignment['course_name']

                    orig_students = course_students.get(orig_course_id, [])
                    orig_is_all, orig_all_ids = cache.get(
                        orig_course_id, orig_coursework_id, orig_students
                    )

                    if student_id in orig_all_ids:
                        swap_success, swap_status = remove_student_from_assignment(
                            service, orig_course_id, orig_coursework_id, student_id,
                            orig_is_all, orig_all_ids, cache, dry_run
                        )
                        print(f"      Remove from {orig_course_name} (swapped): {swap_status}")

                        if swap_success:
                            changes += 1
                            actual_keep_course_id = course_id  # Update which course is keeping it
                        else:
                            errors += 1
                    else:
                        print(f"      Remove from {orig_course_name} (swapped): SKIP (not assigned)")
                continue

            print(f"      Remove from {course_name}: {status}")

            if success:
                changes += 1
            else:
                errors += 1

    return changes, errors


def main():
    parser = argparse.ArgumentParser(
        description='Remove duplicate Google Classroom assignments for multi-period students.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deduplicate_assignments.py              # Preview changes (dry run)
  python deduplicate_assignments.py --apply      # Actually make changes
  python deduplicate_assignments.py --apply -y   # Apply without confirmation

How it works:
  1. Finds students enrolled in multiple of your class periods
  2. Identifies assignments with the same title across those periods
  3. For each student, keeps each assignment in only ONE period
  4. Distributes assignments evenly using round-robin
        """
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually make changes (default is dry-run mode)'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompt when using --apply'
    )
    args = parser.parse_args()

    dry_run = not args.apply

    print("=" * 60)
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print("Use --apply to actually remove duplicates")
    else:
        print("APPLY MODE - Changes WILL be made")
    print("=" * 60)

    if args.apply and not args.yes:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # Authenticate
    print("\nAuthenticating with Google Classroom API...")
    creds = get_credentials()
    service = build('classroom', 'v1', credentials=creds)

    # Get courses
    courses = get_active_courses(service)
    if not courses:
        print("No active courses found. Exiting.")
        sys.exit(0)

    # Build course students cache
    print("\nBuilding enrollment cache...")
    course_students = {}
    for course in courses:
        course_id = course['id']
        course_students[course_id] = get_students_for_course(service, course_id)

    # Find multi-period students
    multi_period_students, student_profiles = find_multi_period_students(service, courses)
    if not multi_period_students:
        print("\nNo students found in multiple periods. Nothing to deduplicate.")
        sys.exit(0)

    # Find duplicate assignments
    duplicate_assignments = find_duplicate_assignments(service, courses)
    if not duplicate_assignments:
        print("\nNo duplicate assignments found. Nothing to deduplicate.")
        sys.exit(0)

    # Create assignee cache
    cache = AssigneeCache(service)

    # Process each multi-period student
    print("\n" + "=" * 60)
    print("DEDUPLICATION")
    print("=" * 60)

    total_changes = 0
    total_errors = 0
    students_processed = 0

    sorted_students = sorted(
        multi_period_students.items(),
        key=lambda x: student_profiles.get(x[0], '')
    )

    for student_id, student_courses_list in sorted_students:
        students_processed += 1
        student_name = student_profiles.get(student_id, f"User {student_id}")

        print(f"\n[{students_processed}/{len(multi_period_students)}] {student_name}")
        print(f"  Courses: {', '.join(c['course_name'] for c in student_courses_list)}")

        changes, errors = deduplicate_for_student(
            service, student_id, student_name, student_courses_list,
            duplicate_assignments, course_students, cache, dry_run
        )
        total_changes += changes
        total_errors += errors

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Multi-period students: {len(multi_period_students)}")
    print(f"  Duplicate assignments: {len(duplicate_assignments)}")
    print(f"  Removals performed:    {total_changes}")
    if total_errors > 0:
        print(f"  Errors encountered:    {total_errors}")

    if dry_run:
        print("\nThis was a DRY RUN. No changes were made.")
        print("Run with --apply to actually make these changes.")
    else:
        print("\nChanges have been applied.")


if __name__ == '__main__':
    main()
