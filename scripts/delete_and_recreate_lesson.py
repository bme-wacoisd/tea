#!/usr/bin/env python3
"""
Delete existing lesson assignments and recreate them with latest content.

Usage:
    python scripts/delete_and_recreate_lesson.py lessons/08-every-kid-needs-champion --dry-run
    python scripts/delete_and_recreate_lesson.py lessons/08-every-kid-needs-champion
"""

import argparse
import json
import os
import sys
from pathlib import Path
import yaml
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from sheets_tracker import GYOTracker

# Target courses (exact names)
# Course names: odd periods = Instructional Practices, even periods = Communications
TARGET_COURSES = [
    '1 Instructional Practices & Practicum',
    '2 Communications and Technology',
    '3 Instructional Practices & Practicum',
    '4 Communications and Technology',
    '5 Instructional Practices & Practicum',
    '6 Communications and Technology',
    '7 Instructional Practices & Practicum',
    '8 Communications and Technology'
]


def get_credentials():
    """Load credentials from token file."""
    token_path = os.path.join(os.path.dirname(__file__), '..', 'token_dedup.json')
    with open(token_path, 'r') as f:
        creds_data = json.load(f)
    return Credentials.from_authorized_user_info(creds_data)


def get_lesson_title(lesson_path):
    """Get the lesson title from slides.yaml."""
    yaml_path = os.path.join(lesson_path, 'slides.yaml')
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('title', '')
    return None


def find_assignments_by_title(service, title):
    """Find all assignments with the given title across target courses."""
    courses = service.courses().list(courseStates=['ACTIVE']).execute().get('courses', [])

    found = []
    for course in courses:
        if course['name'] not in TARGET_COURSES:
            continue

        coursework = service.courses().courseWork().list(
            courseId=course['id']
        ).execute().get('courseWork', [])

        for cw in coursework:
            if cw['title'] == title:
                found.append({
                    'course_id': course['id'],
                    'course_name': course['name'],
                    'coursework_id': cw['id'],
                    'title': cw['title']
                })

    return found


def delete_assignments(service, assignments, tracker, dry_run=True):
    """Delete the specified assignments and mark deleted in tracker."""
    deleted_title = None
    for assignment in assignments:
        if dry_run:
            print(f"  [DRY RUN] Would delete: {assignment['title']} from {assignment['course_name']}")
        else:
            print(f"  Deleting: {assignment['title']} from {assignment['course_name']}...")
            service.courses().courseWork().delete(
                courseId=assignment['course_id'],
                id=assignment['coursework_id']
            ).execute()
            print(f"    Deleted.")
            deleted_title = assignment['title']

    # Mark as deleted in tracker (once per unique title, not per course)
    if deleted_title and not dry_run:
        tracker.mark_assignment_deleted(deleted_title)


def main():
    parser = argparse.ArgumentParser(description='Delete and recreate lesson assignments')
    parser.add_argument('lesson_path', help='Path to lesson folder')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--delete-only', action='store_true', help='Only delete, do not recreate')
    args = parser.parse_args()

    # Normalize path
    lesson_path = os.path.normpath(args.lesson_path)

    if not os.path.isdir(lesson_path):
        print(f"Error: {lesson_path} is not a directory")
        sys.exit(1)

    # Get lesson title
    title = get_lesson_title(lesson_path)
    if not title:
        print(f"Error: Could not find slides.yaml or title in {lesson_path}")
        sys.exit(1)

    print(f"Lesson: {title}")
    print(f"Path: {lesson_path}")
    print()

    # Connect to Classroom
    creds = get_credentials()
    service = build('classroom', 'v1', credentials=creds)

    # Initialize tracker
    tracker = GYOTracker(dry_run=args.dry_run)
    print(f"Tracker: {tracker.get_spreadsheet_url()}")
    print()

    # Find existing assignments
    print("Finding existing assignments...")
    assignments = find_assignments_by_title(service, title)

    if assignments:
        print(f"Found {len(assignments)} assignment(s):")
        for a in assignments:
            print(f"  - {a['course_name']}: {a['title']}")
        print()

        # Delete assignments
        print("Deleting assignments...")
        delete_assignments(service, assignments, tracker, dry_run=args.dry_run)
        print()
    else:
        print("No existing assignments found.")
        print()

    # Recreate unless delete-only
    if not args.delete_only:
        if args.dry_run:
            print("[DRY RUN] Would run: python scripts/create_lesson_assignment.py", lesson_path)
        else:
            print("Recreating assignments...")
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), 'create_lesson_assignment.py')
            result = subprocess.run([sys.executable, script_path, lesson_path], cwd=os.path.dirname(os.path.dirname(__file__)))
            if result.returncode != 0:
                print("Error creating assignments!")
                sys.exit(1)

    print("\nDone!")


if __name__ == '__main__':
    main()
