#!/usr/bin/env python3
"""
sheets_tracker.py - Google Sheets-based tracking for GYO assignments and quiz completions

This module provides a robust, transactional interface for tracking:
1. Assignments (form ID, slides ID, creation date, etc.)
2. Quiz completions (form responses, scores, sync status)

The spreadsheet acts as our source of truth for what's been created and synced.

Usage:
    from sheets_tracker import GYOTracker

    tracker = GYOTracker()
    tracker.record_assignment(...)
    tracker.record_quiz_completion(...)
    tracker.mark_synced_to_classroom(...)
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============================================================================
# CONFIGURATION
# ============================================================================

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_sheets.json'
SPREADSHEET_ID_PATH = PROJECT_ROOT / 'tracking_spreadsheet_id.txt'

# Spreadsheet structure
SPREADSHEET_TITLE = "GYO Grade Tracking"
ASSIGNMENTS_SHEET = "Assignments"
COMPLETIONS_SHEET = "Quiz Completions"

# Column headers
ASSIGNMENTS_HEADERS = [
    "Assignment Title",
    "Form ID",
    "Form URL",
    "Slides ID",
    "Slides URL",
    "Total Points",
    "Created At",
    "Updated At",
    "Status",  # ACTIVE, DELETED
]

COMPLETIONS_HEADERS = [
    "Response ID",  # Unique key from Forms API
    "Assignment Title",
    "Form ID",
    "Student Email",
    "Student Name",
    "Course",
    "Score",
    "Total Points",
    "Percentage",
    "Form Submitted At",
    "Synced to Classroom",  # YES/NO
    "Classroom Sync Time",
    "Classroom Submission ID",
    "Notes",
]


# ============================================================================
# RATE LIMIT HANDLING
# ============================================================================

def api_call_with_retry(api_call: Callable, max_retries: int = 5, **kwargs):
    """
    Execute an API call with exponential backoff retry on rate limit errors.

    Google Sheets API limits:
    - 60 read requests per minute per user
    - 60 write requests per minute per user

    Args:
        api_call: The API method to call (e.g., service.spreadsheets().values().append)
        max_retries: Maximum number of retry attempts
        **kwargs: Arguments to pass to the API call

    Returns:
        API response

    Raises:
        HttpError: If error persists after all retries
    """
    for attempt in range(max_retries):
        try:
            return api_call(**kwargs).execute()
        except HttpError as e:
            if e.resp.status == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds (1s, 2s, 4s, 8s, 16s)
                    wait_time = 2 ** attempt
                    print(f"  Rate limit hit, waiting {wait_time}s before retry ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"  Rate limit exceeded after {max_retries} retries")
                    raise
            else:
                # Not a rate limit error, re-raise immediately
                raise

    # Should never reach here, but just in case
    raise Exception("Unexpected retry logic failure")


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
            print("Refreshing Sheets API credentials...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"ERROR: {CREDENTIALS_PATH} not found!")
                sys.exit(1)
            print("Opening browser for Sheets API authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Sheets credentials saved to {TOKEN_PATH}")

    return creds


# ============================================================================
# TRACKER CLASS
# ============================================================================

class GYOTracker:
    """
    Google Sheets-based tracker for GYO assignments and quiz completions.

    Provides transactional-style operations with idempotency:
    - Recording an assignment twice updates rather than duplicates
    - Recording a completion twice updates rather than duplicates
    - All operations are based on unique keys (assignment title, response ID)
    """

    def __init__(self, dry_run: bool = False):
        """Initialize the tracker."""
        self.dry_run = dry_run
        self.creds = get_credentials()
        self.sheets_service = build('sheets', 'v4', credentials=self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self.spreadsheet_id = self._get_or_create_spreadsheet()

        # Cache for row lookups (reduces API calls)
        self._assignments_cache: Dict[str, int] = {}  # title -> row number
        self._completions_cache: Dict[str, int] = {}  # response_id -> row number
        self._cache_valid = False

    def _get_or_create_spreadsheet(self) -> str:
        """Get existing spreadsheet ID or create a new one."""
        # Check if we have a saved spreadsheet ID
        if SPREADSHEET_ID_PATH.exists():
            spreadsheet_id = SPREADSHEET_ID_PATH.read_text().strip()
            # Verify it still exists
            try:
                self.sheets_service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id
                ).execute()
                return spreadsheet_id
            except HttpError as e:
                if e.resp.status == 404:
                    print("Saved spreadsheet not found, creating new one...")
                else:
                    raise

        # Create new spreadsheet
        return self._create_spreadsheet()

    def _create_spreadsheet(self) -> str:
        """Create the tracking spreadsheet with proper structure."""
        print(f"Creating tracking spreadsheet: {SPREADSHEET_TITLE}")

        spreadsheet_body = {
            'properties': {'title': SPREADSHEET_TITLE},
            'sheets': [
                {
                    'properties': {
                        'title': ASSIGNMENTS_SHEET,
                        'gridProperties': {'frozenRowCount': 1}
                    }
                },
                {
                    'properties': {
                        'title': COMPLETIONS_SHEET,
                        'gridProperties': {'frozenRowCount': 1}
                    }
                }
            ]
        }

        spreadsheet = self.sheets_service.spreadsheets().create(
            body=spreadsheet_body
        ).execute()

        spreadsheet_id = spreadsheet['spreadsheetId']
        print(f"Created spreadsheet: {spreadsheet_id}")

        # Add headers
        self._write_headers(spreadsheet_id)

        # Share with wacoisd.org domain
        self._share_with_domain(spreadsheet_id)

        # Save the spreadsheet ID
        SPREADSHEET_ID_PATH.write_text(spreadsheet_id)
        print(f"Spreadsheet ID saved to {SPREADSHEET_ID_PATH}")

        # Format headers (bold, freeze)
        self._format_headers(spreadsheet_id)

        return spreadsheet_id

    def _write_headers(self, spreadsheet_id: str):
        """Write headers to both sheets."""
        requests = [
            {
                'range': f"'{ASSIGNMENTS_SHEET}'!A1",
                'values': [ASSIGNMENTS_HEADERS]
            },
            {
                'range': f"'{COMPLETIONS_SHEET}'!A1",
                'values': [COMPLETIONS_HEADERS]
            }
        ]

        self.sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'valueInputOption': 'RAW', 'data': requests}
        ).execute()

    def _share_with_domain(self, spreadsheet_id: str):
        """Share the spreadsheet with wacoisd.org domain."""
        try:
            self.drive_service.permissions().create(
                fileId=spreadsheet_id,
                body={
                    'type': 'domain',
                    'role': 'reader',
                    'domain': 'wacoisd.org'
                },
                fields='id'
            ).execute()
            print("Shared with wacoisd.org domain (read access)")
        except HttpError as e:
            print(f"Warning: Could not share with domain: {e}")

    def _format_headers(self, spreadsheet_id: str):
        """Format header rows (bold, background color)."""
        # Get sheet IDs
        spreadsheet = self.sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        sheet_ids = {}
        for sheet in spreadsheet['sheets']:
            sheet_ids[sheet['properties']['title']] = sheet['properties']['sheetId']

        requests = []
        for sheet_name, sheet_id in sheet_ids.items():
            # Bold header row
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {'bold': True},
                            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                        }
                    },
                    'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                }
            })

        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests}
        ).execute()

    def _refresh_cache(self):
        """Refresh the row caches from the spreadsheet."""
        # Get assignments
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{ASSIGNMENTS_SHEET}'!A:A"
        ).execute()

        values = result.get('values', [])
        self._assignments_cache = {}
        for i, row in enumerate(values[1:], start=2):  # Skip header, 1-indexed
            if row:
                self._assignments_cache[row[0]] = i

        # Get completions
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{COMPLETIONS_SHEET}'!A:A"
        ).execute()

        values = result.get('values', [])
        self._completions_cache = {}
        for i, row in enumerate(values[1:], start=2):
            if row:
                self._completions_cache[row[0]] = i

        self._cache_valid = True

    def _invalidate_cache(self):
        """Mark cache as invalid."""
        self._cache_valid = False

    def get_spreadsheet_url(self) -> str:
        """Get the URL to the tracking spreadsheet."""
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"

    # ========================================================================
    # ASSIGNMENT TRACKING
    # ========================================================================

    def record_assignment(
        self,
        assignment_title: str,
        form_id: str,
        form_url: str,
        slides_id: str,
        slides_url: str,
        total_points: int,
        status: str = "ACTIVE"
    ) -> bool:
        """
        Record an assignment in the tracking sheet.

        Idempotent: If assignment already exists, updates it instead of duplicating.

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would record assignment: {assignment_title}")
            return True

        now = datetime.now(timezone.utc).isoformat()

        if not self._cache_valid:
            self._refresh_cache()

        row_data = [
            assignment_title,
            form_id,
            form_url,
            slides_id,
            slides_url,
            total_points,
            now,  # created_at (will be preserved on update)
            now,  # updated_at
            status
        ]

        try:
            if assignment_title in self._assignments_cache:
                # Update existing row (preserve created_at)
                row_num = self._assignments_cache[assignment_title]

                # Get existing created_at
                existing = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{ASSIGNMENTS_SHEET}'!G{row_num}"
                ).execute()
                created_at = existing.get('values', [[now]])[0][0]
                row_data[6] = created_at  # Preserve original created_at

                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{ASSIGNMENTS_SHEET}'!A{row_num}",
                    valueInputOption='RAW',
                    body={'values': [row_data]}
                ).execute()
                print(f"  Updated assignment in tracker: {assignment_title}")
            else:
                # Append new row
                self.sheets_service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{ASSIGNMENTS_SHEET}'!A:A",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': [row_data]}
                ).execute()
                print(f"  Recorded assignment in tracker: {assignment_title}")
                self._invalidate_cache()

            return True

        except HttpError as e:
            print(f"  ERROR recording assignment: {e}")
            return False

    def mark_assignment_deleted(self, assignment_title: str) -> bool:
        """Mark an assignment as deleted (soft delete)."""
        if self.dry_run:
            print(f"  [DRY RUN] Would mark assignment deleted: {assignment_title}")
            return True

        if not self._cache_valid:
            self._refresh_cache()

        if assignment_title not in self._assignments_cache:
            print(f"  Assignment not found in tracker: {assignment_title}")
            return False

        try:
            row_num = self._assignments_cache[assignment_title]
            now = datetime.now(timezone.utc).isoformat()

            # Update status and updated_at
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{ASSIGNMENTS_SHEET}'!H{row_num}:I{row_num}",
                valueInputOption='RAW',
                body={'values': [[now, "DELETED"]]}
            ).execute()
            print(f"  Marked assignment as deleted: {assignment_title}")
            return True

        except HttpError as e:
            print(f"  ERROR marking assignment deleted: {e}")
            return False

    def get_assignment(self, assignment_title: str) -> Optional[Dict[str, Any]]:
        """Get assignment details by title."""
        if not self._cache_valid:
            self._refresh_cache()

        if assignment_title not in self._assignments_cache:
            return None

        row_num = self._assignments_cache[assignment_title]

        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{ASSIGNMENTS_SHEET}'!A{row_num}:I{row_num}"
        ).execute()

        values = result.get('values', [[]])[0]
        if not values:
            return None

        # Pad with empty strings if row is shorter than headers
        while len(values) < len(ASSIGNMENTS_HEADERS):
            values.append('')

        return dict(zip(ASSIGNMENTS_HEADERS, values))

    def get_all_assignments(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get all assignments."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{ASSIGNMENTS_SHEET}'!A:I"
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:  # Only header or empty
            return []

        assignments = []
        for row in values[1:]:
            # Pad with empty strings
            while len(row) < len(ASSIGNMENTS_HEADERS):
                row.append('')

            assignment = dict(zip(ASSIGNMENTS_HEADERS, row))

            if not include_deleted and assignment.get('Status') == 'DELETED':
                continue

            assignments.append(assignment)

        return assignments

    # ========================================================================
    # QUIZ COMPLETION TRACKING
    # ========================================================================

    def record_quiz_completion(
        self,
        response_id: str,
        assignment_title: str,
        form_id: str,
        student_email: str,
        student_name: str,
        course: str,
        score: Optional[int],
        total_points: int,
        submitted_at: str,
        notes: str = ""
    ) -> bool:
        """
        Record a quiz completion in the tracking sheet.

        Idempotent: If response already exists, updates it instead of duplicating.

        Returns True if successful, False otherwise.
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would record completion: {student_name} - {assignment_title}")
            return True

        if not self._cache_valid:
            self._refresh_cache()

        percentage = round((score / total_points) * 100, 1) if score is not None and total_points > 0 else ""

        row_data = [
            response_id,
            assignment_title,
            form_id,
            student_email,
            student_name,
            course,
            score if score is not None else "",
            total_points,
            percentage,
            submitted_at,
            "NO",  # Synced to Classroom
            "",    # Classroom Sync Time
            "",    # Classroom Submission ID
            notes
        ]

        try:
            if response_id in self._completions_cache:
                # Update existing row but preserve sync status
                row_num = self._completions_cache[response_id]

                # Get existing sync status
                existing = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{COMPLETIONS_SHEET}'!K{row_num}:N{row_num}"
                ).execute()
                existing_sync = existing.get('values', [[]])[0]
                if existing_sync:
                    # Preserve existing sync info
                    while len(existing_sync) < 4:
                        existing_sync.append('')
                    row_data[10:14] = existing_sync

                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{COMPLETIONS_SHEET}'!A{row_num}",
                    valueInputOption='RAW',
                    body={'values': [row_data]}
                ).execute()
                print(f"  Updated completion in tracker: {student_name}")
            else:
                # Append new row
                self.sheets_service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{COMPLETIONS_SHEET}'!A:A",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': [row_data]}
                ).execute()
                print(f"  Recorded completion in tracker: {student_name} - {assignment_title}")
                self._invalidate_cache()

            return True

        except HttpError as e:
            print(f"  ERROR recording completion: {e}")
            return False

    def record_quiz_completions_batch(
        self,
        completions: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Record multiple quiz completions in a single batch operation.

        This is much more efficient than calling record_quiz_completion() repeatedly,
        as it reduces API calls from N to 1-2 calls regardless of batch size.

        Args:
            completions: List of completion dicts with keys:
                - response_id (str)
                - assignment_title (str)
                - form_id (str)
                - student_email (str)
                - student_name (str)
                - course (str)
                - score (int or None)
                - total_points (int)
                - submitted_at (str)
                - notes (str, optional)

        Returns:
            Dict with counts: {'recorded': N, 'updated': M, 'errors': K}
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would record {len(completions)} completions in batch")
            return {'recorded': len(completions), 'updated': 0, 'errors': 0}

        if not completions:
            return {'recorded': 0, 'updated': 0, 'errors': 0}

        if not self._cache_valid:
            self._refresh_cache()

        new_rows = []
        updates = []
        stats = {'recorded': 0, 'updated': 0, 'errors': 0}

        # Prepare all rows
        for completion in completions:
            response_id = completion['response_id']
            assignment_title = completion['assignment_title']
            form_id = completion['form_id']
            student_email = completion['student_email']
            student_name = completion['student_name']
            course = completion.get('course', '')
            score = completion.get('score')
            total_points = completion['total_points']
            submitted_at = completion['submitted_at']
            notes = completion.get('notes', '')

            percentage = round((score / total_points) * 100, 1) if score is not None and total_points > 0 else ""

            row_data = [
                response_id,
                assignment_title,
                form_id,
                student_email,
                student_name,
                course,
                score if score is not None else "",
                total_points,
                percentage,
                submitted_at,
                "NO",  # Synced to Classroom
                "",    # Classroom Sync Time
                "",    # Classroom Submission ID
                notes
            ]

            if response_id in self._completions_cache:
                # Queue update (preserve sync status)
                row_num = self._completions_cache[response_id]
                updates.append((row_num, row_data, student_name))
            else:
                # Queue new row
                new_rows.append((row_data, student_name))

        # Execute batch append for new rows
        if new_rows:
            try:
                api_call_with_retry(
                    self.sheets_service.spreadsheets().values().append,
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{COMPLETIONS_SHEET}'!A:A",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': [row[0] for row in new_rows]}
                )
                for _, student_name in new_rows:
                    print(f"  Recorded completion in tracker: {student_name}")
                    stats['recorded'] += 1
                self._invalidate_cache()
            except HttpError as e:
                print(f"  ERROR batch recording completions: {e}")
                stats['errors'] += len(new_rows)

        # Execute batch update for existing rows (preserving sync status)
        if updates:
            try:
                batch_data = []
                for row_num, row_data, _ in updates:
                    # Get existing sync status
                    try:
                        existing = api_call_with_retry(
                            self.sheets_service.spreadsheets().values().get,
                            spreadsheetId=self.spreadsheet_id,
                            range=f"'{COMPLETIONS_SHEET}'!K{row_num}:N{row_num}"
                        )
                        existing_sync = existing.get('values', [[]])[0]
                        if existing_sync:
                            while len(existing_sync) < 4:
                                existing_sync.append('')
                            row_data[10:14] = existing_sync
                    except HttpError:
                        pass  # Keep default "NO" if can't read

                    batch_data.append({
                        'range': f"'{COMPLETIONS_SHEET}'!A{row_num}",
                        'values': [row_data]
                    })

                api_call_with_retry(
                    self.sheets_service.spreadsheets().values().batchUpdate,
                    spreadsheetId=self.spreadsheet_id,
                    body={'valueInputOption': 'RAW', 'data': batch_data}
                )
                for _, _, student_name in updates:
                    print(f"  Updated completion in tracker: {student_name}")
                    stats['updated'] += 1
            except HttpError as e:
                print(f"  ERROR batch updating completions: {e}")
                stats['errors'] += len(updates)

        return stats

    def mark_synced_to_classroom(
        self,
        response_id: str,
        submission_id: str,
        notes: str = ""
    ) -> bool:
        """Mark a quiz completion as synced to Classroom."""
        if self.dry_run:
            print(f"  [DRY RUN] Would mark synced: {response_id}")
            return True

        if not self._cache_valid:
            self._refresh_cache()

        if response_id not in self._completions_cache:
            print(f"  Completion not found in tracker: {response_id}")
            return False

        try:
            row_num = self._completions_cache[response_id]
            now = datetime.now(timezone.utc).isoformat()

            # Update sync columns
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{COMPLETIONS_SHEET}'!K{row_num}:N{row_num}",
                valueInputOption='RAW',
                body={'values': [["YES", now, submission_id, notes]]}
            ).execute()
            print(f"  Marked as synced: {response_id[:20]}...")
            return True

        except HttpError as e:
            print(f"  ERROR marking synced: {e}")
            return False

    def get_unsynced_completions(self) -> List[Dict[str, Any]]:
        """Get all quiz completions that haven't been synced to Classroom."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{COMPLETIONS_SHEET}'!A:N"
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            return []

        completions = []
        for row in values[1:]:
            # Pad with empty strings
            while len(row) < len(COMPLETIONS_HEADERS):
                row.append('')

            completion = dict(zip(COMPLETIONS_HEADERS, row))

            if completion.get('Synced to Classroom') != 'YES':
                completions.append(completion)

        return completions

    def get_all_completions(self) -> List[Dict[str, Any]]:
        """Get all quiz completions."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{COMPLETIONS_SHEET}'!A:N"
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            return []

        completions = []
        for row in values[1:]:
            while len(row) < len(COMPLETIONS_HEADERS):
                row.append('')
            completions.append(dict(zip(COMPLETIONS_HEADERS, row)))

        return completions


# ============================================================================
# STANDALONE USAGE
# ============================================================================

if __name__ == '__main__':
    """Test the tracker by creating/accessing the spreadsheet."""
    print("=" * 60)
    print("GYO TRACKER - INITIALIZATION TEST")
    print("=" * 60)

    tracker = GYOTracker()

    print(f"\nSpreadsheet URL: {tracker.get_spreadsheet_url()}")
    print(f"\nAssignments in tracker: {len(tracker.get_all_assignments())}")
    print(f"Completions in tracker: {len(tracker.get_all_completions())}")
    print(f"Unsynced completions: {len(tracker.get_unsynced_completions())}")

    print("\n" + "=" * 60)
    print("Tracker initialized successfully!")
    print("=" * 60)
