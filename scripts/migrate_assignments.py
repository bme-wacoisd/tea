#!/usr/bin/env python3
"""
migrate_assignments.py - Migrate Google Classroom assignments to API-created

This tool migrates UI-created Google Classroom assignments to API-created
assignments, enabling full API control over grades.

Commands:
    export    - Export quiz responses and grades to JSONL
    delete    - Delete existing assignments
    recreate  - Recreate assignments via API (associatedWithDeveloper: true)
    restore   - Restore grades from exported data

Usage:
    python migrate_assignments.py export [--course COURSE_ID] [--output FILE]
    python migrate_assignments.py delete --course COURSE_ID --assignment ASSIGNMENT_ID
    python migrate_assignments.py recreate --course COURSE_ID --from EXPORT_FILE
    python migrate_assignments.py restore --course COURSE_ID --from EXPORT_FILE

The migration workflow:
1. Run export to backup all quiz responses and grades
2. Run recreate to create new API-controlled assignments
3. Run restore to set grades on the new assignments
4. Verify grades, then delete the old assignments
"""

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / 'credentials.json'
TOKEN_PATH = PROJECT_ROOT / 'token_migration.pickle'
EXPORT_DIR = PROJECT_ROOT / 'migration_exports'

# Need all scopes for full migration
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/forms.responses.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly',
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


def get_all_courses(classroom_service):
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

    return courses


