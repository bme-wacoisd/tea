#!/usr/bin/env python3
"""
create_lesson_assignment.py - Create Google Classroom assignments from lesson folders

Creates Google Form (with anti-cheat settings), Google Slides, and distributes
a Classroom assignment to all 8 periods, avoiding duplicates for multi-period students.

Usage:
    python scripts/create_lesson_assignment.py lessons/08-every-kid-needs-champion/
    python scripts/create_lesson_assignment.py lessons/08-every-kid-needs-champion/ --dry-run

Features:
    - Creates Form with anti-cheat: shuffle questions, no answers shown, require login
    - Enables email collection on forms (emailCollectionType: VERIFIED) for student identification
    - Creates Slides presentation from YAML
    - Distributes assignment across 8 periods with round-robin for multi-period students
    - Uses associatedWithDeveloper=true for API grading
    - API-created assignments do NOT send email notifications (only web UI does)

Requirements:
    pip install google-auth-oauthlib google-api-python-client pyyaml
"""

import argparse
import hashlib
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import yaml

# Import tracker for persistent storage
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sheets_tracker import GYOTracker

# ============================================================================
# CONFIGURATION
# ============================================================================

# The 8 courses we manage
COURSES = {
    "1 Instructional Practices & Practicum": None,  # Course IDs populated at runtime
    "2 Communications and Technology": None,
    "3 Instructional Practices & Practicum": None,
    "4 Communications and Technology": None,
    "5 Instructional Practices & Practicum": None,
    "6 Communications and Technology": None,
    "7 Instructional Practices & Practicum": None,
    "8 Communications and Technology": None,
}

# OAuth scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive',
]

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_assignment.json'

# API rate limiting
API_DELAY = 0.1
MAX_RETRIES = 3
RETRY_DELAY = 2

# Default due date: Feb 13, 2026 at 8:00 AM Central (Waco, TX)
DEFAULT_DUE_DATE = {
    'year': 2026,
    'month': 2,
    'day': 13
}
DEFAULT_DUE_TIME = {
    'hours': 8,
    'minutes': 0
}


# ============================================================================
# AUTHENTICATION
# ============================================================================

def get_credentials():
    """Get valid user credentials from storage or initiate OAuth flow."""
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

        # Save credentials
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_PATH}")

    return creds


