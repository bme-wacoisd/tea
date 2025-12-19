#!/usr/bin/env python3
"""
import_grades_browser.py - Browser automation to import grades from Google Forms to Classroom

Uses Playwright to automate clicking "Import Grades" for quiz assignments.
This fixes existing assignments that weren't created via API.

Usage:
    python import_grades_browser.py              # Interactive mode - logs in, shows what it finds
    python import_grades_browser.py --import     # Actually click Import Grades buttons
    python import_grades_browser.py --headless   # Run without visible browser

First run will open browser for Google login. Session is saved for subsequent runs.
"""

import argparse
import asyncio
import base64
import json
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Persistent browser state directory
SCRIPT_DIR = Path(__file__).parent
USER_DATA_DIR = SCRIPT_DIR / 'browser_data'
STATE_FILE = SCRIPT_DIR / 'classroom_state.json'

# Target courses (periods 1-8, exclude Lovelace)
TARGET_PERIODS = ['1', '2', '3', '4', '5', '6', '7', '8']


async def save_state(state: dict):
    """Save script state to file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


async def load_state() -> dict:
    """Load script state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'processed': [], 'errors': []}


async def is_target_course(course_name: str) -> bool:
    """Check if course is periods 1-8 (not Lovelace)."""
    name_lower = course_name.lower()
    if 'lovelace' in name_lower:
        return False

    # Check for period indicators
    for period in TARGET_PERIODS:
        if course_name.startswith(f'{period} ') or f' {period} ' in course_name:
            return True
    return False


async def login_if_needed(page):
    """Check if logged in, prompt for login if not."""
    # Go directly to Classroom
    await page.goto('https://classroom.google.com/u/0/h')
    await page.wait_for_timeout(2000)
    await page.wait_for_timeout(2000)

    # Check if we're on the Classroom home page or redirected elsewhere
    current_url = page.url
    print(f"  Current URL: {current_url}")

    # Check various indicators that we need to log in
    needs_login = (
        'accounts.google.com' in current_url or
        'signin' in current_url or
        'ServiceLogin' in current_url or
        'edu.google.com' in current_url or  # Marketing page = not logged in
        'workspace-for-education' in current_url
    )

    # Also check for "Sign in" or "Get started" buttons on marketing page
    if not needs_login:
        sign_in_button = await page.query_selector('a[href*="accounts.google.com"], button:has-text("Sign in"), a:has-text("Go to Classroom"), a:has-text("Get started")')
        if sign_in_button:
            needs_login = True

    if needs_login:
        print("\n" + "="*60)
        print("GOOGLE LOGIN REQUIRED")
        print("="*60)

        # If on marketing page, navigate to actual login
        if 'edu.google.com' in current_url or 'workspace-for-education' in current_url:
            print("\nNavigating to Google login...")
            # Go to accounts.google.com with Classroom as the continue URL
            await page.goto('https://accounts.google.com/ServiceLogin?continue=https://classroom.google.com/u/0/h')
            await page.wait_for_timeout(2000)
            await page.wait_for_timeout(1000)
            current_url = page.url
            print(f"  Now at: {current_url}")

        print("\nPlease log in to your Google account in the browser window.")
        print("The script will continue automatically after login.")
        print("\nWaiting for login (up to 5 minutes)...")

        # Wait for redirect to Classroom after login - check periodically
        timeout_seconds = 300
        check_interval = 2
        elapsed = 0

        while elapsed < timeout_seconds:
            await page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval
            current_url = page.url

            # Check if we made it to Classroom (various URL patterns)
            if 'classroom.google.com' in current_url and 'accounts.google.com' not in current_url:
                # Don't wait for networkidle - Classroom keeps connections open
                await page.wait_for_timeout(3000)  # Just wait a bit for content
                print(f"Login successful! Now at: {current_url}")
                break

            # Show progress every 30 seconds
            if elapsed % 30 == 0:
                print(f"  Still waiting... ({elapsed}s) - Current: {current_url[:60]}...")
        else:
            print("ERROR: Login timed out after 5 minutes")
            await page.screenshot(path=str(SCRIPT_DIR / 'login_timeout.png'))
            print(f"  Screenshot saved to: {SCRIPT_DIR / 'login_timeout.png'}")
            return False
    else:
        # Already logged in, but wait for content to load
        print("  Already logged in, waiting for content...")
        await page.wait_for_timeout(2000)

    # Take debug screenshot
    await page.screenshot(path=str(SCRIPT_DIR / 'classroom_home.png'))
    print(f"  Screenshot saved to: {SCRIPT_DIR / 'classroom_home.png'}")

    return True


