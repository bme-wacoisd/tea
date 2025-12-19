#!/usr/bin/env python3
"""
create_assignments.py - Create Google Classroom assignments via API

This script creates assignments for lessons via the Classroom API, ensuring
they have associatedWithDeveloper: true for full API control over grades.

Usage:
    python create_assignments.py --lesson 08-every-kid-needs-champion [--dry-run]
    python create_assignments.py --all [--dry-run]

The script will:
1. Read lesson content from lessons/<lesson-name>/
2. Create a Google Form quiz from quiz.md
3. Create a Classroom assignment with the reading + worksheet + quiz
4. Post to all period 1-8 courses (not Lovelace classes)
5. Use past scheduledTime to avoid sending notifications

Requirements:
    pip install google-api-python-client google-auth-oauthlib
"""

import argparse
import pickle
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_create_assignments.pickle'
LESSONS_DIR = PROJECT_ROOT / 'lessons'

# Scopes needed for creating assignments and forms
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file',
]

# Course IDs for periods 1-8 (excluding Lovelace classes)
TARGET_COURSES = [
    {"id": "835400632498", "name": "1 Instructional Practices & Practicum"},
    {"id": "835399786685", "name": "2 Communications and Technology"},
    {"id": "835400285918", "name": "3 Instructional Practices & Practicum"},
    {"id": "835399531473", "name": "4 Communications and Technology"},
    {"id": "835400459498", "name": "5 Instructional Practices & Practicum"},
    {"id": "835399949498", "name": "6 Communications and Technology"},
    {"id": "835750566498", "name": "7 Instructional Practices & Practicum"},
    {"id": "835749845545", "name": "8 Communications and Technology"},
]


def get_credentials():
    """Get valid user credentials."""
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


def parse_quiz_md(quiz_path: Path) -> tuple[str, list[dict]]:
    """Parse quiz.md into title and questions."""
    content = quiz_path.read_text(encoding='utf-8')

    # Extract title
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Quiz"

    questions = []
    parts = re.split(r'^## Question \d+\s*$', content, flags=re.MULTILINE)

    for part in parts[1:]:
        lines = [l.strip() for l in part.strip().split('\n')
                 if l.strip() and l.strip() != '---']

        if not lines:
            continue

        # First line is the question
        question_text = lines[0]

        # Stop at answer key
        if question_text.startswith('**Answer Key'):
            break

        options = []
        correct_index = 0

        for line in lines[1:]:
            match = re.match(r'^([A-D])\.\s*(.+)$', line)
            if match:
                _, text = match.groups()
                is_correct = '(correct)' in text
                clean_text = re.sub(r'\s*\(correct\)\s*', '', text).strip()
                options.append(clean_text)
                if is_correct:
                    correct_index = len(options) - 1

        if question_text and options:
            questions.append({
                'question': question_text,
                'options': options,
                'correct_index': correct_index
            })

    return title, questions


def create_google_form(forms_service, title: str, questions: list[dict]) -> tuple[str, str]:
    """Create a Google Form quiz. Returns (form_id, responder_url)."""
    print(f"    Creating form: {title}")

    # Create form
    form = forms_service.forms().create(body={
        'info': {
            'title': title,
            'documentTitle': title
        }
    }).execute()
    form_id = form['formId']

    # Enable quiz mode
    forms_service.forms().batchUpdate(
        formId=form_id,
        body={
            'requests': [
                {
                    'updateSettings': {
                        'settings': {
                            'quizSettings': {'isQuiz': True}
                        },
                        'updateMask': 'quizSettings.isQuiz'
                    }
                }
            ]
        }
    ).execute()

    # Add questions
    requests = []
    for idx, q in enumerate(questions):
        question_item = {
            'createItem': {
                'item': {
                    'title': q['question'],
                    'questionItem': {
                        'question': {
                            'required': True,
                            'grading': {
                                'pointValue': 1,
                                'correctAnswers': {
                                    'answers': [{'value': q['options'][q['correct_index']]}]
                                }
                            },
                            'choiceQuestion': {
                                'type': 'RADIO',
                                'options': [{'value': opt} for opt in q['options']],
                                'shuffle': True
                            }
                        }
                    }
                },
                'location': {'index': idx}
            }
        }
        requests.append(question_item)

    if requests:
        forms_service.forms().batchUpdate(
            formId=form_id,
            body={'requests': requests}
        ).execute()

    # Get responder URL
    form = forms_service.forms().get(formId=form_id).execute()
    responder_url = form.get('responderUri', f"https://docs.google.com/forms/d/{form_id}/viewform")

    print(f"      Form ID: {form_id}")
    return form_id, responder_url


def create_assignment_description(lesson_dir: Path) -> str:
    """Build assignment description from lesson files."""
    parts = []

    # Add reading
    reading_path = lesson_dir / 'reading.md'
    if reading_path.exists():
        reading = reading_path.read_text(encoding='utf-8')
        parts.append(reading)

    # Add worksheet
    worksheet_path = lesson_dir / 'worksheet.md'
    if worksheet_path.exists():
        worksheet = worksheet_path.read_text(encoding='utf-8')
        parts.append("\n\n" + worksheet)

    return '\n'.join(parts)


