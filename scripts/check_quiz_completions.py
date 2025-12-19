#!/usr/bin/env python3
"""
check_quiz_completions.py - Check for completed quiz submissions

Finds students who have completed quizzes (Google Forms attached to assignments)
and reports their scores, regardless of whether they clicked "Turn In" in Classroom.

Usage:
    python scripts/check_quiz_completions.py
"""

import sys
from pathlib import Path
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/forms.responses.readonly',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_quiz_check.json'

# Our 8 courses
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
    """Get valid user credentials."""
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
                sys.exit(1)
            print("Opening browser for authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_PATH}")

    return creds


def main():
    print("=" * 70)
    print("QUIZ COMPLETION REPORT")
    print("=" * 70)

    creds = get_credentials()
    classroom = build('classroom', 'v1', credentials=creds)
    forms = build('forms', 'v1', credentials=creds)

    # Get our courses
    print("\nFetching courses...")
    courses_result = classroom.courses().list(teacherId='me', courseStates=['ACTIVE']).execute()
    courses = {c['name']: c for c in courses_result.get('courses', []) if c['name'] in TARGET_COURSES}
    print(f"Found {len(courses)} target courses")

    # Build student email -> name mapping from all courses
    print("\nBuilding student roster...")
    student_by_email = {}  # email -> {name, courses: []}

    for course_name, course in sorted(courses.items()):
        try:
            students_result = classroom.courses().students().list(courseId=course['id']).execute()
            for student in students_result.get('students', []):
                profile = student.get('profile', {})
                email = profile.get('emailAddress', '')
                name = profile.get('name', {}).get('fullName', 'Unknown')
                if email:
                    if email not in student_by_email:
                        student_by_email[email] = {'name': name, 'courses': []}
                    student_by_email[email]['courses'].append(course_name)
        except HttpError:
            pass

    print(f"Found {len(student_by_email)} students with emails")

    # Find all forms attached to assignments
    print("\nFinding quiz forms...")
    form_ids = {}  # form_id -> assignment_title

    for course_name, course in courses.items():
        try:
            coursework_result = classroom.courses().courseWork().list(courseId=course['id']).execute()
            for cw in coursework_result.get('courseWork', []):
                for material in cw.get('materials', []):
                    if 'form' in material:
                        form_url = material['form'].get('formUrl', '')
                        if '/d/' in form_url:
                            form_id = form_url.split('/d/')[1].split('/')[0]
                            form_ids[form_id] = cw['title']
                    elif 'link' in material:
                        link_url = material['link'].get('url', '')
                        if 'forms.google.com' in link_url and '/d/' in link_url:
                            form_id = link_url.split('/d/')[1].split('/')[0]
                            form_ids[form_id] = cw['title']
        except HttpError:
            continue

    print(f"Found {len(form_ids)} quiz forms")

    # Get Classroom submission states for each assignment
    print("\nChecking Classroom submission states...")
    classroom_states = {}  # (assignment_title, email) -> state

    for course_name, course in courses.items():
        try:
            coursework_result = classroom.courses().courseWork().list(courseId=course['id']).execute()
            students_result = classroom.courses().students().list(courseId=course['id']).execute()

            # Build user_id -> email lookup for this course
            user_emails = {}
            for student in students_result.get('students', []):
                user_id = student['userId']
                email = student.get('profile', {}).get('emailAddress', '')
                user_emails[user_id] = email

            for cw in coursework_result.get('courseWork', []):
                title = cw['title']
                try:
                    submissions_result = classroom.courses().courseWork().studentSubmissions().list(
                        courseId=course['id'],
                        courseWorkId=cw['id']
                    ).execute()

                    for sub in submissions_result.get('studentSubmissions', []):
                        user_id = sub.get('userId', '')
                        state = sub.get('state', 'UNKNOWN')
                        email = user_emails.get(user_id, '')
                        if email:
                            classroom_states[(title, email)] = state
                except HttpError:
                    pass
        except HttpError:
            continue

    # Check form responses
    print("\nChecking form responses...")
    completions = []  # [{assignment, email, name, score, total, turned_in, timestamp}]

    for form_id, assignment_title in sorted(form_ids.items(), key=lambda x: x[1]):
        try:
            # Get form info for total points
            form_info = forms.forms().get(formId=form_id).execute()

            # Calculate total possible points
            total_possible = 0
            for item in form_info.get('items', []):
                question_item = item.get('questionItem', {})
                question = question_item.get('question', {})
                grading = question.get('grading', {})
                points = grading.get('pointValue', 0)
                total_possible += points

            # Get responses
            responses_result = forms.forms().responses().list(formId=form_id).execute()
            responses = responses_result.get('responses', [])

            for resp in responses:
                respondent_email = resp.get('respondentEmail', '')
                total_score = resp.get('totalScore')
                timestamp = resp.get('lastSubmittedTime', resp.get('createTime', ''))

                # Look up student name
                student_info = student_by_email.get(respondent_email, {'name': 'Unknown', 'courses': []})
                name = student_info['name']

                # Check Classroom state
                classroom_state = classroom_states.get((assignment_title, respondent_email), 'UNKNOWN')
                turned_in = classroom_state in ['TURNED_IN', 'RETURNED']

                completions.append({
                    'assignment': assignment_title,
                    'email': respondent_email if respondent_email else '(no email collected)',
                    'name': name,
                    'score': total_score,
                    'total': total_possible,
                    'turned_in': turned_in,
                    'classroom_state': classroom_state,
                    'timestamp': timestamp,
                })

        except HttpError as e:
            print(f"  Error checking {assignment_title}: {e}")

    # Print summary report
    print("\n" + "=" * 70)
    print("QUIZ COMPLETION SUMMARY")
    print("=" * 70)

    if not completions:
        print("\nNo quiz completions found.")
    else:
        # Group by assignment
        by_assignment = defaultdict(list)
        for comp in completions:
            by_assignment[comp['assignment']].append(comp)

        total_completions = 0
        turned_in_count = 0
        not_turned_in_count = 0

        for assignment in sorted(by_assignment.keys()):
            responses = by_assignment[assignment]
            print(f"\n{assignment}")
            print("-" * 60)

            for resp in sorted(responses, key=lambda x: x['name']):
                name = resp['name']
                email = resp['email']
                score = resp['score']
                total = resp['total']
                turned_in = resp['turned_in']
                state = resp['classroom_state']
                timestamp = resp['timestamp'][:16].replace('T', ' ') if resp['timestamp'] else ''

                total_completions += 1
                if turned_in:
                    turned_in_count += 1
                    status = "[TURNED IN]"
                else:
                    not_turned_in_count += 1
                    status = "[NOT TURNED IN]"

                if score is not None and total > 0:
                    pct = (score / total) * 100
                    print(f"  {status} {name}")
                    print(f"           Email: {email}")
                    print(f"           Score: {score}/{total} ({pct:.0f}%)")
                    print(f"           Submitted: {timestamp}")
                    print()
                else:
                    print(f"  {status} {name}")
                    print(f"           Email: {email}")
                    print(f"           Score: (not recorded)")
                    print()

        print("=" * 70)
        print("TOTALS")
        print("=" * 70)
        print(f"  Total quiz completions: {total_completions}")
        print(f"  Turned in via Classroom: {turned_in_count}")
        print(f"  NOT turned in (form only): {not_turned_in_count}")

        if not_turned_in_count > 0:
            print(f"\n  ACTION NEEDED: {not_turned_in_count} students completed quizzes but didn't turn in!")
            print("  Run the grade sync script to auto-turn-in and enter grades.")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
