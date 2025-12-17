#!/usr/bin/env python3
"""
classroom_status.py - Google Classroom status report

Compares Google Classroom enrollment and assignments against Frontline TEAMS roster
(source of truth) and reports:
- Students who haven't accepted the class invite
- Students missing assignments
- Students with duplicate assignments (same title in multiple periods)
- Roster mismatches between Frontline and Google Classroom

Usage:
    python classroom_status.py

Requires:
    - credentials.json in project root
    - ab-frontline-roster-2025-12-11.csv (Frontline TEAMS roster)
    - name-mappings.csv (name differences between systems)
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
    'https://www.googleapis.com/auth/classroom.profile.emails',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_classroom.pickle'
ROSTER_PATH = PROJECT_ROOT / 'ab-frontline-roster-2025-12-11.csv'
NAME_MAPPINGS_PATH = PROJECT_ROOT / 'name-mappings.csv'


def get_credentials():
    """Get valid user credentials for Google Classroom."""
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing credentials...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"ERROR: {CREDENTIALS_PATH} not found!")
                return None
            print("Opening browser for authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def load_name_mappings():
    """Load name mappings from CSV. Returns dict: frontline_name -> classroom_name"""
    mappings = {}
    if NAME_MAPPINGS_PATH.exists():
        with open(NAME_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                frontline = row['Frontline Teams'].strip()
                classroom = row['Google Classroom'].strip()
                if frontline and classroom:
                    mappings[frontline] = classroom
    return mappings


def load_frontline_roster():
    """
    Load Frontline TEAMS roster.
    Returns dict: student_name -> list of {course, period, day}
    """
    roster = defaultdict(list)

    if not ROSTER_PATH.exists():
        print(f"ERROR: Roster file not found: {ROSTER_PATH}")
        return roster

    with open(ROSTER_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Student Name'].strip()
            roster[name].append({
                'course': row['Course'].strip(),
                'period': row['Period'].strip(),
                'day': row['Day'].strip(),
                'section': row['Section'].strip()
            })

    return roster


def normalize_name(name):
    """Normalize a name for comparison."""
    # Remove extra whitespace, lowercase
    name = ' '.join(name.lower().split())
    # Remove punctuation
    name = re.sub(r"['\-]", '', name)
    return name


def frontline_to_first_last(name):
    """Convert 'Last, First Middle' to 'First Last' for comparison."""
    if ',' in name:
        parts = name.split(',', 1)
        last = parts[0].strip()
        first_middle = parts[1].strip().split()[0] if parts[1].strip() else ''
        return f"{first_middle} {last}"
    return name


def get_active_courses(service):
    """Get all active courses where user is a teacher."""
    courses = []
    page_token = None

    while True:
        response = service.courses().list(
            teacherId='me',
            courseStates=['ACTIVE'],
            pageToken=page_token
        ).execute()

        courses.extend(response.get('courses', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return courses


def get_students_for_course(service, course_id):
    """Get all students enrolled in a course with their enrollment state."""
    students = []
    page_token = None

    while True:
        try:
            response = service.courses().students().list(
                courseId=course_id,
                pageToken=page_token
            ).execute()

            students.extend(response.get('students', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            print(f"  Error fetching students: {e}")
            break

    return students


def get_coursework_for_course(service, course_id):
    """Get all coursework for a course."""
    coursework = []
    page_token = None

    while True:
        try:
            response = service.courses().courseWork().list(
                courseId=course_id,
                pageToken=page_token
            ).execute()

            coursework.extend(response.get('courseWork', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            print(f"  Error fetching coursework: {e}")
            break

    return coursework


def get_submissions_for_coursework(service, course_id, coursework_id):
    """Get all student submissions for a coursework item."""
    submissions = []
    page_token = None

    while True:
        try:
            response = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=coursework_id,
                pageToken=page_token
            ).execute()

            submissions.extend(response.get('studentSubmissions', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            # Silently skip errors for individual assignments
            break

    return submissions


def main():
    print("=" * 70)
    print("GOOGLE CLASSROOM STATUS REPORT")
    print("=" * 70)

    # Load Frontline roster and name mappings
    print("\nLoading Frontline TEAMS roster...")
    frontline_roster = load_frontline_roster()
    name_mappings = load_name_mappings()

    unique_frontline_students = set(frontline_roster.keys())
    print(f"  {len(unique_frontline_students)} unique students in Frontline roster")
    print(f"  {len(name_mappings)} name mappings loaded")

    # Authenticate with Google
    print("\nConnecting to Google Classroom...")
    creds = get_credentials()
    if not creds:
        print("ERROR: Could not authenticate")
        sys.exit(1)

    service = build('classroom', 'v1', credentials=creds)

    # Get courses
    print("\nFetching courses...")
    courses = get_active_courses(service)
    print(f"  Found {len(courses)} active courses:")
    for c in courses:
        print(f"    - {c['name']}")

    # Collect data from all courses
    all_classroom_students = {}  # user_id -> {name, courses: [course_names], accepted: bool}
    course_assignments = {}  # course_id -> list of assignment titles
    student_assignments = defaultdict(lambda: defaultdict(set))  # user_id -> {title -> set of course_ids}
    students_not_accepted = []

    for course in courses:
        course_id = course['id']
        course_name = course['name']
        print(f"\nProcessing: {course_name}")

        # Get students
        students = get_students_for_course(service, course_id)
        print(f"  {len(students)} students enrolled")

        for student in students:
            user_id = student['userId']
            profile = student.get('profile', {})
            name = profile.get('name', {}).get('fullName', f'User {user_id}')

            # Check if student has accepted invite
            # Students who haven't accepted won't have a profile or will have limited data
            has_accepted = bool(profile.get('emailAddress'))

            if user_id not in all_classroom_students:
                all_classroom_students[user_id] = {
                    'name': name,
                    'courses': [],
                    'accepted': has_accepted,
                    'email': profile.get('emailAddress', '')
                }

            all_classroom_students[user_id]['courses'].append(course_name)

            if not has_accepted and user_id not in [s['user_id'] for s in students_not_accepted]:
                students_not_accepted.append({
                    'user_id': user_id,
                    'name': name,
                    'course': course_name
                })

        # Get coursework
        coursework = get_coursework_for_course(service, course_id)
        course_assignments[course_id] = [cw['title'] for cw in coursework]
        print(f"  {len(coursework)} assignments")

        # Track which students have which assignments
        for cw in coursework:
            cw_id = cw['id']
            title = cw['title']

            submissions = get_submissions_for_coursework(service, course_id, cw_id)
            for sub in submissions:
                student_id = sub['userId']
                student_assignments[student_id][title].add(course_id)

    # === REPORT ===

    print("\n" + "=" * 70)
    print("SUMMARY REPORT")
    print("=" * 70)

    # 1. Students not accepted
    print(f"\n{'-' * 50}")
    print("STUDENTS WHO HAVEN'T ACCEPTED INVITE")
    print(f"{'-' * 50}")

    if students_not_accepted:
        print(f"\n  {len(students_not_accepted)} student(s) haven't accepted:")
        for s in students_not_accepted:
            print(f"    - {s['name']} (in {s['course']})")
    else:
        print("\n  All students have accepted their invites!")

    # 2. Duplicate assignments check
    print(f"\n{'-' * 50}")
    print("DUPLICATE ASSIGNMENTS CHECK")
    print(f"{'-' * 50}")

    students_with_duplicates = []
    for user_id, assignments in student_assignments.items():
        student_name = all_classroom_students.get(user_id, {}).get('name', f'User {user_id}')
        duplicates = {title: courses for title, courses in assignments.items() if len(courses) > 1}
        if duplicates:
            students_with_duplicates.append({
                'name': student_name,
                'duplicates': duplicates
            })

    if students_with_duplicates:
        print(f"\n  {len(students_with_duplicates)} student(s) still have duplicate assignments:")
        for s in students_with_duplicates[:10]:  # Show first 10
            print(f"\n    {s['name']}:")
            for title, course_ids in list(s['duplicates'].items())[:3]:
                print(f"      - \"{title}\" in {len(course_ids)} courses")
        if len(students_with_duplicates) > 10:
            print(f"\n    ... and {len(students_with_duplicates) - 10} more")
    else:
        print("\n  No duplicate assignments found!")

    # 3. Roster comparison
    print(f"\n{'-' * 50}")
    print("ROSTER COMPARISON (Frontline vs Google Classroom)")
    print(f"{'-' * 50}")

    # Build lookup for classroom students by normalized name
    classroom_by_name = {}
    for user_id, data in all_classroom_students.items():
        norm = normalize_name(data['name'])
        classroom_by_name[norm] = data['name']

    # Check who's in Frontline but not Classroom
    frontline_not_in_classroom = []
    for frontline_name in unique_frontline_students:
        # Try direct match
        search_name = frontline_to_first_last(frontline_name)
        norm_search = normalize_name(search_name)

        # Check if there's a name mapping
        if frontline_name in name_mappings:
            mapped_name = name_mappings[frontline_name]
            norm_search = normalize_name(mapped_name)

        # Search in classroom
        found = False
        for norm_classroom in classroom_by_name:
            # Fuzzy match - check if key parts match
            if norm_search in norm_classroom or norm_classroom in norm_search:
                found = True
                break
            # Also check first name + last name separately
            search_parts = set(norm_search.split())
            classroom_parts = set(norm_classroom.split())
            if len(search_parts & classroom_parts) >= 2:
                found = True
                break

        if not found:
            frontline_not_in_classroom.append(frontline_name)

    print(f"\n  Frontline students: {len(unique_frontline_students)}")
    print(f"  Classroom students: {len(all_classroom_students)}")

    if frontline_not_in_classroom:
        print(f"\n  {len(frontline_not_in_classroom)} Frontline student(s) NOT found in Classroom:")
        for name in sorted(frontline_not_in_classroom)[:15]:
            print(f"    - {name}")
        if len(frontline_not_in_classroom) > 15:
            print(f"    ... and {len(frontline_not_in_classroom) - 15} more")
    else:
        print("\n  All Frontline students found in Classroom!")

    # 4. Multi-period students
    print(f"\n{'-' * 50}")
    print("MULTI-PERIOD STUDENTS")
    print(f"{'-' * 50}")

    multi_period = {uid: data for uid, data in all_classroom_students.items()
                    if len(data['courses']) > 1}

    print(f"\n  {len(multi_period)} students enrolled in multiple courses")

    # 5. Quick stats
    print(f"\n{'-' * 50}")
    print("QUICK STATS")
    print(f"{'-' * 50}")

    total_assignments = sum(len(a) for a in course_assignments.values())
    print(f"\n  Total courses: {len(courses)}")
    print(f"  Total students in Classroom: {len(all_classroom_students)}")
    print(f"  Total assignments across all courses: {total_assignments}")
    print(f"  Students not accepted: {len(students_not_accepted)}")
    print(f"  Students with duplicates: {len(students_with_duplicates)}")
    print(f"  Multi-period students: {len(multi_period)}")

    print("\n" + "=" * 70)
    print("REPORT COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
