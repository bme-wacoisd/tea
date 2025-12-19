#!/usr/bin/env python3
"""
delete_assignments_browser.py - Delete Google Classroom assignments via browser automation

This script uses Playwright to automate deleting assignments through the Google Classroom UI.
It targets periods 1-8 only, excluding the Lovelace classes.

Usage:
    python delete_assignments_browser.py [--dry-run]

The script will:
1. Open Chrome with your existing profile (if available)
2. Navigate to each course's classwork page
3. Click the 3-dot menu on each assignment and select Delete
4. Confirm deletion

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import asyncio
import base64
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# Course IDs for periods 1-8 (excluding Lovelace classes)
# These are the courses that start with "1 ", "2 ", etc.
TARGET_COURSES = [
    {"id": "835749845545", "name": "8 Communications and Technology"},
    {"id": "835750566498", "name": "7 Instructional Practices & Practicum"},
    {"id": "835399949498", "name": "6 Communications and Technology"},
    {"id": "835400459498", "name": "5 Instructional Practices & Practicum"},
    {"id": "835399531473", "name": "4 Communications and Technology"},
    {"id": "835399786685", "name": "2 Communications and Technology"},
    {"id": "835400285918", "name": "3 Instructional Practices & Practicum"},
    {"id": "835400632498", "name": "1 Instructional Practices & Practicum"},
]


async def delete_assignments_in_course(page, course_id: str, course_name: str, dry_run: bool) -> tuple[int, int]:
    """Delete all assignments in a course. Returns (deleted_count, error_count)."""
    deleted = 0
    errors = 0

    # Navigate to course classwork page
    url = f"https://classroom.google.com/w/{course_id}/t/all"
    print(f"\n  Navigating to: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)  # Wait for page to stabilize
    except PlaywrightTimeout:
        print(f"  ERROR: Timeout loading course page")
        return 0, 1

    # Keep deleting until no more assignments
    while True:
        # Find all assignment elements with 3-dot menus
        # The 3-dot menu button is typically in the assignment card
        menu_buttons = await page.query_selector_all('button[aria-label="More options"], button[aria-label="More actions"], [data-tooltip="More options"]')

        if not menu_buttons:
            # Try alternative selectors
            menu_buttons = await page.query_selector_all('.VfPpkd-kBDsod[aria-label*="More"], .U26fgb[aria-label*="options"]')

        if not menu_buttons:
            print(f"  No more assignments found")
            break

        print(f"  Found {len(menu_buttons)} menu buttons")

        # Click the first menu button (we delete one at a time since the DOM changes)
        try:
            menu_button = menu_buttons[0]

            # Get assignment name if possible
            parent = await menu_button.evaluate_handle('el => el.closest("[data-stream-item-id]") || el.closest(".cC2uM")')
            assignment_name = "Unknown"
            try:
                name_el = await parent.query_selector('.YVvGBb, .onkcGd, .asQXV')
                if name_el:
                    assignment_name = await name_el.inner_text()
            except:
                pass

            if dry_run:
                print(f"    Would delete: {assignment_name}")
                deleted += 1
                # In dry run, we need to skip this element somehow
                # Since we can't actually track which ones we've "processed", just break after counting
                break
            else:
                print(f"    Deleting: {assignment_name}")

                # Click the 3-dot menu
                await menu_button.click()
                await page.wait_for_timeout(500)

                # Look for Delete option in the menu
                delete_option = await page.query_selector('text="Delete"')
                if not delete_option:
                    delete_option = await page.query_selector('[role="menuitem"]:has-text("Delete")')

                if not delete_option:
                    print(f"      Could not find Delete option")
                    errors += 1
                    # Press Escape to close menu
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
                    continue

                # Click Delete
                await delete_option.click()
                await page.wait_for_timeout(500)

                # Confirm deletion in dialog
                confirm_button = await page.query_selector('button:has-text("Delete")')
                if confirm_button:
                    await confirm_button.click()
                    await page.wait_for_timeout(1500)  # Wait for deletion to complete
                    print(f"      Deleted!")
                    deleted += 1
                else:
                    print(f"      Could not find confirmation button")
                    errors += 1
                    await page.keyboard.press("Escape")

        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1
            try:
                await page.keyboard.press("Escape")
            except:
                pass

    return deleted, errors


async def main(dry_run: bool):
    print("=" * 70)
    print("DELETE ASSIGNMENTS VIA BROWSER AUTOMATION")
    print("=" * 70)

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***")

    print(f"\nTarget courses (periods 1-8, excluding Lovelace):")
    for course in TARGET_COURSES:
        print(f"  - {course['name']}")

    async with async_playwright() as p:
        # Try to use existing Chrome profile
        chrome_path = Path.home() / "AppData/Local/Google/Chrome/User Data"
        browser = None
        context = None

        print("\nLaunching browser...")

        try:
            # Try with existing profile first
            if chrome_path.exists():
                print("  Attempting to use existing Chrome profile...")
                context = await p.chromium.launch_persistent_context(
                    str(chrome_path),
                    channel="chrome",
                    headless=False,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                    slow_mo=100,
                )
                page = context.pages[0] if context.pages else await context.new_page()
            else:
                raise Exception("Chrome profile not found")
        except Exception as e:
            print(f"  Could not use Chrome profile: {e}")
            print("  Using Playwright browser (will need login)...")
            browser = await p.chromium.launch(headless=False, slow_mo=100)
            context = await browser.new_context()
            page = await context.new_page()

        # Navigate to Classroom to check login
        print("\nChecking login status...")
        await page.goto("https://classroom.google.com", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        current_url = page.url
        print(f"  Current URL: {current_url}")

        # Check if we need to log in
        if "accounts.google.com" in current_url or "edu.google.com" in current_url:
            print("\n" + "=" * 60)
            print("GOOGLE LOGIN REQUIRED")
            print("=" * 60)
            print("\nPlease log in to your Google account in the browser window.")
            print("The script will continue automatically after login.")
            print("\nWaiting for login (up to 5 minutes)...")

            try:
                await page.wait_for_url("**/classroom.google.com/**", timeout=300000)
                print("Login successful!")
            except PlaywrightTimeout:
                print("ERROR: Login timed out after 5 minutes")
                if browser:
                    await browser.close()
                elif context:
                    await context.close()
                return

        # Process each course
        total_deleted = 0
        total_errors = 0

        for course in TARGET_COURSES:
            print(f"\n{'='*60}")
            print(f"Course: {course['name']}")
            print(f"{'='*60}")

            deleted, errors = await delete_assignments_in_course(
                page, course['id'], course['name'], dry_run
            )
            total_deleted += deleted
            total_errors += errors

        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"{'Would delete' if dry_run else 'Deleted'}: {total_deleted} assignments")
        if total_errors:
            print(f"Errors: {total_errors}")

        # Close browser
        print("\nClosing browser...")
        if browser:
            await browser.close()
        elif context:
            await context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete Google Classroom assignments via browser automation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    args = parser.parse_args()

    asyncio.run(main(args.dry_run))