def get_coursework(classroom_service, course_id):
    """Get all coursework for a course."""
    coursework = []
    page_token = None

    while True:
        response = classroom_service.courses().courseWork().list(
            courseId=course_id,
            pageToken=page_token
        ).execute()

        coursework.extend(response.get('courseWork', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return coursework


def get_submissions(classroom_service, course_id, coursework_id):
    """Get all submissions for a coursework item."""
    submissions = []
    page_token = None

    while True:
        response = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=course_id,
            courseWorkId=coursework_id,
            pageToken=page_token
        ).execute()

        submissions.extend(response.get('studentSubmissions', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return submissions


def get_students(classroom_service, course_id):
    """Get all students in a course."""
    students = []
    page_token = None

    while True:
        response = classroom_service.courses().students().list(
            courseId=course_id,
            pageToken=page_token
        ).execute()

        students.extend(response.get('students', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return students


def extract_form_id(materials):
    """Extract Google Form ID from assignment materials."""
    if not materials:
        return None

    for material in materials:
        # Check for direct form attachment (most reliable)
        form = material.get('form', {})
        form_url = form.get('formUrl', '')
        if form_url and 'docs.google.com/forms' in form_url:
            parts = form_url.split('/d/')
            if len(parts) > 1:
                form_id = parts[1].split('/')[0]
                return form_id

        # Also check link materials (less common)
        link = material.get('link', {})
        url = link.get('url', '')

        # Check for Forms URL patterns
        if 'docs.google.com/forms' in url:
            # URLs like https://docs.google.com/forms/d/FORM_ID/viewform
            parts = url.split('/d/')
            if len(parts) > 1:
                form_id = parts[1].split('/')[0]
                return form_id

    return None


def get_form_responses(forms_service, form_id):
    """Get all responses for a Google Form."""
    try:
        responses = []
        page_token = None

        while True:
            response = forms_service.forms().responses().list(
                formId=form_id,
                pageToken=page_token
            ).execute()

            responses.extend(response.get('responses', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return responses
    except HttpError as e:
        print(f"    Error fetching form responses: {e.resp.status}")
        return []


def get_form_info(forms_service, form_id):
    """Get form metadata."""
    try:
        form = forms_service.forms().get(formId=form_id).execute()
        return form
    except HttpError as e:
        print(f"    Error fetching form info: {e.resp.status}")
        return None


def cmd_export(args, classroom_service, forms_service):
    """Export quiz data to JSONL."""
    print("=" * 70)
    print("EXPORT QUIZ DATA")
    print("=" * 70)

    EXPORT_DIR.mkdir(exist_ok=True)

    # Get courses
    if args.course:
        courses = [classroom_service.courses().get(id=args.course).execute()]
    else:
        courses = get_all_courses(classroom_service)

    print(f"\nFound {len(courses)} course(s)")

    export_data = []

    for course in courses:
        course_id = course['id']
        course_name = course['name']
        print(f"\n{'='*50}")
        print(f"Course: {course_name}")
        print(f"{'='*50}")

        # Get students for email mapping
        print("  Fetching students...")
        students = get_students(classroom_service, course_id)
        student_map = {}  # userId -> {name, email}
        for s in students:
            profile = s.get('profile', {})
            student_map[s['userId']] = {
                'name': profile.get('name', {}).get('fullName', 'Unknown'),
                'email': profile.get('emailAddress', '')
            }
        print(f"    {len(students)} students")

        # Get coursework
        print("  Fetching assignments...")
        coursework = get_coursework(classroom_service, course_id)
        print(f"    {len(coursework)} assignments")

        for cw in coursework:
            cw_id = cw['id']
            cw_title = cw['title']
            cw_type = cw.get('workType', 'ASSIGNMENT')
            max_points = cw.get('maxPoints', 0)
            associated_with_dev = cw.get('associatedWithDeveloper', False)

            # Extract form ID if present
            form_id = extract_form_id(cw.get('materials', []))

            print(f"\n  Assignment: {cw_title}")
            print(f"    Type: {cw_type}, Max Points: {max_points}")
            print(f"    API-controlled: {associated_with_dev}")

            # Skip if already API-controlled
            if associated_with_dev:
                print("    (Already API-controlled, skipping)")
                continue

            # Get submissions
            submissions = get_submissions(classroom_service, course_id, cw_id)

            assignment_data = {
                'course_id': course_id,
                'course_name': course_name,
                'coursework_id': cw_id,
                'title': cw_title,
                'description': cw.get('description', ''),
                'work_type': cw_type,
                'max_points': max_points,
                'state': cw.get('state', 'PUBLISHED'),
                'due_date': cw.get('dueDate'),
                'due_time': cw.get('dueTime'),
                'materials': cw.get('materials', []),
                'form_id': form_id,
                'submissions': [],
                'form_responses': [],
                'exported_at': datetime.now().isoformat()
            }

            # Export submissions
            for sub in submissions:
                student_id = sub['userId']
                student_info = student_map.get(student_id, {})

                sub_data = {
                    'submission_id': sub['id'],
                    'user_id': student_id,
                    'student_name': student_info.get('name', 'Unknown'),
                    'student_email': student_info.get('email', ''),
                    'state': sub.get('state', ''),
                    'assigned_grade': sub.get('assignedGrade'),
                    'draft_grade': sub.get('draftGrade'),
                    'late': sub.get('late', False),
                    'submission_history': sub.get('submissionHistory', [])
                }
                assignment_data['submissions'].append(sub_data)

            print(f"    Submissions: {len(submissions)}")

            # Get form responses if this is a quiz
            if form_id:
                print(f"    Form ID: {form_id}")
                form_info = get_form_info(forms_service, form_id)
                if form_info:
                    assignment_data['form_info'] = {
                        'title': form_info.get('info', {}).get('title', ''),
                        'document_title': form_info.get('info', {}).get('documentTitle', ''),
                        'responder_uri': form_info.get('responderUri', '')
                    }

                form_responses = get_form_responses(forms_service, form_id)
                assignment_data['form_responses'] = form_responses
                print(f"    Form responses: {len(form_responses)}")

            graded_count = len([s for s in submissions if s.get('assignedGrade') is not None])
            print(f"    Graded: {graded_count}/{len(submissions)}")

            export_data.append(assignment_data)

    # Write export file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = args.output or (EXPORT_DIR / f'quiz_export_{timestamp}.jsonl')
    output_file = Path(output_file)

    print(f"\n{'='*70}")
    print(f"Writing export to: {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        for item in export_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"Exported {len(export_data)} assignments")

    # Summary
    total_submissions = sum(len(a['submissions']) for a in export_data)
    total_graded = sum(
        len([s for s in a['submissions'] if s.get('assigned_grade') is not None])
        for a in export_data
    )
    total_form_responses = sum(len(a.get('form_responses', [])) for a in export_data)

    print(f"\nSUMMARY:")
    print(f"  Assignments: {len(export_data)}")
    print(f"  Total submissions: {total_submissions}")
    print(f"  Graded submissions: {total_graded}")
    print(f"  Form responses: {total_form_responses}")

    return output_file


def cmd_recreate(args, classroom_service, forms_service):
    """Recreate assignments via API."""
    print("=" * 70)
    print("RECREATE ASSIGNMENTS VIA API")
    print("=" * 70)

    if not args.input:
        print("ERROR: --from FILE required")
        return

    export_file = Path(args.input)
    if not export_file.exists():
        print(f"ERROR: Export file not found: {export_file}")
        return

    # Load export data
    assignments = []
    with open(export_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                assignments.append(json.loads(line))

    print(f"Loaded {len(assignments)} assignments from export")

    if args.course:
        assignments = [a for a in assignments if a['course_id'] == args.course]
        print(f"Filtered to {len(assignments)} assignments for course {args.course}")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    created = []

    for assignment in assignments:
        course_id = assignment['course_id']
        course_name = assignment['course_name']
        title = assignment['title']

        print(f"\n{course_name}: {title}")

        # Build the new coursework body
        # Use a past scheduledTime to prevent notifications
        body = {
            'title': title,
            'description': assignment.get('description', ''),
            'workType': assignment.get('work_type', 'ASSIGNMENT'),
            'state': 'PUBLISHED',  # Publish immediately
            # Setting scheduledTime to the past prevents notifications
            'scheduledTime': '2020-01-01T00:00:00Z',
        }

        if assignment.get('max_points'):
            body['maxPoints'] = assignment['max_points']

        if assignment.get('due_date'):
            body['dueDate'] = assignment['due_date']
        if assignment.get('due_time'):
            body['dueTime'] = assignment['due_time']

        # Copy materials (including form links)
        if assignment.get('materials'):
            body['materials'] = assignment['materials']

        if args.dry_run:
            print(f"  Would create: {title}")
            print(f"    workType: {body.get('workType')}")
            print(f"    maxPoints: {body.get('maxPoints')}")
            created.append({
                'old_id': assignment['coursework_id'],
                'new_id': 'DRY_RUN',
                'title': title,
                'course_id': course_id
            })
        else:
            try:
                result = classroom_service.courses().courseWork().create(
                    courseId=course_id,
                    body=body
                ).execute()

                print(f"  Created: {result['id']}")
                print(f"    associatedWithDeveloper: {result.get('associatedWithDeveloper', 'NOT SET')}")

                created.append({
                    'old_id': assignment['coursework_id'],
                    'new_id': result['id'],
                    'title': title,
                    'course_id': course_id
                })

            except HttpError as e:
                print(f"  ERROR: {e.resp.status} - {e.error_details}")

    # Save mapping file
    if created:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        mapping_file = EXPORT_DIR / f'id_mapping_{timestamp}.json'
        with open(mapping_file, 'w') as f:
            json.dump(created, f, indent=2)
        print(f"\nID mapping saved to: {mapping_file}")

    print(f"\nCreated {len(created)} assignments")


def cmd_restore(args, classroom_service, forms_service):
    """Restore grades from exported data."""
    print("=" * 70)
    print("RESTORE GRADES")
    print("=" * 70)

    if not args.input:
        print("ERROR: --from FILE required")
        return

    export_file = Path(args.input)
    if not export_file.exists():
        print(f"ERROR: Export file not found: {export_file}")
        return

    # Load export data
    assignments = []
    with open(export_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                assignments.append(json.loads(line))

    print(f"Loaded {len(assignments)} assignments from export")

    # Need mapping file to know new assignment IDs
    if not args.mapping:
        print("ERROR: --mapping FILE required (the id_mapping JSON from recreate)")
        return

    mapping_file = Path(args.mapping)
    if not mapping_file.exists():
        print(f"ERROR: Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, 'r') as f:
        id_mapping = json.load(f)

    # Build lookup: old_id -> new_id
    old_to_new = {m['old_id']: m['new_id'] for m in id_mapping}
    print(f"Loaded {len(old_to_new)} ID mappings")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    restored_count = 0
    error_count = 0

    for assignment in assignments:
        old_id = assignment['coursework_id']
        new_id = old_to_new.get(old_id)

        if not new_id or new_id == 'DRY_RUN':
            print(f"\nSkipping {assignment['title']}: no mapping found")
            continue

        course_id = assignment['course_id']
        title = assignment['title']

        print(f"\n{assignment['course_name']}: {title}")
        print(f"  Old ID: {old_id}")
        print(f"  New ID: {new_id}")

        # Get current submissions for new assignment
        new_submissions = get_submissions(classroom_service, course_id, new_id)
        new_sub_by_user = {s['userId']: s for s in new_submissions}

        # Restore grades from old submissions
        for old_sub in assignment['submissions']:
            user_id = old_sub['user_id']
            assigned_grade = old_sub.get('assigned_grade')
            draft_grade = old_sub.get('draft_grade')

            if assigned_grade is None and draft_grade is None:
                continue  # No grade to restore

            new_sub = new_sub_by_user.get(user_id)
            if not new_sub:
                print(f"    {old_sub['student_name']}: not found in new assignment")
                continue

            grade_to_set = assigned_grade if assigned_grade is not None else draft_grade

            if args.dry_run:
                print(f"    {old_sub['student_name']}: would set grade to {grade_to_set}")
                restored_count += 1
            else:
                try:
                    update_body = {}
                    update_mask = []

                    if assigned_grade is not None:
                        update_body['assignedGrade'] = assigned_grade
                        update_mask.append('assignedGrade')
                    if draft_grade is not None:
                        update_body['draftGrade'] = draft_grade
                        update_mask.append('draftGrade')

                    classroom_service.courses().courseWork().studentSubmissions().patch(
                        courseId=course_id,
                        courseWorkId=new_id,
                        id=new_sub['id'],
                        updateMask=','.join(update_mask),
                        body=update_body
                    ).execute()

                    print(f"    {old_sub['student_name']}: grade set to {grade_to_set}")
                    restored_count += 1

                except HttpError as e:
                    print(f"    {old_sub['student_name']}: ERROR {e.resp.status}")
                    error_count += 1

    print(f"\n{'='*70}")
    print(f"Restored {restored_count} grades")
    if error_count:
        print(f"Errors: {error_count}")


def cmd_grade(args, classroom_service, forms_service):
    """Grade assignments from form responses."""
    print("=" * 70)
    print("GRADE FROM FORM RESPONSES")
    print("=" * 70)

    if not args.input:
        print("ERROR: --from FILE required")
        return

    export_file = Path(args.input)
    if not export_file.exists():
        print(f"ERROR: Export file not found: {export_file}")
        return

    # Load export data
    assignments = []
    with open(export_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                assignments.append(json.loads(line))

    print(f"Loaded {len(assignments)} assignments from export")

    # Filter to assignments with form responses
    assignments = [a for a in assignments if a.get('form_responses')]
    print(f"Found {len(assignments)} assignments with form responses")

    if args.course:
        assignments = [a for a in assignments if a['course_id'] == args.course]
        print(f"Filtered to {len(assignments)} for course {args.course}")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    graded_count = 0
    error_count = 0
    skipped_count = 0

    for assignment in assignments:
        course_id = assignment['course_id']
        coursework_id = assignment['coursework_id']
        title = assignment['title']
        max_points = assignment.get('max_points', 100)
        form_responses = assignment.get('form_responses', [])

        print(f"\n{assignment['course_name']}: {title}")
        print(f"  Coursework ID: {coursework_id}")
        print(f"  Max Points: {max_points}")
        print(f"  Form responses: {len(form_responses)}")

        # Build email -> score mapping from form responses
        email_to_score = {}
        for resp in form_responses:
            email = resp.get('respondentEmail', '').lower()
            if not email:
                continue

            # Calculate total score from individual answers
            answers = resp.get('answers', {})
            total_correct = sum(
                ans.get('grade', {}).get('score', 0)
                for ans in answers.values()
            )
            total_questions = len(answers)

            # Scale to max_points
            if total_questions > 0:
                score = round((total_correct / total_questions) * max_points, 1)
            else:
                score = 0

            email_to_score[email] = {
                'score': score,
                'correct': total_correct,
                'total': total_questions
            }

        print(f"  Email->Score mappings: {len(email_to_score)}")

        # Get current submissions
        submissions = get_submissions(classroom_service, course_id, coursework_id)

        # Get student emails
        students = get_students(classroom_service, course_id)
        user_to_email = {}
        for s in students:
            profile = s.get('profile', {})
            email = profile.get('emailAddress', '').lower()
            if email:
                user_to_email[s['userId']] = email

        # Match and grade
        for sub in submissions:
            user_id = sub['userId']
            student_email = user_to_email.get(user_id, '').lower()
            sub_id = sub['id']
            current_grade = sub.get('assignedGrade')

            # Skip if already graded
            if current_grade is not None and not args.force:
                skipped_count += 1
                continue

            # Find score by email
            score_info = email_to_score.get(student_email)
            if not score_info:
                continue

            score = score_info['score']

            if args.dry_run:
                print(f"    {student_email}: would set grade to {score} ({score_info['correct']}/{score_info['total']})")
                graded_count += 1
            else:
                try:
                    classroom_service.courses().courseWork().studentSubmissions().patch(
                        courseId=course_id,
                        courseWorkId=coursework_id,
                        id=sub_id,
                        updateMask='assignedGrade,draftGrade',
                        body={
                            'assignedGrade': score,
                            'draftGrade': score
                        }
                    ).execute()

                    print(f"    {student_email}: grade set to {score} ({score_info['correct']}/{score_info['total']})")
                    graded_count += 1

                except HttpError as e:
                    print(f"    {student_email}: ERROR {e.resp.status}")
                    error_count += 1

    print(f"\n{'='*70}")
    print(f"Graded {graded_count} submissions")
    if error_count:
        print(f"Errors: {error_count}")
    if skipped_count:
        print(f"Skipped (already graded): {skipped_count}")


def cmd_delete_all(args, classroom_service, forms_service):
    """Delete all assignments from courses matching pattern."""
    # DISABLED: This command requires explicit human instruction
    print("=" * 70)
    print("COMMAND DISABLED")
    print("=" * 70)
    print("\nERROR: Do not implement or run delete-all without clear explicit")
    print("instruction from a human prompter.")
    print("\nThis command has been disabled for safety. If you need to delete")
    print("assignments, use the browser automation script instead:")
    print("  python scripts/delete_assignments_browser.py")
    return

    # Original implementation below (disabled)
    print("=" * 70)
    print("DELETE ALL ASSIGNMENTS")
    print("=" * 70)

    # Get all courses
    courses = get_all_courses(classroom_service)
    print(f"\nFound {len(courses)} courses")

    # Filter courses by pattern (periods 1-8)
    target_courses = []
    for course in courses:
        name = course['name']
        # Match courses like "1 Instructional...", "2 Communications...", etc.
        if any(name.startswith(f"{i} ") for i in range(1, 9)):
            target_courses.append(course)

    print(f"Matched {len(target_courses)} courses (periods 1-8):")
    for c in target_courses:
        print(f"  - {c['name']}")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    total_deleted = 0
    total_errors = 0

    for course in target_courses:
        course_id = course['id']
        course_name = course['name']
        print(f"\n{'='*50}")
        print(f"Course: {course_name}")

        # Get all coursework
        coursework = get_coursework(classroom_service, course_id)
        print(f"  Found {len(coursework)} assignments")

        for cw in coursework:
            cw_id = cw['id']
            cw_title = cw['title']

            if args.dry_run:
                print(f"    Would delete: {cw_title}")
                total_deleted += 1
            else:
                try:
                    classroom_service.courses().courseWork().delete(
                        courseId=course_id,
                        id=cw_id
                    ).execute()
                    print(f"    Deleted: {cw_title}")
                    total_deleted += 1
                except HttpError as e:
                    print(f"    ERROR deleting {cw_title}: {e.resp.status}")
                    total_errors += 1

    print(f"\n{'='*70}")
    print(f"{'Would delete' if args.dry_run else 'Deleted'} {total_deleted} assignments")
    if total_errors:
        print(f"Errors: {total_errors}")


def cmd_delete(args, classroom_service, forms_service):
    """Delete an assignment."""
    print("=" * 70)
    print("DELETE ASSIGNMENT")
    print("=" * 70)

    if not args.course or not args.assignment:
        print("ERROR: --course and --assignment required")
        return

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    try:
        # Get assignment info first
        cw = classroom_service.courses().courseWork().get(
            courseId=args.course,
            id=args.assignment
        ).execute()

        print(f"Assignment: {cw['title']}")
        print(f"  ID: {cw['id']}")
        print(f"  Course: {args.course}")

        if args.dry_run:
            print("\n  Would delete this assignment")
        else:
            confirm = input("\nType 'DELETE' to confirm: ")
            if confirm != 'DELETE':
                print("Cancelled")
                return

            classroom_service.courses().courseWork().delete(
                courseId=args.course,
                id=args.assignment
            ).execute()
            print("Deleted!")

    except HttpError as e:
        print(f"ERROR: {e.resp.status} - {e.error_details}")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Google Classroom assignments to API-controlled',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export quiz data to JSONL')
    export_parser.add_argument('--course', help='Specific course ID (optional)')
    export_parser.add_argument('--output', '-o', help='Output file path')

    # Recreate command
    recreate_parser = subparsers.add_parser('recreate', help='Recreate assignments via API')
    recreate_parser.add_argument('--from', dest='input', required=True, help='Export JSONL file')
    recreate_parser.add_argument('--course', help='Specific course ID (optional)')
    recreate_parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore grades from export')
    restore_parser.add_argument('--from', dest='input', required=True, help='Export JSONL file')
    restore_parser.add_argument('--mapping', required=True, help='ID mapping JSON from recreate')
    restore_parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    # Grade command
    grade_parser = subparsers.add_parser('grade', help='Grade assignments from form responses')
    grade_parser.add_argument('--from', dest='input', required=True, help='Export JSONL file')
    grade_parser.add_argument('--course', help='Specific course ID (optional)')
    grade_parser.add_argument('--force', action='store_true', help='Re-grade already graded submissions')
    grade_parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    # Delete-all command
    delete_all_parser = subparsers.add_parser('delete-all', help='Delete all assignments from periods 1-8')
    delete_all_parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete an assignment')
    delete_parser.add_argument('--course', required=True, help='Course ID')
    delete_parser.add_argument('--assignment', required=True, help='Assignment ID to delete')
    delete_parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Authenticate
    print("Authenticating...")
    creds = get_credentials()
    if not creds:
        print("Authentication failed")
        sys.exit(1)

    classroom_service = build('classroom', 'v1', credentials=creds)
    forms_service = build('forms', 'v1', credentials=creds)

    # Run command
    if args.command == 'export':
        cmd_export(args, classroom_service, forms_service)
    elif args.command == 'recreate':
        cmd_recreate(args, classroom_service, forms_service)
    elif args.command == 'restore':
        cmd_restore(args, classroom_service, forms_service)
    elif args.command == 'grade':
        cmd_grade(args, classroom_service, forms_service)
    elif args.command == 'delete-all':
        cmd_delete_all(args, classroom_service, forms_service)
    elif args.command == 'delete':
        cmd_delete(args, classroom_service, forms_service)


if __name__ == '__main__':
    main()
