#!/usr/bin/env python3
"""
send_classroom_reminders.py - Send email reminders to students who haven't accepted Google Classroom invites

Sends personalized emails via Gmail API:
- Students who haven't accepted ANY class: general reminder
- Multi-period students who accepted some but not all: specific message about which periods

Usage:
    python send_classroom_reminders.py              # Dry run (shows what would be sent)
    python send_classroom_reminders.py --send       # Actually send emails
    python send_classroom_reminders.py --send -y    # Send without confirmation

Requirements:
    pip install google-auth-oauthlib google-api-python-client

Security:
    - Student emails are only held in memory
    - No PII written to disk
"""

import argparse
import base64
import sys
import time
from collections import defaultdict
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes for Classroom (read) and Gmail (send)
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.profile.emails',
    'https://www.googleapis.com/auth/gmail.send',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_reminders.json'

# Rate limiting
SEND_DELAY = 1.0  # seconds between emails to avoid rate limits

# Teacher info
TEACHER_NAME = "Mr. Edwards"
TEACHER_EMAIL = "brian.edwards@wacoisd.org"


def get_credentials():
    """Get valid user credentials for Classroom and Gmail APIs."""
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
            print("NOTE: You'll need to grant Gmail send permission.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_PATH}")

    return creds


def get_active_courses(classroom_service):
    """Get all active courses where user is a teacher."""
    courses = []
    page_token = None

    while True:
        response = classroom_service.courses().list(
            teacherId='me',
            courseStates=['ACTIVE'],
            pageToken=page_token
        ).execute()

        courses.extend(response.get('courses', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return sorted(courses, key=lambda c: c['name'])


def get_students_with_status(classroom_service, courses):
    """
    Get all students and their acceptance status per course.

    Returns:
        dict: user_id -> {
            'name': str,
            'email': str or None,
            'courses': {course_id: {'name': str, 'accepted': bool}}
        }
    """
    students = {}

    for course in courses:
        course_id = course['id']
        course_name = course['name']
        print(f"  Checking {course_name}...")

        page_token = None
        while True:
            try:
                response = classroom_service.courses().students().list(
                    courseId=course_id,
                    pageToken=page_token
                ).execute()

                for student in response.get('students', []):
                    user_id = student['userId']
                    profile = student.get('profile', {})
                    name = profile.get('name', {}).get('fullName', f'User {user_id}')
                    email = profile.get('emailAddress')

                    # Check if student has accepted (has email visible = accepted)
                    has_accepted = bool(email)

                    if user_id not in students:
                        students[user_id] = {
                            'name': name,
                            'email': email,
                            'courses': {}
                        }

                    # Update email if we found one (student accepted in another class)
                    if email and not students[user_id]['email']:
                        students[user_id]['email'] = email

                    students[user_id]['courses'][course_id] = {
                        'name': course_name,
                        'accepted': has_accepted
                    }

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            except HttpError as e:
                print(f"    Error: {e}")
                break

    return students


def categorize_students(students):
    """
    Categorize students by their acceptance status.

    Returns:
        tuple: (no_classes_accepted, some_classes_accepted, all_accepted)

        Each is a list of:
        {
            'user_id': str,
            'name': str,
            'email': str or None,
            'accepted_courses': [str],  # course names
            'not_accepted_courses': [str]  # course names
        }
    """
    no_classes = []
    some_classes = []
    all_accepted = []

    for user_id, data in students.items():
        accepted = [c['name'] for c in data['courses'].values() if c['accepted']]
        not_accepted = [c['name'] for c in data['courses'].values() if not c['accepted']]

        student_info = {
            'user_id': user_id,
            'name': data['name'],
            'email': data['email'],
            'accepted_courses': sorted(accepted),
            'not_accepted_courses': sorted(not_accepted)
        }

        if len(not_accepted) == 0:
            all_accepted.append(student_info)
        elif len(accepted) == 0:
            no_classes.append(student_info)
        else:
            some_classes.append(student_info)

    # Sort by name
    no_classes.sort(key=lambda s: s['name'])
    some_classes.sort(key=lambda s: s['name'])
    all_accepted.sort(key=lambda s: s['name'])

    return no_classes, some_classes, all_accepted


def create_email_no_classes(student_name, courses):
    """Create email for student who hasn't accepted any classes."""
    course_list = '\n'.join(f"  - {c}" for c in courses)

    subject = "Action Required: Accept Your Google Classroom Invites"

    body = f"""Hi {student_name.split()[0]},

You have Google Classroom invitations waiting for you. Please accept them as soon as possible so you can access class materials and assignments.

Classes to accept:
{course_list}

How to accept:
1. Open Google Classroom (classroom.google.com) on your Chromebook
2. Make sure you're logged in with your school account
3. Click "Accept" on each class invitation

If you have any questions, let me know.

{TEACHER_NAME}
{TEACHER_EMAIL}
"""
    return subject, body


def create_email_some_classes(student_name, accepted, not_accepted):
    """Create email for multi-period student who accepted some but not all."""
    not_accepted_list = '\n'.join(f"  - {c}" for c in not_accepted)
    accepted_list = ', '.join(accepted)

    subject = "Quick Fix Needed: Accept Your Other Class Period(s)"

    body = f"""Hi {student_name.split()[0]},

You have me for multiple class periods. I see you've accepted the invite for {accepted_list} - thank you!

However, you still need to accept the invite for:
{not_accepted_list}

Please open Google Classroom and accept these remaining invitations so you can see all your assignments.

How to accept:
1. Open Google Classroom (classroom.google.com) on your Chromebook
2. Look for the pending invitations at the top
3. Click "Accept" on each one

Thanks!

{TEACHER_NAME}
{TEACHER_EMAIL}
"""
    return subject, body


def send_email(gmail_service, to_email, subject, body, dry_run=True):
    """Send an email via Gmail API."""
    message = MIMEText(body)
    message['to'] = to_email
    message['from'] = TEACHER_EMAIL
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    if dry_run:
        return True, "DRY RUN"

    try:
        gmail_service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        return True, "SENT"
    except HttpError as e:
        return False, f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Send email reminders to students who haven\'t accepted Google Classroom invites.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python send_classroom_reminders.py              # Preview emails (dry run)
  python send_classroom_reminders.py --send       # Actually send emails
  python send_classroom_reminders.py --send -y    # Send without confirmation
        """
    )
    parser.add_argument(
        '--send',
        action='store_true',
        help='Actually send emails (default is dry-run mode)'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompt when using --send'
    )
    args = parser.parse_args()

    dry_run = not args.send

    print("=" * 60)
    if dry_run:
        print("DRY RUN MODE - No emails will be sent")
        print("Use --send to actually send emails")
    else:
        print("SEND MODE - Emails WILL be sent")
    print("=" * 60)

    # Authenticate
    print("\nAuthenticating...")
    creds = get_credentials()
    classroom_service = build('classroom', 'v1', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)

    # Get courses
    print("\nFetching courses...")
    courses = get_active_courses(classroom_service)
    print(f"  Found {len(courses)} active courses")

    # Get student status
    print("\nChecking student acceptance status...")
    students = get_students_with_status(classroom_service, courses)

    # Categorize
    no_classes, some_classes, all_accepted = categorize_students(students)

    print(f"\n  Students who accepted ALL classes: {len(all_accepted)}")
    print(f"  Students who accepted SOME classes: {len(some_classes)}")
    print(f"  Students who accepted NO classes: {len(no_classes)}")

    # Students to email
    to_email = []

    # Add students with no accepted classes
    for student in no_classes:
        if student['email']:
            subject, body = create_email_no_classes(
                student['name'],
                student['not_accepted_courses']
            )
            to_email.append({
                'student': student,
                'subject': subject,
                'body': body,
                'type': 'no_classes'
            })

    # Add multi-period students who accepted some but not all
    for student in some_classes:
        if student['email']:
            subject, body = create_email_some_classes(
                student['name'],
                student['accepted_courses'],
                student['not_accepted_courses']
            )
            to_email.append({
                'student': student,
                'subject': subject,
                'body': body,
                'type': 'some_classes'
            })

    # Count students without email (can't contact)
    no_email_count = sum(1 for s in no_classes + some_classes if not s['email'])

    print(f"\n  Emails to send: {len(to_email)}")
    print(f"  Students with no email (can't contact): {no_email_count}")

    if not to_email:
        print("\nNo emails to send!")
        return

    # Confirmation
    if args.send and not args.yes:
        print(f"\nAbout to send {len(to_email)} emails.")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # Send emails
    print("\n" + "=" * 60)
    print("SENDING EMAILS")
    print("=" * 60)

    sent = 0
    errors = 0

    for i, email_data in enumerate(to_email):
        student = email_data['student']
        print(f"\n[{i+1}/{len(to_email)}] {student['name']} ({email_data['type']})")
        print(f"  To: {student['email']}")
        print(f"  Subject: {email_data['subject']}")

        if dry_run:
            print("  Preview:")
            for line in email_data['body'].split('\n')[:5]:
                print(f"    {line}")
            print("    ...")

        success, status = send_email(
            gmail_service,
            student['email'],
            email_data['subject'],
            email_data['body'],
            dry_run
        )

        print(f"  Status: {status}")

        if success:
            sent += 1
        else:
            errors += 1

        if not dry_run:
            time.sleep(SEND_DELAY)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Emails sent: {sent}")
    if errors > 0:
        print(f"  Errors: {errors}")
    if no_email_count > 0:
        print(f"  Students without email (couldn't contact): {no_email_count}")

    if dry_run:
        print("\nThis was a DRY RUN. No emails were sent.")
        print("Run with --send to actually send emails.")


if __name__ == '__main__':
    main()