def get_lesson_title(lesson_dir: Path) -> str:
    """Extract lesson title from reading.md or lesson-plan.md."""
    # Try reading.md first
    reading_path = lesson_dir / 'reading.md'
    if reading_path.exists():
        content = reading_path.read_text(encoding='utf-8')
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

    # Fall back to lesson-plan.md
    plan_path = lesson_dir / 'lesson-plan.md'
    if plan_path.exists():
        content = plan_path.read_text(encoding='utf-8')
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

    # Fall back to directory name
    return lesson_dir.name.replace('-', ' ').title()


def create_assignment(classroom_service, course_id: str, title: str, description: str,
                      form_id: str, max_points: int = 100, dry_run: bool = False) -> dict:
    """Create a Classroom assignment with the quiz attached."""

    # Use a past scheduled time to avoid notifications
    # This tells Classroom "this was supposed to be posted in the past"
    past_time = "2020-01-01T00:00:00Z"

    # Due date far in the future
    due_date = {
        "year": 2026,
        "month": 1,
        "day": 31
    }
    due_time = {
        "hours": 5,
        "minutes": 59
    }

    body = {
        'title': title,
        'description': description,
        'workType': 'ASSIGNMENT',
        'state': 'PUBLISHED',
        'scheduledTime': past_time,  # Prevents notifications
        'maxPoints': max_points,
        'dueDate': due_date,
        'dueTime': due_time,
        'materials': [
            {
                'form': {
                    'formUrl': f"https://docs.google.com/forms/d/{form_id}/edit"
                }
            }
        ]
    }

    if dry_run:
        return {'id': 'DRY_RUN', 'title': title}

    result = classroom_service.courses().courseWork().create(
        courseId=course_id,
        body=body
    ).execute()

    return result


def process_lesson(lesson_name: str, classroom_service, forms_service, dry_run: bool):
    """Process a single lesson and create assignments in all courses."""
    lesson_dir = LESSONS_DIR / lesson_name

    if not lesson_dir.exists():
        print(f"ERROR: Lesson not found: {lesson_dir}")
        return False

    print(f"\n{'='*70}")
    print(f"LESSON: {lesson_name}")
    print(f"{'='*70}")

    # Get lesson title
    title = get_lesson_title(lesson_dir)
    print(f"  Title: {title}")

    # Parse quiz
    quiz_path = lesson_dir / 'quiz.md'
    if not quiz_path.exists():
        print(f"  ERROR: No quiz.md found")
        return False

    quiz_title, questions = parse_quiz_md(quiz_path)
    print(f"  Quiz: {len(questions)} questions")

    # Build description
    description = create_assignment_description(lesson_dir)
    print(f"  Description: {len(description)} characters")

    # Create form (one form shared across all courses)
    if dry_run:
        print(f"  [DRY RUN] Would create form: {quiz_title}")
        form_id = "DRY_RUN_FORM_ID"
    else:
        form_id, responder_url = create_google_form(forms_service, quiz_title, questions)

    # Create assignment in each course
    print(f"\n  Creating assignments in {len(TARGET_COURSES)} courses:")

    for course in TARGET_COURSES:
        course_id = course['id']
        course_name = course['name']

        if dry_run:
            print(f"    [DRY RUN] Would create in: {course_name}")
        else:
            try:
                result = create_assignment(
                    classroom_service, course_id, title, description,
                    form_id, max_points=100, dry_run=False
                )
                print(f"    Created in {course_name}: {result['id']}")
                print(f"      associatedWithDeveloper: {result.get('associatedWithDeveloper', 'NOT SET')}")
            except HttpError as e:
                print(f"    ERROR in {course_name}: {e.resp.status}")

    return True


def list_lessons():
    """List all available lessons."""
    print("\nAvailable lessons:")
    for lesson_dir in sorted(LESSONS_DIR.iterdir()):
        if lesson_dir.is_dir() and not lesson_dir.name.startswith('.'):
            quiz_exists = (lesson_dir / 'quiz.md').exists()
            status = "[OK]" if quiz_exists else "[NO QUIZ]"
            print(f"  {lesson_dir.name} {status}")


def main():
    parser = argparse.ArgumentParser(
        description='Create Google Classroom assignments from lessons',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--lesson', '-l', help='Lesson folder name (e.g., 08-every-kid-needs-champion)')
    parser.add_argument('--all', action='store_true', help='Process all lessons')
    parser.add_argument('--list', action='store_true', help='List available lessons')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    args = parser.parse_args()

    if args.list:
        list_lessons()
        return

    if not args.lesson and not args.all:
        parser.print_help()
        print("\n" + "="*70)
        print("ERROR: Specify --lesson LESSON_NAME or --all")
        print("="*70)
        list_lessons()
        return

    # Authenticate
    print("Authenticating...")
    creds = get_credentials()
    if not creds:
        print("Authentication failed")
        sys.exit(1)

    classroom_service = build('classroom', 'v1', credentials=creds)
    forms_service = build('forms', 'v1', credentials=creds)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***")

    if args.all:
        # Process all lessons
        lessons = sorted([d.name for d in LESSONS_DIR.iterdir()
                          if d.is_dir() and not d.name.startswith('.') and d.name != 'templates'])
        print(f"\nProcessing {len(lessons)} lessons...")
        for lesson in lessons:
            process_lesson(lesson, classroom_service, forms_service, args.dry_run)
    else:
        # Process single lesson
        process_lesson(args.lesson, classroom_service, forms_service, args.dry_run)

    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()
