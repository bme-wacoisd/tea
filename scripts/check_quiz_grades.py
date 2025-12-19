#!/usr/bin/env python3
"""
Check for grades on quiz assignments in Google Classroom courses.

Filters to periods 1-8 (excludes Lovelace) and looks for quiz-type assignments
that have graded student submissions.
"""

import os
import sys
from pathlib import Path

# Allow OAuth to proceed even if granted scopes differ from requested
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes required for reading coursework and grades (as teacher)
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
]

# File paths for credentials
SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'token_quiz_grades.json'  # Separate token for different scopes


def authenticate():
    """Handle Google OAuth 2.0 authentication."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: {CREDENTIALS_FILE} not found!")
                print("See deduplicate_assignments.py for setup instructions.")
                sys.exit(1)

            print("Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print("Authentication successful!")

    return creds


def is_target_course(course_name):
    """Check if course is periods 1-8 (not Lovelace)."""
    name_lower = course_name.lower()

    # Exclude Lovelace
    if 'lovelace' in name_lower:
        return False

    # Check for period indicators (1-8)
    # Common patterns: "Period 1", "P1", "1st", etc.
    for period in range(1, 9):
        patterns = [
            f'period {period}',
            f'period{period}',
            f'p{period}',
            f' {period} ',
            f'({period})',
            f'-{period}-',
            f'-{period})',
            f'({period}-',
        ]
        for pattern in patterns:
            if pattern in name_lower or name_lower.startswith(f'{period} ') or name_lower.endswith(f' {period}'):
                return True

    # If no Lovelace and no clear period number, include it (might be relevant)
    return True


def is_quiz_assignment(work):
    """Check if coursework is a quiz.

    Quiz assignments from tea/lessons have:
    - A numbered title pattern (e.g., "01 James Baldwin: Civil Rights")
    - One attachment - a Google Form quiz linked for auto-grading
    """
    # Check workType field
    work_type = work.get('workType', '')
    if work_type in ['QUIZ', 'MULTIPLE_CHOICE_QUESTION', 'SHORT_ANSWER_QUESTION']:
        return True

    # Check title for quiz indicators
    title_lower = work.get('title', '').lower()
    quiz_keywords = ['quiz', 'test', 'exam', 'assessment']
    if any(keyword in title_lower for keyword in quiz_keywords):
        return True

    # Check for tea/lessons pattern: starts with 2-digit number
    title = work.get('title', '')
    if len(title) >= 2 and title[:2].isdigit():
        return True

    # Check if it has a Google Form attachment (forms are typically quizzes)
    materials = work.get('materials', [])
    for material in materials:
        if 'form' in material:
            return True

    return False


def check_quiz_grades(service):
    """Find quiz assignments with grades in periods 1-8."""
    print("\nFetching your courses...")

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

    if not courses:
        print("No active courses found.")
        return

    # Filter to target courses (1-8, not Lovelace)
    target_courses = [c for c in courses if is_target_course(c['name'])]
    excluded = len(courses) - len(target_courses)

    print(f"\nFound {len(courses)} total courses, {len(target_courses)} match periods 1-8 (excluded {excluded}):")
    for c in target_courses:
        print(f"  - {c['name']}")

    print("\n" + "="*70)
    print("Checking for quiz assignments with grades...")
    print("="*70)

    quizzes_with_grades = []
    quizzes_without_grades = []

    for course in target_courses:
        course_name = course['name']
        course_id = course['id']

        print(f"\n[{course_name}]")

        # Get all coursework
        try:
            coursework = []
            page_token = None

            while True:
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
            continue

        # Filter to quizzes
        quizzes = [w for w in coursework if is_quiz_assignment(w)]

        if not quizzes:
            print("  No quiz assignments found")
            continue

        print(f"  Found {len(quizzes)} quiz assignment(s):")

        for quiz in quizzes:
            quiz_title = quiz['title']
            quiz_id = quiz['id']
            max_points = quiz.get('maxPoints', 'ungraded')
            work_type = quiz.get('workType', 'ASSIGNMENT')

            # Get student submissions
            try:
                submissions = []
                page_token = None

                while True:
                    response = service.courses().courseWork().studentSubmissions().list(
                        courseId=course_id,
                        courseWorkId=quiz_id,
                        pageToken=page_token
                    ).execute()

                    submissions.extend(response.get('studentSubmissions', []))
                    page_token = response.get('nextPageToken')
                    if not page_token:
                        break

            except HttpError as e:
                print(f"    - {quiz_title}: Error fetching submissions: {e}")
                continue

            # Count graded submissions
            graded = [s for s in submissions if s.get('assignedGrade') is not None]
            total = len(submissions)

            grade_info = f"{len(graded)}/{total} graded"

            if graded:
                # Calculate grade stats
                grades = [s['assignedGrade'] for s in graded]
                avg = sum(grades) / len(grades)
                grade_info += f" (avg: {avg:.1f}"
                if max_points != 'ungraded':
                    grade_info += f"/{max_points}"
                grade_info += ")"

                quizzes_with_grades.append({
                    'course': course_name,
                    'title': quiz_title,
                    'graded_count': len(graded),
                    'total_count': total,
                    'avg_grade': avg,
                    'max_points': max_points,
                    'work_type': work_type
                })
                print(f"    [GRADED] {quiz_title} [{work_type}] - {grade_info}")
            else:
                quizzes_without_grades.append({
                    'course': course_name,
                    'title': quiz_title,
                    'total_count': total,
                    'max_points': max_points,
                    'work_type': work_type
                })
                print(f"    [NO GRADES] {quiz_title} [{work_type}] - {grade_info}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if quizzes_with_grades:
        print(f"\nQUIZZES WITH GRADES ({len(quizzes_with_grades)}):")
        for q in quizzes_with_grades:
            print(f"  - {q['course']}: {q['title']} ({q['graded_count']} students graded)")
    else:
        print("\nNo quizzes have grades yet.")

    if quizzes_without_grades:
        print(f"\nQUIZZES WITHOUT GRADES ({len(quizzes_without_grades)}):")
        for q in quizzes_without_grades:
            print(f"  - {q['course']}: {q['title']} ({q['total_count']} submissions)")

    return quizzes_with_grades


def main():
    print("Google Classroom Quiz Grade Checker")
    print("="*70)

    creds = authenticate()
    service = build('classroom', 'v1', credentials=creds)

    try:
        check_quiz_grades(service)
    except HttpError as error:
        print(f"\nAPI Error: {error}")
        sys.exit(1)

    print("\nDone!")


if __name__ == '__main__':
    main()