def api_call_with_retry(func, *args, **kwargs):
    """Execute an API call with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(API_DELAY)
            return func(*args, **kwargs).execute()
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    print(f"    API error, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
            raise
    return None


# ============================================================================
# QUIZ PARSING AND FORM CREATION
# ============================================================================

def parse_quiz(content: str) -> tuple[str, list[dict]]:
    """Parse quiz markdown into title and questions."""
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

        question_text = lines[0]
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


def create_google_form(forms_service, drive_service, title: str, questions: list[dict], dry_run: bool = False) -> tuple[str, str]:
    """Create Google Form with anti-cheat settings and share with wacoisd.org."""
    if dry_run:
        print(f"  [DRY RUN] Would create form: {title}")
        print(f"  [DRY RUN] With {len(questions)} questions")
        return "DRY_RUN_FORM_ID", "https://example.com/dry-run-form"

    print(f"  Creating form: {title}")
    form = forms_service.forms().create(body={
        'info': {
            'title': title,
            'documentTitle': title
        }
    }).execute()
    form_id = form['formId']

    # Configure quiz settings with anti-cheat
    print("  Configuring quiz settings (anti-cheat)...")
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
                            'quizSettings': {
                                'isQuiz': True
                            },
                            'emailCollectionType': 'VERIFIED'  # Collect respondent email for identification
                        },
                        'updateMask': 'quizSettings.isQuiz,emailCollectionType'
                    }
                }
            ]
        }
    ).execute()

    # Add questions with shuffled options
    print(f"  Adding {len(questions)} questions...")
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
                                'shuffle': True  # Anti-cheat: shuffle answer options
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

    # Share form with wacoisd.org domain
    print("  Sharing form with wacoisd.org...")
    try:
        drive_service.permissions().create(
            fileId=form_id,
            body={
                'type': 'domain',
                'role': 'reader',
                'domain': 'wacoisd.org'
            },
            fields='id'
        ).execute()
    except HttpError as e:
        print(f"    Warning: Could not share with domain: {e}")

    # Also share with 'anyone' for link sharing - helps Classroom fetch the title
    print("  Enabling link sharing (anyone with link)...")
    try:
        drive_service.permissions().create(
            fileId=form_id,
            body={
                'type': 'anyone',
                'role': 'reader'
            },
            fields='id'
        ).execute()
    except HttpError as e:
        print(f"    Warning: Could not enable link sharing: {e}")

    form = forms_service.forms().get(formId=form_id).execute()
    student_url = form.get('responderUri', f"https://docs.google.com/forms/d/{form_id}/viewform")

    return form_id, student_url


# ============================================================================
# SLIDES CREATION
# ============================================================================

def rgb_to_color(rgb_dict):
    """Convert {r, g, b} dict to Google Slides color format."""
    return {'red': rgb_dict['r'], 'green': rgb_dict['g'], 'blue': rgb_dict['b']}


def inch_to_emu(inches):
    """Convert inches to EMU."""
    return int(inches * 914400)


class SlideBuilder:
    """Builds Google Slides presentations from YAML config."""

    SLIDE_WIDTH = 10.0
    SLIDE_HEIGHT = 5.625

    def __init__(self, slides_service, drive_service, config, base_path):
        self.slides = slides_service
        self.drive = drive_service
        self.config = config
        self.base_path = Path(base_path)
        self.presentation_id = None
        self.counter = 0
        self.uploaded_images = {}

        theme = config.get('theme', {})
        self.colors = {
            'primary': rgb_to_color(theme.get('primary', {'r': 0.1, 'g': 0.2, 'b': 0.4})),
            'secondary': rgb_to_color(theme.get('secondary', {'r': 0.2, 'g': 0.6, 'b': 0.6})),
            'accent1': rgb_to_color(theme.get('accent1', {'r': 0.95, 'g': 0.75, 'b': 0.2})),
            'accent2': rgb_to_color(theme.get('accent2', {'r': 0.95, 'g': 0.4, 'b': 0.35})),
            'background': rgb_to_color(theme.get('background', {'r': 1.0, 'g': 0.98, 'b': 0.94})),
            'text': rgb_to_color(theme.get('text', {'r': 0.2, 'g': 0.2, 'b': 0.25})),
            'white': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
        }

    def make_id(self, suffix):
        return f'slide{self.counter}_{suffix}'

    def upload_image(self, image_key):
        if image_key in self.uploaded_images:
            return self.uploaded_images[image_key]

        images = self.config.get('images', {})
        if image_key not in images:
            return None

        image_path = self.base_path / images[image_key]
        if not image_path.exists():
            print(f"    WARNING: Image not found: {image_path}")
            return None

        print(f"    Uploading image: {image_path.name}")
        file_metadata = {'name': image_path.name}
        media = MediaFileUpload(str(image_path), mimetype='image/jpeg')
        file = self.drive.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        file_id = file.get('id')

        self.drive.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        url = f'https://drive.google.com/uc?id={file_id}'
        self.uploaded_images[image_key] = url
        return url

    def create_presentation(self):
        pres = self.slides.presentations().create(
            body={'title': self.config.get('title', 'Untitled Presentation')}
        ).execute()
        self.presentation_id = pres['presentationId']

        default_slide_id = pres['slides'][0]['objectId']
        self.slides.presentations().batchUpdate(
            presentationId=self.presentation_id,
            body={'requests': [{'deleteObject': {'objectId': default_slide_id}}]}
        ).execute()

        return self.presentation_id

    def create_slide(self):
        response = self.slides.presentations().batchUpdate(
            presentationId=self.presentation_id,
            body={'requests': [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'BLANK'}}}]}
        ).execute()
        return response['replies'][0]['createSlide']['objectId']

    def execute_requests(self, requests):
        if requests:
            self.slides.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={'requests': requests}
            ).execute()

    def add_shape(self, requests, slide_id, shape_id, shape_type, x, y, w, h, color=None):
        requests.append({
            'createShape': {
                'objectId': shape_id,
                'shapeType': shape_type,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': inch_to_emu(w), 'unit': 'EMU'},
                        'height': {'magnitude': inch_to_emu(h), 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1, 'scaleY': 1,
                        'translateX': inch_to_emu(x),
                        'translateY': inch_to_emu(y),
                        'unit': 'EMU'
                    }
                }
            }
        })
        if color:
            requests.append({
                'updateShapeProperties': {
                    'objectId': shape_id,
                    'shapeProperties': {
                        'shapeBackgroundFill': {'solidFill': {'color': {'rgbColor': color}}},
                        'outline': {'propertyState': 'NOT_RENDERED'}
                    },
                    'fields': 'shapeBackgroundFill,outline'
                }
            })

    def add_text(self, requests, shape_id, text, font_size=18, bold=False, color=None, alignment='START'):
        requests.append({
            'insertText': {'objectId': shape_id, 'text': text, 'insertionIndex': 0}
        })
        style = {'fontSize': {'magnitude': font_size, 'unit': 'PT'}, 'bold': bold}
        fields = 'fontSize,bold'
        if color:
            style['foregroundColor'] = {'opaqueColor': {'rgbColor': color}}
            fields += ',foregroundColor'
        requests.append({
            'updateTextStyle': {
                'objectId': shape_id, 'style': style,
                'textRange': {'type': 'ALL'}, 'fields': fields
            }
        })
        requests.append({
            'updateParagraphStyle': {
                'objectId': shape_id, 'style': {'alignment': alignment},
                'textRange': {'type': 'ALL'}, 'fields': 'alignment'
            }
        })

    def add_image(self, requests, slide_id, image_id, url, x, y, w, h, drop_shadow=True):
        """Add an image to a slide with optional drop shadow."""
        requests.append({
            'createImage': {
                'objectId': image_id,
                'url': url,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': inch_to_emu(w), 'unit': 'EMU'},
                        'height': {'magnitude': inch_to_emu(h), 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1, 'scaleY': 1,
                        'translateX': inch_to_emu(x),
                        'translateY': inch_to_emu(y),
                        'unit': 'EMU'
                    }
                }
            }
        })

        # Add drop shadow effect for professional look
        if drop_shadow:
            requests.append({
                'updateImageProperties': {
                    'objectId': image_id,
                    'imageProperties': {
                        'shadow': {
                            'type': 'OUTER',
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': inch_to_emu(0.05),  # Slight offset right
                                'translateY': inch_to_emu(0.05),  # Slight offset down
                                'unit': 'EMU'
                            },
                            'alignment': 'BOTTOM_RIGHT',
                            'blurRadius': {'magnitude': 8, 'unit': 'PT'},
                            'color': {
                                'rgbColor': {'red': 0.0, 'green': 0.0, 'blue': 0.0}
                            },
                            'alpha': 0.3,  # 30% opacity shadow
                            'rotateWithShape': True,
                            'propertyState': 'RENDERED'
                        }
                    },
                    'fields': 'shadow'
                }
            })

    def create_table(self, requests, slide_id, table_id, rows, cols, x, y, w, h):
        requests.append({
            'createTable': {
                'objectId': table_id,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': inch_to_emu(w), 'unit': 'EMU'},
                        'height': {'magnitude': inch_to_emu(h), 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1, 'scaleY': 1,
                        'translateX': inch_to_emu(x),
                        'translateY': inch_to_emu(y),
                        'unit': 'EMU'
                    }
                },
                'rows': rows, 'columns': cols
            }
        })

    def style_table_cell(self, requests, table_id, row, col, text=None, bg_color=None, text_color=None, bold=False, font_size=14):
        if text:
            requests.append({
                'insertText': {
                    'objectId': table_id,
                    'cellLocation': {'rowIndex': row, 'columnIndex': col},
                    'text': text, 'insertionIndex': 0
                }
            })
            style = {'fontSize': {'magnitude': font_size, 'unit': 'PT'}, 'bold': bold}
            if text_color:
                style['foregroundColor'] = {'opaqueColor': {'rgbColor': text_color}}
            requests.append({
                'updateTextStyle': {
                    'objectId': table_id,
                    'cellLocation': {'rowIndex': row, 'columnIndex': col},
                    'style': style,
                    'textRange': {'type': 'ALL'},
                    'fields': 'fontSize,bold,foregroundColor'
                }
            })
        if bg_color:
            requests.append({
                'updateTableCellProperties': {
                    'objectId': table_id,
                    'tableRange': {
                        'location': {'rowIndex': row, 'columnIndex': col},
                        'rowSpan': 1, 'columnSpan': 1
                    },
                    'tableCellProperties': {
                        'tableCellBackgroundFill': {'solidFill': {'color': {'rgbColor': bg_color}}}
                    },
                    'fields': 'tableCellBackgroundFill'
                }
            })

    def get_accent_color(self, accent_name):
        return self.colors.get(accent_name, self.colors['primary'])

    # Slide type builders (condensed for brevity - same logic as slides.py)
    def build_title_slide(self, slide_id, slide_config):
        requests = []
        title = self.config.get('title', 'Untitled')
        subtitle = self.config.get('subtitle', '')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 1.9, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('stripe'), 'RECTANGLE', 0, 1.8, W, 0.1, self.colors['accent1'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.4, 0.4, W - 0.8, 1.2, None)
        self.add_text(requests, self.make_id('title'), title, font_size=40, bold=True, color=self.colors['white'], alignment='CENTER')
        if subtitle:
            self.add_shape(requests, slide_id, self.make_id('subtitle'), 'TEXT_BOX', 0.4, 2.4, W - 0.8, 0.6, None)
            self.add_text(requests, self.make_id('subtitle'), subtitle, font_size=22, color=self.colors['text'], alignment='CENTER')
        return requests

    def build_big_idea_slide(self, slide_id, slide_config):
        requests = []
        label = slide_config.get('label', 'THE BIG IDEA')
        main_text = slide_config.get('main_text', '')
        supporting = slide_config.get('supporting_text', '')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('bg'), 'RECTANGLE', 0, 0, W, H, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('accent'), 'RECTANGLE', 0, 0, 0.2, H, self.colors['accent1'])
        self.add_shape(requests, slide_id, self.make_id('label'), 'TEXT_BOX', 0.6, 0.3, 8, 0.6, None)
        self.add_text(requests, self.make_id('label'), label, font_size=18, bold=True, color=self.colors['accent1'])
        self.add_shape(requests, slide_id, self.make_id('main'), 'TEXT_BOX', 0.6, 1.0, 8.5, 1.5, None)
        self.add_text(requests, self.make_id('main'), main_text, font_size=44, bold=True, color=self.colors['white'])
        if supporting:
            self.add_shape(requests, slide_id, self.make_id('support'), 'TEXT_BOX', 0.6, 3.0, 8, 1.5, None)
            self.add_text(requests, self.make_id('support'), supporting, font_size=22, color=self.colors['background'])
        return requests

    def build_image_bio_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        image_key = slide_config.get('image')
        description = slide_config.get('description', '')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 1.0, self.colors['secondary'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.4, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=28, bold=True, color=self.colors['white'])
        if image_key:
            image_url = self.upload_image(image_key)
            if image_url:
                self.add_image(requests, slide_id, self.make_id('photo'), image_url, 0.5, 1.3, 2.8, 3.2)
            else:
                self.add_shape(requests, slide_id, self.make_id('photo'), 'ROUND_RECTANGLE', 0.5, 1.3, 2.8, 3.2, self.colors['text'])
        self.add_shape(requests, slide_id, self.make_id('desc'), 'TEXT_BOX', 3.8, 1.4, 5.8, 3.5, None)
        self.add_text(requests, self.make_id('desc'), description, font_size=24, color=self.colors['text'])
        self.add_shape(requests, slide_id, self.make_id('bottom'), 'RECTANGLE', 0, H - 0.15, W, 0.15, self.colors['accent1'])
        return requests

    def build_quote_slide(self, slide_id, slide_config):
        requests = []
        quote = slide_config.get('quote', '')
        attribution = slide_config.get('attribution')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('bg'), 'RECTANGLE', 0, 0, W, H, self.colors['text'])
        self.add_shape(requests, slide_id, self.make_id('qmark'), 'TEXT_BOX', 0.3, 0.2, 1.5, 1.5, None)
        self.add_text(requests, self.make_id('qmark'), '"', font_size=100, bold=True, color=self.colors['accent1'])
        self.add_shape(requests, slide_id, self.make_id('quote'), 'TEXT_BOX', 1.0, 1.2, 8, 2.8, None)
        self.add_text(requests, self.make_id('quote'), quote, font_size=28, color=self.colors['white'])
        if attribution:
            self.add_shape(requests, slide_id, self.make_id('attr'), 'TEXT_BOX', 1.0, 4.3, 8, 0.8, None)
            self.add_text(requests, self.make_id('attr'), f'— {attribution}', font_size=18, color=self.colors['accent1'])
        return requests

    def build_table_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        headers = slide_config.get('headers', [])
        rows = slide_config.get('rows', [])
        accent = self.get_accent_color(slide_config.get('accent', 'secondary'))
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, accent)
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])
        num_rows = len(rows) + 1
        num_cols = len(headers)
        table_id = self.make_id('table')
        self.create_table(requests, slide_id, table_id, num_rows, num_cols, 0.3, 1.1, W - 0.6, H - 1.3)
        for col, header in enumerate(headers):
            self.style_table_cell(requests, table_id, 0, col, text=header, bg_color=accent, text_color=self.colors['white'], bold=True, font_size=12)
        for row_idx, row_data in enumerate(rows):
            bg = self.colors['background'] if row_idx % 2 == 0 else self.colors['white']
            for col_idx, cell_text in enumerate(row_data):
                self.style_table_cell(requests, table_id, row_idx + 1, col_idx, text=cell_text, bg_color=bg, text_color=self.colors['text'], font_size=11)
        return requests

    def build_comparison_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        left_header = slide_config.get('left_header', 'DO')
        right_header = slide_config.get('right_header', "DON'T")
        left_items = slide_config.get('left_items', [])
        right_items = slide_config.get('right_items', [])
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])
        col_width = (W - 0.8) / 2
        self.add_shape(requests, slide_id, self.make_id('left_hdr'), 'ROUND_RECTANGLE', 0.3, 1.1, col_width - 0.1, 0.5, self.colors['secondary'])
        self.add_text(requests, self.make_id('left_hdr'), left_header, font_size=16, bold=True, color=self.colors['white'], alignment='CENTER')
        self.add_shape(requests, slide_id, self.make_id('right_hdr'), 'ROUND_RECTANGLE', 0.3 + col_width + 0.2, 1.1, col_width - 0.1, 0.5, self.colors['accent2'])
        self.add_text(requests, self.make_id('right_hdr'), right_header, font_size=16, bold=True, color=self.colors['white'], alignment='CENTER')
        left_text = '\n'.join([f'✓  {item}' for item in left_items])
        self.add_shape(requests, slide_id, self.make_id('left_box'), 'TEXT_BOX', 0.4, 1.75, col_width - 0.2, H - 2.0, None)
        self.add_text(requests, self.make_id('left_box'), left_text, font_size=14, color=self.colors['text'])
        right_text = '\n'.join([f'✗  {item}' for item in right_items])
        self.add_shape(requests, slide_id, self.make_id('right_box'), 'TEXT_BOX', 0.4 + col_width + 0.2, 1.75, col_width - 0.2, H - 2.0, None)
        self.add_text(requests, self.make_id('right_box'), right_text, font_size=14, color=self.colors['text'])
        return requests

    def build_two_column_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        left_title = slide_config.get('left_title', '')
        right_title = slide_config.get('right_title', '')
        left_items = slide_config.get('left_items', [])
        right_items = slide_config.get('right_items', [])
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, self.colors['secondary'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])
        col_width = (W - 0.8) / 2
        self.add_shape(requests, slide_id, self.make_id('left_title'), 'TEXT_BOX', 0.3, 1.1, col_width, 0.5, None)
        self.add_text(requests, self.make_id('left_title'), left_title, font_size=16, bold=True, color=self.colors['primary'])
        left_text = '\n'.join([f'•  {b}' for b in left_items])
        self.add_shape(requests, slide_id, self.make_id('left_box'), 'TEXT_BOX', 0.3, 1.7, col_width, H - 2.0, None)
        self.add_text(requests, self.make_id('left_box'), left_text, font_size=14, color=self.colors['text'])
        self.add_shape(requests, slide_id, self.make_id('right_title'), 'TEXT_BOX', 0.3 + col_width + 0.2, 1.1, col_width, 0.5, None)
        self.add_text(requests, self.make_id('right_title'), right_title, font_size=16, bold=True, color=self.colors['primary'])
        right_text = '\n'.join([f'•  {b}' for b in right_items])
        self.add_shape(requests, slide_id, self.make_id('right_box'), 'TEXT_BOX', 0.3 + col_width + 0.2, 1.7, col_width, H - 2.0, None)
        self.add_text(requests, self.make_id('right_box'), right_text, font_size=14, color=self.colors['text'])
        return requests

    def build_bullets_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        items = slide_config.get('items', [])
        accent = self.get_accent_color(slide_config.get('accent', 'accent2'))
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, accent)
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])
        available_height = H - 1.3
        item_height = min(0.8, available_height / max(len(items), 1))
        y_pos = 1.15
        for i, bullet in enumerate(items):
            self.add_shape(requests, slide_id, self.make_id(f'dot_{i}'), 'ELLIPSE', 0.4, y_pos + 0.1, 0.25, 0.25, accent)
            self.add_shape(requests, slide_id, self.make_id(f'txt_{i}'), 'TEXT_BOX', 0.8, y_pos, W - 1.2, 0.6, None)
            self.add_text(requests, self.make_id(f'txt_{i}'), bullet, font_size=16, color=self.colors['text'])
            y_pos += item_height
        return requests

    def build_numbered_slide(self, slide_id, slide_config):
        requests = []
        title = slide_config.get('title', '')
        items = slide_config.get('items', [])
        colors_cycle = [self.colors['accent2'], self.colors['secondary'], self.colors['accent1'], self.colors['primary']]
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])
        available_height = H - 1.3
        item_height = min(0.9, available_height / max(len(items), 1))
        y_pos = 1.15
        for i, item in enumerate(items):
            self.add_shape(requests, slide_id, self.make_id(f'circle_{i}'), 'ELLIPSE', 0.3, y_pos, 0.5, 0.5, colors_cycle[i % len(colors_cycle)])
            self.add_shape(requests, slide_id, self.make_id(f'num_{i}'), 'TEXT_BOX', 0.3, y_pos + 0.08, 0.5, 0.4, None)
            self.add_text(requests, self.make_id(f'num_{i}'), str(i + 1), font_size=18, bold=True, color=self.colors['white'], alignment='CENTER')
            self.add_shape(requests, slide_id, self.make_id(f'item_{i}'), 'TEXT_BOX', 1.0, y_pos + 0.08, W - 1.4, 0.6, None)
            self.add_text(requests, self.make_id(f'item_{i}'), item, font_size=18, color=self.colors['text'])
            y_pos += item_height
        return requests

    def build_closing_slide(self, slide_id, slide_config):
        requests = []
        # Support both field name formats for backwards compatibility
        quote = slide_config.get('quote', '') or slide_config.get('main_text', '')
        attribution = slide_config.get('attribution', '') or slide_config.get('subtext', '')
        cta = slide_config.get('call_to_action', '')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT
        self.add_shape(requests, slide_id, self.make_id('bg'), 'RECTANGLE', 0, 0, W, H, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('quote'), 'TEXT_BOX', 1, 0.8, W - 2, 2.2, None)
        self.add_text(requests, self.make_id('quote'), f'"{quote}"', font_size=24, color=self.colors['white'], alignment='CENTER')
        if attribution:
            self.add_shape(requests, slide_id, self.make_id('attr'), 'TEXT_BOX', 1, 3.3, W - 2, 0.6, None)
            self.add_text(requests, self.make_id('attr'), f'— {attribution}', font_size=18, bold=True, color=self.colors['accent1'], alignment='CENTER')
        if cta:
            self.add_shape(requests, slide_id, self.make_id('cta'), 'TEXT_BOX', 1, 4.5, W - 2, 0.6, None)
            self.add_text(requests, self.make_id('cta'), cta, font_size=16, color=self.colors['background'], alignment='CENTER')
        return requests

    def build_slide(self, slide_config):
        slide_type = slide_config.get('type', 'bullets')
        slide_id = self.create_slide()
        self.counter += 1

        builders = {
            'title': self.build_title_slide,
            'big_idea': self.build_big_idea_slide,
            'image_bio': self.build_image_bio_slide,
            'quote': self.build_quote_slide,
            'table': self.build_table_slide,
            'comparison': self.build_comparison_slide,
            'two_column': self.build_two_column_slide,
            'bullets': self.build_bullets_slide,
            'numbered': self.build_numbered_slide,
            'closing': self.build_closing_slide,
        }

        builder = builders.get(slide_type, self.build_bullets_slide)
        requests = builder(slide_id, slide_config)
        self.execute_requests(requests)

        return slide_id

    def build_all(self):
        self.create_presentation()
        for slide_config in self.config.get('slides', []):
            slide_type = slide_config.get('type', 'unknown')
            print(f"    Creating slide: {slide_type}")
            self.build_slide(slide_config)
        return self.presentation_id


def create_google_slides(slides_service, drive_service, config: dict, base_path: Path, dry_run: bool = False) -> str:
    """Create Google Slides presentation from YAML config."""
    title = config.get('title', 'Untitled')
    num_slides = len(config.get('slides', []))

    if dry_run:
        print(f"  [DRY RUN] Would create slides: {title}")
        print(f"  [DRY RUN] With {num_slides} slides")
        return "DRY_RUN_SLIDES_ID"

    print(f"  Creating slides: {title}")
    builder = SlideBuilder(slides_service, drive_service, config, base_path)
    presentation_id = builder.build_all()
    return presentation_id


# ============================================================================
# CLASSROOM INTEGRATION
# ============================================================================

def get_courses(classroom_service):
    """Get all active courses and map to our expected names."""
    print("  Fetching courses...")
    all_courses = []
    page_token = None

    while True:
        response = api_call_with_retry(
            classroom_service.courses().list,
            teacherId='me',
            courseStates=['ACTIVE'],
            pageToken=page_token
        )
        if not response:
            break

        all_courses.extend(response.get('courses', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    # Map to our expected courses
    course_map = {}
    for course in all_courses:
        name = course['name']
        if name in COURSES:
            course_map[name] = course

    # Check we found all expected courses
    missing = set(COURSES.keys()) - set(course_map.keys())
    if missing:
        print(f"  ERROR: Missing courses: {missing}")
        sys.exit(1)

    print(f"  Found all {len(course_map)} expected courses")
    return course_map


def get_students_for_course(classroom_service, course_id):
    """Get all students enrolled in a course."""
    students = []
    page_token = None

    while True:
        try:
            response = api_call_with_retry(
                classroom_service.courses().students().list,
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


def find_multi_period_students(classroom_service, course_map, assignment_title):
    """Find students enrolled in multiple periods and determine assignment distribution.

    Uses assignment_title in the hash to achieve true round-robin distribution:
    different assignments will be distributed to different periods for each
    multi-period student.
    """
    print("  Analyzing student enrollments...")

    # Map student ID -> list of course names they're in
    student_courses = defaultdict(list)
    # Map student ID -> profile info
    student_profiles = {}
    # Map course_id -> list of students
    course_students = {}

    sorted_course_names = sorted(course_map.keys())

    for course_name in sorted_course_names:
        course = course_map[course_name]
        course_id = course['id']
        students = get_students_for_course(classroom_service, course_id)
        course_students[course_id] = students

        for student in students:
            user_id = student['userId']
            profile = student.get('profile', {})
            name = profile.get('name', {}).get('fullName', f'User {user_id}')

            student_courses[user_id].append(course_name)
            student_profiles[user_id] = name

    # For each student, determine which course should have the assignment
    # Uses deterministic hash including assignment_title for true round-robin:
    # different assignments will go to different periods for each student
    student_assignment = {}  # student_id -> course_name where they get the assignment

    for student_id, courses in student_courses.items():
        if len(courses) == 1:
            # Single-period student: assign to their only course
            student_assignment[student_id] = courses[0]
        else:
            # Multi-period student: use hash with assignment title for round-robin
            # Including the assignment title means each assignment may go to a
            # different period, spreading the workload across all their courses
            hash_input = f"{student_id}:{assignment_title}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            course_idx = hash_val % len(courses)
            student_assignment[student_id] = sorted(courses)[course_idx]

    # Build reverse map: course_name -> list of student_ids who should get assignment there
    course_assignees = defaultdict(list)
    for student_id, course_name in student_assignment.items():
        course_assignees[course_name].append(student_id)

    multi_period_count = sum(1 for courses in student_courses.values() if len(courses) > 1)
    print(f"  Total students: {len(student_courses)}")
    print(f"  Multi-period students: {multi_period_count}")

    return course_assignees, student_profiles


def create_classroom_assignments(classroom_service, course_map, course_assignees,
                                  assignment_title, quiz_title, form_id, slides_title, slides_id,
                                  reading_content, worksheet_content, dry_run=False):
    """Create assignment in each course, distributing to correct students."""
    print("\n  Creating Classroom assignments...")

    # Note: API-created assignments do NOT send email notifications to students
    # (only web UI assignments trigger notifications) so we can use full features

    # Build assignment description from reading and worksheet
    description = f"""READING
