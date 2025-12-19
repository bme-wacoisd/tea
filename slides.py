#!/usr/bin/env python3
"""
slides.py - Create Google Slides presentations from YAML configuration

Usage:
    python slides.py <slides.yaml>
    python slides.py lessons/01-james-baldwin-civil-rights/slides.yaml

METHODOLOGY:
============
1. Read slide content from YAML config (NOT hardcoded!)
2. Create a new blank presentation via Slides API
3. DELETE the default first slide (it has template placeholder junk)
4. Create each slide as BLANK layout, then add custom shapes/text
5. For images: upload to Google Drive first, make public, then insert via URL
6. Each element needs a unique object ID (minimum 5 characters)

YAML STRUCTURE:
===============
- title: Presentation title
- subtitle: Presentation subtitle
- theme: Color definitions (primary, secondary, accent1, accent2, background, text)
- images: Named image paths relative to YAML file
- slides: List of slide definitions with 'type' and type-specific content

SUPPORTED SLIDE TYPES:
======================
- title: Title slide with title/subtitle
- big_idea: Full-bleed background with main message
- image_bio: Image with biographical text
- quote: Large quote with attribution
- table: Styled data table
- comparison: Two-column IS/IS NOT style
- two_column: Two columns of bullets
- bullets: Bullet points with accent markers
- numbered: Numbered list items
- closing: Final quote slide with CTA

AUTHENTICATION:
===============
- Requires credentials.json (OAuth Desktop App from Google Cloud Console)
- First run opens browser for authorization
- Token saved to token.pickle for subsequent runs

REQUIRED APIS:
==============
- Google Slides API
- Google Drive API
"""

import sys
import pickle
from pathlib import Path
import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/drive']


