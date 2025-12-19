#!/usr/bin/env python3
"""
check_calendar_events.py - Verify if Google Classroom assignments create calendar events

This script checks if API-created assignments generate calendar events.
Hypothesis: Only web UI-created assignments create calendar events, not API-created ones.

Usage:
    python scripts/check_calendar_events.py

Requirements:
    - Enable Calendar API: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# OAuth scopes - need Calendar read access
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
]

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_calendar.json'

# Our assignment titles to search for
ASSIGNMENT_TITLES = [
    "Every Kid Needs a Champion",
    "The Birth of Public Education",
    "How Children Think at Different Ages",
    "Teaching in the Zone",
    "Reaching Every Learner",
    "Six Levels of Thinking",
    "Planning Backward from the End",
    "Designing for All Learners",
    "Checking for Understanding",
    "Preventing Problems Before They Start",
    "Learning by Doing",
    "Following the Child",
    "The Professional Boundary",
    "When You Must Speak Up",
    "Meeting Students Where They Are",
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
            print("Opening browser for Calendar API authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_PATH}")

    return creds


def main():
    print("=" * 60)
    print("CALENDAR EVENT VERIFICATION")
    print("=" * 60)
    print("\nChecking if API-created assignments generated calendar events...\n")

    creds = get_credentials()
    calendar_service = build('calendar', 'v3', credentials=creds)

    # Get list of calendars
    print("Fetching calendars...")
    calendars_result = calendar_service.calendarList().list().execute()
    calendars = calendars_result.get('items', [])

    print(f"Found {len(calendars)} calendars:\n")

    classroom_calendars = []
    for cal in calendars:
        summary = cal.get('summary', 'Untitled')
        cal_id = cal.get('id', '')

        # Look for Classroom-related calendars
        is_classroom = 'classroom' in summary.lower() or 'class' in summary.lower() or '@group.calendar.google.com' in cal_id
        marker = " <-- Classroom?" if is_classroom else ""
        print(f"  - {summary}{marker}")

        if is_classroom or 'Instructional' in summary or 'Communications' in summary:
            classroom_calendars.append(cal)

    # Search for events matching our assignment titles
    print("\n" + "-" * 60)
    print("SEARCHING FOR ASSIGNMENT EVENTS")
    print("-" * 60)

    # Search in primary calendar and any classroom calendars
    calendars_to_search = [{'id': 'primary', 'summary': 'Primary Calendar'}] + classroom_calendars

    # Time range: from a month ago to 6 months from now
    time_min = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
    time_max = (datetime.utcnow() + timedelta(days=180)).isoformat() + 'Z'

    found_events = []

    for cal in calendars_to_search:
        cal_id = cal.get('id', 'primary')
        cal_name = cal.get('summary', 'Unknown')

        print(f"\nSearching in: {cal_name}")

        try:
            events_result = calendar_service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            for event in events:
                title = event.get('summary', '')

                # Check if this event matches any of our assignment titles
                for assignment_title in ASSIGNMENT_TITLES:
                    if assignment_title.lower() in title.lower():
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                        found_events.append({
                            'title': title,
                            'calendar': cal_name,
                            'start': start,
                            'assignment': assignment_title
                        })
                        print(f"  FOUND: {title} ({start})")
                        break

        except Exception as e:
            print(f"  Error accessing calendar: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if found_events:
        print(f"\nFOUND {len(found_events)} calendar events matching our assignments:")
        for event in found_events:
            print(f"  - {event['assignment']}")
            print(f"    Calendar: {event['calendar']}")
            print(f"    Event title: {event['title']}")
            print(f"    Date: {event['start']}")
            print()
        print("CONCLUSION: API-created assignments DO create calendar events.")
    else:
        print("\nNO calendar events found for our API-created assignments.")
        print("\nCONCLUSION: API-created assignments do NOT create calendar events.")
        print("(Or they're on a calendar this account can't access)")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