-------
{reading_content}

GROUP DISCUSSION
----------------
{worksheet_content}

MATERIALS
---------
After reading and discussing, complete the quiz to check your understanding."""

    created_count = 0
    sorted_course_names = sorted(course_map.keys())

    for course_name in sorted_course_names:
        course = course_map[course_name]
        course_id = course['id']
        assignee_ids = course_assignees.get(course_name, [])

        if not assignee_ids:
            print(f"    {course_name}: SKIP (no students to assign)")
            continue

        if dry_run:
            print(f"    {course_name}: [DRY RUN] Would assign to {len(assignee_ids)} students")
            continue

        # Create the assignment with proper names
        coursework_body = {
            'title': assignment_title,
            'description': description,
            'workType': 'ASSIGNMENT',
            'state': 'PUBLISHED',
            'dueDate': DEFAULT_DUE_DATE,
            'dueTime': DEFAULT_DUE_TIME,
            'maxPoints': 100,
            'assigneeMode': 'INDIVIDUAL_STUDENTS',
            'individualStudentsOptions': {
                'studentIds': assignee_ids
            },
            'materials': [
                {
                    # Use direct form URL (not responderUri) - may show proper title
                    'link': {
                        'url': f'https://docs.google.com/forms/d/{form_id}/viewform'
                    }
                },
                {
                    # Use 'driveFile' for slides - Classroom reads title from Drive
                    'driveFile': {
                        'driveFile': {
                            'id': slides_id
                        },
                        'shareMode': 'VIEW'
                    }
                }
            ],
            'associatedWithDeveloper': True  # Enables API grading
        }

        try:
            result = api_call_with_retry(
                classroom_service.courses().courseWork().create,
                courseId=course_id,
                body=coursework_body
            )
            print(f"    {course_name}: Created for {len(assignee_ids)} students")
            created_count += 1
        except HttpError as e:
            print(f"    {course_name}: ERROR - {e}")

    return created_count


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Create Google Classroom assignments from lesson folders.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/create_lesson_assignment.py lessons/08-every-kid-needs-champion/
    python scripts/create_lesson_assignment.py lessons/08-every-kid-needs-champion/ --dry-run
        """
    )
    parser.add_argument('lesson_path', help='Path to lesson folder')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    args = parser.parse_args()

    lesson_path = Path(args.lesson_path)
    dry_run = args.dry_run

    # Validate lesson folder
    if not lesson_path.exists():
        print(f"ERROR: Lesson folder not found: {lesson_path}")
        sys.exit(1)

    quiz_path = lesson_path / 'quiz.md'
    slides_path = lesson_path / 'slides.yaml'
    reading_path = lesson_path / 'reading.md'
    worksheet_path = lesson_path / 'worksheet.md'

    if not quiz_path.exists():
        print(f"ERROR: quiz.md not found in {lesson_path}")
        sys.exit(1)

    if not slides_path.exists():
        print(f"ERROR: slides.yaml not found in {lesson_path}")
        sys.exit(1)

    if not reading_path.exists():
        print(f"ERROR: reading.md not found in {lesson_path}")
        sys.exit(1)

    if not worksheet_path.exists():
        print(f"ERROR: worksheet.md not found in {lesson_path}")
        sys.exit(1)

    print("=" * 60)
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    else:
        print("CREATING LESSON ASSIGNMENT")
    print("=" * 60)
    print(f"Lesson: {lesson_path.name}")

    # Authenticate
    print("\nAuthenticating...")
    creds = get_credentials()

    # Build services
    forms_service = build('forms', 'v1', credentials=creds)
    slides_service = build('slides', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    classroom_service = build('classroom', 'v1', credentials=creds)

    # Parse quiz
    print("\n1. QUIZ")
    quiz_content = quiz_path.read_text(encoding='utf-8')
    quiz_title, questions = parse_quiz(quiz_content)
    print(f"  Title: {quiz_title}")
    print(f"  Questions: {len(questions)}")

    form_id, form_url = create_google_form(forms_service, drive_service, quiz_title, questions, dry_run)
    if not dry_run:
        print(f"  Form URL: {form_url}")

    # Create slides
    print("\n2. SLIDES")
    with open(slides_path, 'r', encoding='utf-8') as f:
        slides_config = yaml.safe_load(f)

    slides_title = slides_config.get('title', 'Untitled')
    print(f"  Title: {slides_title}")

    presentation_id = create_google_slides(slides_service, drive_service, slides_config, lesson_path, dry_run)
    slides_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit" if not dry_run else "https://example.com/dry-run-slides"
    if not dry_run:
        print(f"  Slides URL: {slides_url}")

    # Get courses and students
    print("\n3. CLASSROOM DISTRIBUTION")
    course_map = get_courses(classroom_service)
    # Use quiz title (without "Quiz: " prefix) as assignment title for round-robin hashing
    assignment_title = quiz_title.replace("Quiz: ", "")
    course_assignees, student_profiles = find_multi_period_students(classroom_service, course_map, assignment_title)

    # Show distribution
    print("\n  Distribution by period:")
    for course_name in sorted(course_assignees.keys()):
        count = len(course_assignees[course_name])
        print(f"    {course_name}: {count} students")

    # Read reading and worksheet content
    print("\n4. LOADING CONTENT")
    reading_content = reading_path.read_text(encoding='utf-8')
    worksheet_content = worksheet_path.read_text(encoding='utf-8')
    # Strip markdown headers for cleaner display
    reading_content = re.sub(r'^#.*\n+', '', reading_content).strip()
    worksheet_content = re.sub(r'^#.*\n+', '', worksheet_content).strip()
    print(f"  Reading: {len(reading_content)} characters")
    print(f"  Worksheet: {len(worksheet_content)} characters")

    # Create assignments
    print("\n5. CREATING ASSIGNMENTS")
    created = create_classroom_assignments(
        classroom_service, course_map, course_assignees,
        assignment_title, quiz_title, form_id, slides_title, presentation_id,
        reading_content, worksheet_content, dry_run
    )

    # Record in tracker (persistent storage)
    print("\n6. RECORDING IN TRACKER")
    try:
        tracker = GYOTracker(dry_run=dry_run)
        total_points = len(questions)  # Each question is 1 point
        tracker.record_assignment(
            assignment_title=assignment_title,
            form_id=form_id if not dry_run else "dry-run-form-id",
            form_url=form_url if not dry_run else "https://example.com/dry-run-form",
            slides_id=presentation_id if not dry_run else "dry-run-slides-id",
            slides_url=slides_url,
            total_points=total_points,
            status="ACTIVE"
        )
        if not dry_run:
            print(f"  Tracker URL: {tracker.get_spreadsheet_url()}")
    except Exception as e:
        print(f"  WARNING: Failed to record in tracker: {e}")
        print("  (Assignment was still created successfully)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if dry_run:
        print("DRY RUN - No changes were made")
        print(f"Would create form with {len(questions)} questions")
        print(f"Would create slides with {len(slides_config.get('slides', []))} slides")
        print(f"Would create assignments in {len([c for c in course_assignees.values() if c])} periods")
    else:
        print(f"Form created: {form_url}")
        print(f"Slides created: {slides_url}")
        print(f"Assignments created in {created} periods")
        print(f"Tracked in: {tracker.get_spreadsheet_url()}")


if __name__ == '__main__':
    main()