def get_credentials():
    """Get valid user credentials from storage or initiate OAuth flow."""
    creds = None
    token_path = Path('token.pickle')
    creds_path = Path('credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print("ERROR: credentials.json not found!")
                print("See CLAUDE.md for setup instructions.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def load_config(yaml_path):
    """Load and parse the YAML configuration file."""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


SUPPORTED_SLIDE_TYPES = [
    'title', 'big_idea', 'image_bio', 'quote', 'table',
    'comparison', 'two_column', 'bullets', 'numbered', 'closing'
]


def verify_slides_yaml(config: dict, base_path: Path) -> tuple[bool, list[str]]:
    """
    Verify slides YAML configuration.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Check required fields
    if not config.get('title'):
        errors.append("Missing 'title' field")

    if not config.get('theme'):
        errors.append("Missing 'theme' field")
    else:
        theme = config['theme']
        required_colors = ['primary', 'secondary', 'accent1', 'accent2', 'background', 'text']
        for color in required_colors:
            if color not in theme:
                errors.append(f"Missing theme color: {color}")

    if not config.get('slides'):
        errors.append("Missing 'slides' field")
        return False, errors

    # Check slides
    for i, slide in enumerate(config['slides']):
        slide_type = slide.get('type')
        if not slide_type:
            errors.append(f"Slide {i+1}: Missing 'type' field")
        elif slide_type not in SUPPORTED_SLIDE_TYPES:
            errors.append(f"Slide {i+1}: Unknown type '{slide_type}' (supported: {', '.join(SUPPORTED_SLIDE_TYPES)})")

    # Check images exist
    images = config.get('images', {})
    for name, path in images.items():
        full_path = base_path / path
        if not full_path.exists():
            errors.append(f"Image not found: {path}")

    return len(errors) == 0, errors


def rgb_to_color(rgb_dict):
    """Convert {r, g, b} dict to Google Slides color format."""
    return {'red': rgb_dict['r'], 'green': rgb_dict['g'], 'blue': rgb_dict['b']}


def inch_to_emu(inches):
    """Convert inches to EMU (English Metric Units)."""
    return int(inches * 914400)


def pt_to_emu(pt):
    """Convert points to EMU."""
    return int(pt * 12700)


class SlideBuilder:
    """Builds Google Slides presentations from YAML config."""

    # Standard Google Slides 16:9 dimensions (default, cannot be changed via API)
    SLIDE_WIDTH = 10.0    # inches
    SLIDE_HEIGHT = 5.625  # inches

    def __init__(self, slides_service, drive_service, config, base_path):
        self.slides = slides_service
        self.drive = drive_service
        self.config = config
        self.base_path = Path(base_path)
        self.presentation_id = None
        self.counter = 0
        self.uploaded_images = {}

        # Parse theme colors
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
        """Create a unique object ID (min 5 chars)."""
        return f'slide{self.counter}_{suffix}'

    def upload_image(self, image_key):
        """Upload an image to Drive and cache the URL."""
        if image_key in self.uploaded_images:
            return self.uploaded_images[image_key]

        images = self.config.get('images', {})
        if image_key not in images:
            return None

        image_path = self.base_path / images[image_key]
        if not image_path.exists():
            print(f"  WARNING: Image not found: {image_path}")
            return None

        print(f"  Uploading image: {image_path.name}")
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
        """Create a new presentation.

        Note: Google Slides default page size is 10" x 5.625" (16:9).
        This cannot be changed via the API, so all coordinates are designed for this.
        """
        pres = self.slides.presentations().create(
            body={'title': self.config.get('title', 'Untitled Presentation')}
        ).execute()
        self.presentation_id = pres['presentationId']

        # Delete the default template slide (it has placeholder junk)
        default_slide_id = pres['slides'][0]['objectId']
        self.slides.presentations().batchUpdate(
            presentationId=self.presentation_id,
            body={'requests': [{'deleteObject': {'objectId': default_slide_id}}]}
        ).execute()

        return self.presentation_id

    def create_slide(self):
        """Create a new blank slide."""
        response = self.slides.presentations().batchUpdate(
            presentationId=self.presentation_id,
            body={'requests': [{'createSlide': {'slideLayoutReference': {'predefinedLayout': 'BLANK'}}}]}
        ).execute()
        return response['replies'][0]['createSlide']['objectId']

    def execute_requests(self, requests):
        """Execute a batch of requests."""
        if requests:
            self.slides.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={'requests': requests}
            ).execute()

    def add_shape(self, requests, slide_id, shape_id, shape_type, x, y, w, h, color=None):
        """Add a shape to requests."""
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
        """Add text to a shape."""
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

    def add_image(self, requests, slide_id, image_id, url, x, y, w, h):
        """Add an image to a slide."""
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

    def create_table(self, requests, slide_id, table_id, rows, cols, x, y, w, h):
        """Create a table."""
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
        """Style a table cell."""
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
        """Get a color by name from the theme."""
        return self.colors.get(accent_name, self.colors['primary'])

    # ===== SLIDE TYPE BUILDERS =====

    def build_title_slide(self, slide_id, slide_config):
        """Build title slide."""
        requests = []
        title = self.config.get('title', 'Untitled')
        subtitle = self.config.get('subtitle', '')
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT  # 10" x 5.625"

        # Header bar
        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 1.9, self.colors['primary'])
        # Gold stripe
        self.add_shape(requests, slide_id, self.make_id('stripe'), 'RECTANGLE', 0, 1.8, W, 0.1, self.colors['accent1'])
        # Title
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.4, 0.4, W - 0.8, 1.2, None)
        self.add_text(requests, self.make_id('title'), title, font_size=40, bold=True, color=self.colors['white'], alignment='CENTER')
        # Subtitle
        if subtitle:
            self.add_shape(requests, slide_id, self.make_id('subtitle'), 'TEXT_BOX', 0.4, 2.4, W - 0.8, 0.6, None)
            self.add_text(requests, self.make_id('subtitle'), subtitle, font_size=22, color=self.colors['text'], alignment='CENTER')

        return requests

    def build_big_idea_slide(self, slide_id, slide_config):
        """Build big idea slide."""
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
        """Build image with bio slide."""
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
        """Build quote slide."""
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
        """Build table slide."""
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
        """Build comparison (IS vs IS NOT) slide."""
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

        col_width = (W - 0.8) / 2  # Two equal columns with margins
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
        """Build two-column bullet slide."""
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
        """Build bullet points slide."""
        requests = []
        title = slide_config.get('title', '')
        items = slide_config.get('items', [])
        accent = self.get_accent_color(slide_config.get('accent', 'accent2'))
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT

        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, accent)
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])

        # Calculate vertical spacing based on number of items
        available_height = H - 1.3  # Space below header
        item_height = min(0.8, available_height / max(len(items), 1))
        y_pos = 1.15

        for i, bullet in enumerate(items):
            self.add_shape(requests, slide_id, self.make_id(f'dot_{i}'), 'ELLIPSE', 0.4, y_pos + 0.1, 0.25, 0.25, accent)
            self.add_shape(requests, slide_id, self.make_id(f'txt_{i}'), 'TEXT_BOX', 0.8, y_pos, W - 1.2, 0.6, None)
            self.add_text(requests, self.make_id(f'txt_{i}'), bullet, font_size=16, color=self.colors['text'])
            y_pos += item_height

        return requests

    def build_numbered_slide(self, slide_id, slide_config):
        """Build numbered list slide."""
        requests = []
        title = slide_config.get('title', '')
        items = slide_config.get('items', [])
        colors_cycle = [self.colors['accent2'], self.colors['secondary'], self.colors['accent1'], self.colors['primary']]
        W, H = self.SLIDE_WIDTH, self.SLIDE_HEIGHT

        self.add_shape(requests, slide_id, self.make_id('header'), 'RECTANGLE', 0, 0, W, 0.9, self.colors['primary'])
        self.add_shape(requests, slide_id, self.make_id('title'), 'TEXT_BOX', 0.3, 0.2, 9, 0.6, None)
        self.add_text(requests, self.make_id('title'), title, font_size=24, bold=True, color=self.colors['white'])

        # Calculate vertical spacing based on number of items
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
        """Build closing slide."""
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
        """Build a slide based on its type."""
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
        """Build the entire presentation."""
        self.create_presentation()
        for slide_config in self.config.get('slides', []):
            slide_type = slide_config.get('type', 'unknown')
            print(f"  Creating slide: {slide_type}")
            self.build_slide(slide_config)

        return self.presentation_id


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    yaml_path = Path(sys.argv[1])
    if not yaml_path.exists():
        print(f"ERROR: File not found: {yaml_path}")
        sys.exit(1)

    print(f"Loading config from: {yaml_path}")
    config = load_config(yaml_path)

    # Verify before doing anything with Google API
    print("Verifying configuration...")
    is_valid, errors = verify_slides_yaml(config, yaml_path.parent)

    if not is_valid:
        print("\nVERIFICATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"Verification passed. {len(config['slides'])} slides.")

    print("Authenticating with Google...")
    creds = get_credentials()
    if not creds:
        sys.exit(1)

    slides_service = build('slides', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    print("Creating presentation...")
    builder = SlideBuilder(slides_service, drive_service, config, yaml_path.parent)
    presentation_id = builder.build_all()

    print("\n" + "=" * 60)
    print("PRESENTATION CREATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nOpen your presentation at:")
    print(f"https://docs.google.com/presentation/d/{presentation_id}/edit")


if __name__ == '__main__':
    main()
