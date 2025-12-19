#!/usr/bin/env python3
"""
build_student_lookup.py - Build comprehensive student lookup table

Extracts student data from:
1. Google Classroom rosters (authoritative for enrolled students)
2. Frontline roster CSV (for official name spellings)
3. Name mappings CSV (for Frontline <-> Classroom name differences)

Creates:
1. Local CSV file in student_lookup/ directory (gitignored)
2. Human-readable report in ~/Documents/gyo-student-roster/
3. Students sheet in the tracker spreadsheet

Student data includes:
- Student ID
- Full Name (Frontline spelling)
- Full Name (Google Classroom spelling)
- Grade level
- ID Email (s########@student.wacoisd.org)
- Name Email (firstname.lastname@student.wacoisd.org)
- Periods enrolled (in Mr. Edwards' classes)
- Course types (Instructional Practices, Communications)

IMPORTANT: This data contains PII - never commit to git!

Usage:
    python scripts/build_student_lookup.py --dry-run   # Preview
    python scripts/build_student_lookup.py             # Execute
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
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.profile.emails',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_student_lookup.json'

# Output paths (all gitignored or outside repo)
LOCAL_LOOKUP_DIR = PROJECT_ROOT / 'student_lookup'
DOCUMENTS_DIR = Path.home() / 'Documents' / 'gyo-student-roster'

# Roster files
FRONTLINE_ROSTER = Path.home() / 'google-classroom' / 'waco-teams-hosting' / 'rosters' / 'ab-frontline-roster-2025-12-11.csv'
NAME_MAPPINGS = Path.home() / 'google-classroom' / 'waco-teams-hosting' / 'rosters' / 'name-mappings.csv'

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

# Map course names to types
COURSE_TYPES = {
    '1 Instructional Practices & Practicum': 'Instructional Practices',
    '2 Communications and Technology': 'Communications',
    '3 Instructional Practices & Practicum': 'Instructional Practices',
    '4 Communications and Technology': 'Communications',
    '5 Instructional Practices & Practicum': 'Instructional Practices',
    '6 Communications and Technology': 'Communications',
    '7 Instructional Practices & Practicum': 'Instructional Practices',
    '8 Communications and Technology': 'Communications',
}

# CSV headers
CSV_HEADERS = [
    "Student ID",
    "Name (Frontline)",
    "Name (Classroom)",
    "Grade",
    "ID Email",
    "Name Email",
    "Classroom User ID",
    "Periods",
    "Course Types",
    "All Courses",
    "Last Updated"
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


def extract_student_id(email):
    """Extract student ID from email like s30020013@student.wacoisd.org"""
    if not email:
        return None
    match = re.match(r's(\d+)@student\.wacoisd\.org', email.lower())
    if match:
        return match.group(1)
    return None


def is_name_email(email):
    """Check if email is firstname.lastname format"""
    if not email:
        return False
    return '@student.wacoisd.org' in email.lower() and not email.lower().startswith('s')


def load_name_mappings():
    """Load Frontline -> Classroom name mappings"""
    mappings = {}
    reverse_mappings = {}
    if NAME_MAPPINGS.exists():
        with open(NAME_MAPPINGS, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                frontline = row.get('Frontline Teams', '').strip()
                classroom = row.get('Google Classroom', '').strip()
                if frontline and classroom:
                    mappings[frontline] = classroom
                    reverse_mappings[classroom.lower()] = frontline
    return mappings, reverse_mappings


def load_frontline_roster():
    """Load Frontline roster - source of truth for official names"""
    students = {}
    if FRONTLINE_ROSTER.exists():
        with open(FRONTLINE_ROSTER, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Student Name', '').strip()
                if not name:
                    continue

                if name not in students:
                    students[name] = {
                        'frontline_name': name,
                        'periods': set(),
                        'course_types': set(),
                        'courses': set()
                    }

                period = row.get('Period', '').strip()
                course_code = row.get('Course', '').strip()

                if period:
                    students[name]['periods'].add(period)

                    # Map period to course name and type
                    for course_name, course_type in COURSE_TYPES.items():
                        if course_name.startswith(period):
                            students[name]['course_types'].add(course_type)
                            students[name]['courses'].add(course_name)
    return students


def normalize_name(name):
    """Normalize name for matching (lowercase, no extra spaces)"""
    return ' '.join(name.lower().split())


def main():
    parser = argparse.ArgumentParser(description='Build student lookup table')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    print("=" * 70)
    print("BUILD COMPREHENSIVE STUDENT LOOKUP TABLE")
    print("=" * 70)
    print("\nIMPORTANT: This data contains student PII - never commit to git!\n")

    if args.dry_run:
        print("[DRY RUN MODE - No files will be written]\n")

    # Initialize services
    creds = get_credentials()
    classroom = build('classroom', 'v1', credentials=creds)

    # Load reference data
    print("Loading reference data...")
    name_mappings, reverse_mappings = load_name_mappings()
    print(f"  Name mappings: {len(name_mappings)} (Frontline -> Classroom differences)")

    frontline_roster = load_frontline_roster()
    print(f"  Frontline roster: {len(frontline_roster)} unique students")

    # Get courses
    print("\nFetching Google Classroom courses...")
    courses_result = classroom.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = {c['name']: c for c in courses_result.get('courses', []) if c['name'] in TARGET_COURSES}
    print(f"Found {len(courses)} target courses")

    # Build comprehensive student data
    print("\nBuilding student roster from Google Classroom...")

    # Key: normalized classroom name -> student data
    students = {}

    for course_name, course in sorted(courses.items()):
        period = course_name.split()[0]  # Extract period number
        course_type = COURSE_TYPES.get(course_name, 'Unknown')

        print(f"  Period {period} - {course_type}...")

        try:
            students_result = classroom.courses().students().list(courseId=course['id']).execute()
            for student in students_result.get('students', []):
                user_id = student.get('userId', '')
                profile = student.get('profile', {})
                email = profile.get('emailAddress', '')
                classroom_name = profile.get('name', {}).get('fullName', 'Unknown')

                if not classroom_name or classroom_name == 'Unknown':
                    continue

                # Create key for deduplication
                key = normalize_name(classroom_name)

                if key not in students:
                    students[key] = {
                        'student_id': '',
                        'frontline_name': '',
                        'classroom_name': classroom_name,
                        'grade': '',
                        'id_email': '',
                        'name_email': '',
                        'classroom_user_id': '',
                        'periods': set(),
                        'course_types': set(),
                        'courses': set()
                    }

                # Update with this course's data
                students[key]['periods'].add(period)
                students[key]['course_types'].add(course_type)
                students[key]['courses'].add(course_name)

                # Capture Classroom user ID (Google's internal ID)
                if user_id:
                    students[key]['classroom_user_id'] = user_id

                # Capture email (both types if available)
                student_id = extract_student_id(email)
                if student_id:
                    students[key]['student_id'] = student_id
                    students[key]['id_email'] = email
                elif is_name_email(email):
                    students[key]['name_email'] = email

        except HttpError as e:
            print(f"    Error: {e}")

    # Match with Frontline roster for official names and grades
    print("\nMatching with Frontline roster...")
    matched = 0

    for key, data in students.items():
        classroom_name = data['classroom_name']

        # Check if there's a known name mapping
        frontline_name = reverse_mappings.get(classroom_name.lower(), '')

        if not frontline_name:
            # Try to find by similar name in Frontline roster
            for fl_name in frontline_roster:
                # Frontline format: "Last, First Middle"
                # Classroom format: "First Last" or "First Middle Last"
                parts = fl_name.split(', ')
                if len(parts) == 2:
                    last, first_middle = parts
                    first = first_middle.split()[0]
                    # Simple match: first name and last name appear in classroom name
                    if first.lower() in classroom_name.lower() and last.lower() in classroom_name.lower():
                        frontline_name = fl_name
                        break

        if frontline_name and frontline_name in frontline_roster:
            data['frontline_name'] = frontline_name
            fl_data = frontline_roster[frontline_name]
            # Merge period/course data from Frontline
            data['periods'].update(fl_data['periods'])
            data['course_types'].update(fl_data['course_types'])
            data['courses'].update(fl_data['courses'])
            matched += 1
        else:
            data['frontline_name'] = '(not matched)'

    print(f"  Matched {matched} of {len(students)} students to Frontline roster")

    # Sort and prepare output
    print("\n" + "=" * 70)
    print("STUDENT LOOKUP TABLE")
    print("=" * 70)

    rows = []
    for key in sorted(students.keys()):
        data = students[key]

        periods_str = ', '.join(sorted(data['periods']))
        course_types_str = ', '.join(sorted(data['course_types']))
        courses_str = ' | '.join(sorted(data['courses']))

        row = {
            'Student ID': data['student_id'],
            'Name (Frontline)': data['frontline_name'],
            'Name (Classroom)': data['classroom_name'],
            'Grade': data['grade'],
            'ID Email': data['id_email'],
            'Name Email': data['name_email'],
            'Classroom User ID': data['classroom_user_id'],
            'Periods': periods_str,
            'Course Types': course_types_str,
            'All Courses': courses_str,
            'Last Updated': datetime.now().isoformat()
        }
        rows.append(row)

        # Print summary
        id_display = data['student_id'] if data['student_id'] else '(no ID)'
        email_display = data['id_email'] or data['name_email'] or '(no email)'
        print(f"  {id_display:>10} | {data['classroom_name']:<30} | P{periods_str:<10} | {email_display}")

    print(f"\nTotal students: {len(rows)}")

    if args.dry_run:
        print("\n[DRY RUN - No files written]")
        return

    # Create output directories
    LOCAL_LOOKUP_DIR.mkdir(exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d')

    # Write CSV to local gitignored directory
    csv_path = LOCAL_LOOKUP_DIR / f'students_{timestamp}.csv'
    print(f"\nWriting CSV: {csv_path}")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Also write a "latest" symlink/copy
    latest_csv = LOCAL_LOOKUP_DIR / 'students_latest.csv'
    with open(latest_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Write human-readable report to Documents
    report_path = DOCUMENTS_DIR / f'student-roster-{timestamp}.txt'
    print(f"Writing report: {report_path}")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("GYO STUDENT ROSTER\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        f.write("IMPORTANT: This file contains student PII - do not share or commit to git!\n\n")
        f.write("-" * 80 + "\n\n")

        for row in rows:
            f.write(f"Student: {row['Name (Classroom)']}\n")
            if row['Name (Frontline)'] and row['Name (Frontline)'] != '(not matched)':
                f.write(f"  Frontline Name: {row['Name (Frontline)']}\n")
            if row['Student ID']:
                f.write(f"  Student ID: {row['Student ID']}\n")
            if row['ID Email']:
                f.write(f"  ID Email: {row['ID Email']}\n")
            if row['Name Email']:
                f.write(f"  Name Email: {row['Name Email']}\n")
            f.write(f"  Periods: {row['Periods']}\n")
            f.write(f"  Course Types: {row['Course Types']}\n")
            f.write("\n")

    # Update tracker spreadsheet
    print("\nUpdating tracker spreadsheet...")
    tracker = GYOTracker(dry_run=False)
    spreadsheet_id = tracker.spreadsheet_id
    sheets_service = tracker.sheets_service

    # Check if Students sheet exists
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_names = [s['properties']['title'] for s in spreadsheet['sheets']]

    if 'Students' not in sheet_names:
        print("  Creating Students sheet...")
        request = {
            'addSheet': {
                'properties': {
                    'title': 'Students'
                }
            }
        }
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()

    # Prepare data for sheets
    sheet_rows = [[
        row['Student ID'],
        row['Name (Frontline)'],
        row['Name (Classroom)'],
        row['Grade'],
        row['ID Email'],
        row['Name Email'],
        row['Classroom User ID'],
        row['Periods'],
        row['Course Types'],
        row['All Courses'],
        row['Last Updated']
    ] for row in rows]

    # Write to sheet
    all_data = [CSV_HEADERS] + sheet_rows
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range='Students!A1',
        valueInputOption='RAW',
        body={'values': all_data}
    ).execute()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Students processed: {len(rows)}")
    print(f"  CSV saved: {csv_path}")
    print(f"  Report saved: {report_path}")
    print(f"  Tracker updated: {tracker.get_spreadsheet_url()}")


if __name__ == '__main__':
    main()
