#!/usr/bin/env python3
"""
quiz.py - Create Google Form quizzes from markdown

Usage:
    python quiz.py <quiz.md>
    python quiz.py lessons/01-james-baldwin-civil-rights/quiz.md

Quiz markdown format:
    # Quiz Title

    ## Question 1
    Question text here?

    A. Option one
    B. Option two (correct)
    C. Option three
    D. Option four

Mark correct answers with (correct) tag.
"""

import sys
import pickle
import re
from pathlib import Path
from typing import Optional

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file'
]

TOKEN_PATH = Path('token_forms.pickle')
CREDS_PATH = Path('credentials.json')


class QuizError(Exception):
    """Quiz parsing or creation error."""
    pass


def verify_quiz(content: str) -> tuple[bool, list[str]]:
    """
    Verify quiz markdown format.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Check for title
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if not title_match:
        errors.append("Missing quiz title (# Title)")
    else:
        title = title_match.group(1).strip()
        if not title or title.lower() in ['quiz', 'untitled', 'untitled quiz']:
            errors.append(f"Quiz needs a descriptive title, not '{title}'")

    # Check for questions
    questions = re.findall(r'^## Question \d+', content, re.MULTILINE)
    if not questions:
        errors.append("No questions found (## Question N)")
    elif len(questions) < 3:
        errors.append(f"Only {len(questions)} questions found (recommend at least 5)")

    # Check each question has options and a correct answer
    parts = re.split(r'^## Question \d+\s*$', content, flags=re.MULTILINE)

    for i, part in enumerate(parts[1:], 1):
        if '**Answer Key' in part:
            break

        options = re.findall(r'^[A-D]\.', part, re.MULTILINE)
        if len(options) < 2:
            errors.append(f"Question {i}: Less than 2 options")

        if '(correct)' not in part:
            errors.append(f"Question {i}: No correct answer marked")

        correct_count = part.count('(correct)')
        if correct_count > 1:
            errors.append(f"Question {i}: Multiple answers marked correct ({correct_count})")

    return len(errors) == 0, errors


def parse_quiz(content: str) -> tuple[str, list[dict]]:
    """
    Parse quiz markdown into title and structured questions.
    Returns (title, questions_list).
    """
    # Extract title
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Untitled Quiz"

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


def get_credentials() -> Optional[Credentials]:
    """Get or refresh Google API credentials."""
    if not GOOGLE_API_AVAILABLE:
        raise QuizError("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")

    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_PATH.exists():
                raise QuizError(f"Credentials file not found: {CREDS_PATH}\nDownload from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def create_google_form(title: str, questions: list[dict]) -> tuple[str, str]:
    """
    Create Google Form quiz.
    Returns (edit_url, student_url).
    """
    print("Authenticating with Google...")
    creds = get_credentials()

    forms_service = build('forms', 'v1', credentials=creds)

    print(f"Creating form: {title}")
    form = forms_service.forms().create(body={
        'info': {
            'title': title,
            'documentTitle': title
        }
    }).execute()
    form_id = form['formId']

    # Set form title and enable quiz mode
    print("Configuring quiz settings...")
    forms_service.forms().batchUpdate(
        formId=form_id,
        body={
            'requests': [
                {
                    'updateFormInfo': {
                        'info': {'title': title},
                        'updateMask': 'title'
                    }
                },
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
    print(f"Adding {len(questions)} questions...")
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

    form = forms_service.forms().get(formId=form_id).execute()
    student_url = form.get('responderUri', f"https://docs.google.com/forms/d/{form_id}/viewform")
    edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"

    return edit_url, student_url


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    quiz_path = Path(sys.argv[1])

    # Verify file exists
    if not quiz_path.exists():
        print(f"ERROR: File not found: {quiz_path}")
        sys.exit(1)

    if not quiz_path.suffix == '.md':
        print(f"WARNING: Expected .md file, got {quiz_path.suffix}")

    content = quiz_path.read_text(encoding='utf-8')

    # Verify quiz format
    print(f"Verifying: {quiz_path.name}")
    is_valid, errors = verify_quiz(content)

    if not is_valid:
        print("\nVERIFICATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("Verification passed.")

    # Parse quiz
    title, questions = parse_quiz(content)
    print(f"Parsed {len(questions)} questions.")

    # Create form
    edit_url, student_url = create_google_form(title, questions)

    print(f"\n{'='*60}")
    print("QUIZ CREATED SUCCESSFULLY!")
    print('='*60)
    print(f"\nEdit:    {edit_url}")
    print(f"Student: {student_url}\n")


if __name__ == '__main__':
    main()