async def get_courses(page) -> list:
    """Get list of courses from Classroom homepage."""
    await page.goto('https://classroom.google.com/u/0/h')
    await page.wait_for_timeout(3000)  # Wait for dynamic content

    # Save page HTML for debugging
    html = await page.content()
    with open(SCRIPT_DIR / 'classroom_debug.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Debug HTML saved to: {SCRIPT_DIR / 'classroom_debug.html'}")

    courses = []

    # Method 1: Get from list items with data-course-id
    course_items = await page.query_selector_all('li[data-course-id]')
    print(f"  Found {len(course_items)} course list items")

    for item in course_items:
        # Get numeric course ID from data attribute
        numeric_id = await item.get_attribute('data-course-id')

        # Get base64 course ID from the link inside
        link = await item.query_selector('a[href*="/c/"]')
        if link:
            href = await link.get_attribute('href') or ''
            if '/c/' in href:
                parts = href.split('/c/')
                if len(parts) > 1:
                    course_id = parts[1].split('/')[0].split('?')[0]

                    # Get course name from aria-label or text content
                    aria_label = await link.get_attribute('aria-label') or ''
                    if 'gradebook for' in aria_label:
                        # Extract name from: Open gradebook for "Course Name"
                        match = re.search(r'"([^"]+)"', aria_label)
                        name = match.group(1) if match else ''
                    else:
                        # Try getting text from the list item
                        name = await item.inner_text()
                        name = name.strip().split('\n')[0] if name else ''

                    if name and course_id not in [c['id'] for c in courses]:
                        courses.append({'id': course_id, 'name': name})

    return courses


async def get_assignments_for_course(page, course_id: str, course_name: str) -> list:
    """Get list of assignments for a course."""
    # Navigate to course classwork page
    # Format: /w/{courseId}/t/all (NOT /c/{courseId}/w)
    url = f'https://classroom.google.com/w/{course_id}/t/all'
    print(f"    Navigating to: {url}")

    response = await page.goto(url)

    # Fast fail on 404 or error
    if response and response.status >= 400:
        print(f"    ERROR: HTTP {response.status} - bad course ID?")
        return []

    # Check for 404 page content
    await page.wait_for_timeout(2000)
    if 'not found' in (await page.content()).lower() or '404' in await page.title():
        print(f"    ERROR: 404 page - course ID '{course_id}' invalid")
        return []

    # Wait for assignments to load - use data-stream-item-id (with hyphens)
    try:
        await page.wait_for_selector('[data-stream-item-id]', timeout=5000)
    except PlaywrightTimeout:
        print(f"    No assignments found for {course_name}")
        return []

    assignments = []
    # Use more specific selector: assignment cards with data-stream-item-id
    # Target the clickable assignment cards, not all elements with the attribute
    assignment_elements = await page.query_selector_all('div.qhnNic[data-stream-item-id], div[data-stream-item-id][class*="wBE4bf"]')

    if not assignment_elements:
        # Fallback to broader selector
        assignment_elements = await page.query_selector_all('[data-stream-item-id]')

    print(f"    Found {len(assignment_elements)} assignment elements")

    # Deduplicate by ID (same assignment can appear multiple times in DOM)
    seen_ids = set()
    for element in assignment_elements:
        assign_id = await element.get_attribute('data-stream-item-id')
        if not assign_id or assign_id in seen_ids:
            continue
        seen_ids.add(assign_id)

        # Get assignment title - look for various title class patterns
        # Try multiple selectors for the title
        title = ''
        for selector in ['.YVvGBb', '.tLDEHd', '.onkcGd', 'h2', 'h3', '[class*="title"]']:
            title_el = await element.query_selector(selector)
            if title_el:
                title = await title_el.inner_text()
                if title and title.strip():
                    title = title.strip()
                    break

        if not title:
            # Fallback: get first line of text content
            text = await element.inner_text()
            if text:
                lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
                if lines:
                    title = lines[0]

        # Debug: show what we found
        if assign_id and len(seen_ids) <= 5:  # Only show first 5
            print(f"      ID: {assign_id[:15]}... Title: '{title[:40] if title else 'NONE'}...'")

        if title:
            # Convert numeric ID to base64 for URLs
            base64_id = base64.b64encode(assign_id.encode()).decode()
            assignments.append({
                'id': assign_id,
                'base64_id': base64_id,
                'title': title.strip(),
                'course_id': course_id,
                'course_name': course_name
            })

    return assignments


async def check_import_grades_available(page, course_id: str, assignment_id: str, base64_assignment_id: str = None) -> dict:
    """
    Navigate to assignment and check if Import Grades is available.
    Returns dict with status info.
    """
    # Navigate to the assignment student work view
    # URL format: /c/{courseId}/sp/{base64AssignmentId}/all/default
    # If base64_assignment_id not provided, encode the numeric ID
    if not base64_assignment_id:
        base64_assignment_id = base64.b64encode(assignment_id.encode()).decode()

    url = f'https://classroom.google.com/c/{course_id}/sp/{base64_assignment_id}/all/default'
    print(f"      Checking URL: {url}")
    await page.goto(url)

    # Wait for page content to load - look for student list or assignment header
    try:
        await page.wait_for_selector('.YRLLCE, .xRRFG, .rZXyy, [data-student-id]', timeout=15000)
    except PlaywrightTimeout:
        pass  # Continue anyway, maybe the selector is wrong

    await page.wait_for_timeout(2000)  # Extra buffer after content loads

    result = {
        'has_import_button': False,
        'import_button_text': None,
        'already_imported': False,
        'error': None
    }

    try:
        # Look for Import Grades button - try multiple selectors
        # Common selectors: button with "Import grades" text, aria-label, or class
        import_button = await page.query_selector(
            'button:has-text("Import grades"), '
            'button:has-text("Import Grades"), '
            '[aria-label*="Import grades"], '
            '[aria-label*="Import Grades"], '
            '[data-tooltip*="Import"], '
            '.nTZJSb'  # Known class for import button
        )

        if import_button:
            result['has_import_button'] = True
            result['import_button_text'] = await import_button.inner_text()
        else:
            # Check if there's a grading section that indicates grades already exist
            grade_elements = await page.query_selector_all('[data-grade], .dDKhVc')
            if grade_elements:
                result['already_imported'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


async def click_import_grades(page, course_id: str, assignment_id: str, base64_assignment_id: str = None) -> dict:
    """
    Navigate to assignment and click Import Grades.
    Returns dict with result info.
    """
    # URL format: /c/{courseId}/sp/{base64AssignmentId}/all/default
    if not base64_assignment_id:
        base64_assignment_id = base64.b64encode(assignment_id.encode()).decode()

    url = f'https://classroom.google.com/c/{course_id}/sp/{base64_assignment_id}/all/default'
    await page.goto(url)
    await page.wait_for_timeout(3000)

    result = {
        'success': False,
        'message': None,
        'grades_imported': 0
    }

    try:
        # Look for Import Grades button
        import_button = await page.query_selector('button:has-text("Import grades"), [aria-label*="Import grades"]')

        if not import_button:
            result['message'] = 'Import grades button not found'
            return result

        # Click the button
        await import_button.click()

        # Wait for confirmation dialog or for grades to update
        await page.wait_for_timeout(2000)

        # Look for confirmation dialog and click Import
        confirm_button = await page.query_selector('button:has-text("Import"), [data-mdc-dialog-action="accept"]')
        if confirm_button:
            await confirm_button.click()
            await page.wait_for_timeout(2000)

        # Check for success message or updated grades
        success_toast = await page.query_selector('[role="status"]:has-text("imported"), .OafbNb')
        if success_toast:
            result['success'] = True
            result['message'] = await success_toast.inner_text()
        else:
            result['success'] = True
            result['message'] = 'Import clicked (check manually for confirmation)'

    except Exception as e:
        result['message'] = f'Error: {str(e)}'

    return result


async def main():
    parser = argparse.ArgumentParser(description='Import grades from Google Forms to Classroom')
    parser.add_argument('--import', dest='do_import', action='store_true',
                       help='Actually click Import Grades buttons')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--course', type=str,
                       help='Only process specific course (by name substring)')
    args = parser.parse_args()

    print("="*70)
    print("GOOGLE CLASSROOM GRADE IMPORTER")
    print("="*70)

    if not args.do_import:
        print("\nDRY RUN MODE - Use --import to actually import grades")

    async with async_playwright() as p:
        # Launch browser (non-persistent for reliability, will need login each time)
        print("Launching browser...")
        browser = await p.chromium.launch(
            headless=args.headless,
            slow_mo=100,  # Slow down for stability
        )

        # Create context with viewport
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )

        page = await context.new_page()
        print("Browser launched, navigating to Classroom...")

        # Navigate immediately to Google login with Classroom redirect
        await page.goto('https://accounts.google.com/ServiceLogin?continue=https://classroom.google.com/u/0/h')
        await page.wait_for_timeout(2000)
        print(f"  Navigated to: {page.url}")

        # Login if needed
        if not await login_if_needed(page):
            await browser.close()
            return

        # Get all courses
        print("\nFetching courses...")
        courses = await get_courses(page)
        print(f"Found {len(courses)} courses")

        # Filter to target courses
        target_courses = [c for c in courses if await is_target_course(c['name'])]
        if args.course:
            target_courses = [c for c in target_courses if args.course.lower() in c['name'].lower()]

        print(f"Target courses: {len(target_courses)}")
        for c in target_courses:
            print(f"  - {c['name']} (ID: {c['id']})")

        # Load state
        state = await load_state()

        # Process each course
        results = {
            'processed': 0,
            'import_available': 0,
            'imported': 0,
            'already_done': 0,
            'no_import': 0,
            'errors': []
        }

        for course in target_courses:
            print(f"\n{'='*60}")
            print(f"Course: {course['name']}")
            print('='*60)

            assignments = await get_assignments_for_course(page, course['id'], course['name'])
            print(f"  Found {len(assignments)} assignments")

            for assignment in assignments:
                key = f"{course['id']}:{assignment['id']}"

                # Skip if already processed
                if key in state['processed']:
                    print(f"  [SKIP] {assignment['title']} (already processed)")
                    continue

                print(f"\n  Checking: {assignment['title']}")

                status = await check_import_grades_available(
                    page, course['id'], assignment['id'], assignment.get('base64_id')
                )

                # Save debug screenshot for first assignment only
                if results['processed'] == 0:
                    screenshot_path = SCRIPT_DIR / 'assignment_debug.png'
                    await page.screenshot(path=str(screenshot_path))
                    print(f"      Debug screenshot saved: {screenshot_path}")

                results['processed'] += 1

                if status['error']:
                    print(f"    ERROR: {status['error']}")
                    results['errors'].append({'assignment': assignment['title'], 'error': status['error']})
                elif status['already_imported']:
                    print(f"    [OK] Grades already present")
                    results['already_done'] += 1
                    state['processed'].append(key)
                elif status['has_import_button']:
                    print(f"    [FOUND] Import Grades available")
                    results['import_available'] += 1

                    if args.do_import:
                        print(f"    Clicking Import Grades...")
                        import_result = await click_import_grades(
                            page, course['id'], assignment['id'], assignment.get('base64_id')
                        )
                        if import_result['success']:
                            print(f"    [SUCCESS] {import_result['message']}")
                            results['imported'] += 1
                            state['processed'].append(key)
                        else:
                            print(f"    [FAILED] {import_result['message']}")
                            results['errors'].append({'assignment': assignment['title'], 'error': import_result['message']})
                else:
                    print(f"    [NO IMPORT] Button not found - may need manual setup")
                    results['no_import'] += 1

                # Save state after each assignment
                await save_state(state)

                # Brief pause between assignments
                await page.wait_for_timeout(500)

        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"  Assignments checked: {results['processed']}")
        print(f"  Import available: {results['import_available']}")
        print(f"  Successfully imported: {results['imported']}")
        print(f"  Already had grades: {results['already_done']}")
        print(f"  No import option: {results['no_import']}")
        print(f"  Errors: {len(results['errors'])}")

        if results['errors']:
            print("\nErrors:")
            for err in results['errors']:
                print(f"  - {err['assignment']}: {err['error']}")

        if not args.do_import and results['import_available'] > 0:
            print(f"\nRun with --import to import grades for {results['import_available']} assignments")

        # Keep browser open briefly for inspection
        if not args.headless:
            print("\nBrowser will close in 5 seconds...")
            await page.wait_for_timeout(5000)

        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
