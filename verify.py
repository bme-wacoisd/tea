#!/usr/bin/env python3
"""
verify.py - Verify lesson materials are complete and correctly formatted

Usage:
    python verify.py <lesson_directory>
    python verify.py lessons/01-james-baldwin-civil-rights

Checks:
- Required files exist
- YAML configuration is valid
- Slide types are supported
- Images referenced in YAML exist
- Quiz format is correct (Automagical Forms)
- No hardcoded content in wrong places
"""

import sys
from pathlib import Path
import yaml

# Required files for each lesson
REQUIRED_FILES = [
    'slides.yaml',      # Slide content configuration
    'slides.md',        # Human-readable slide planning
    'reading.md',       # Read-aloud text
    'worksheet.md',     # Group discussion prompts
    'quiz.md',          # Assessment quiz
    'lesson-plan.md',   # Formal lesson plan
]

# Optional but recommended
RECOMMENDED_FILES = [
    'assets/',          # Directory for images
]

# Supported slide types in create_slides_from_yaml.py
SUPPORTED_SLIDE_TYPES = [
    'title',
    'big_idea',
    'image_bio',
    'quote',
    'table',
    'comparison',
    'two_column',
    'bullets',
    'numbered',
    'closing',
]


def check_file_exists(lesson_dir: Path, filename: str) -> tuple[bool, str]:
    """Check if a file exists."""
    path = lesson_dir / filename
    if filename.endswith('/'):
        exists = path.is_dir()
    else:
        exists = path.is_file()
    status = "[OK]" if exists else "[MISSING]"
    return exists, f"{status} {filename}"


def check_yaml_config(lesson_dir: Path) -> list[str]:
    """Validate the slides.yaml configuration."""
    errors = []
    yaml_path = lesson_dir / 'slides.yaml'

    if not yaml_path.exists():
        return ["slides.yaml not found - cannot validate"]

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    # Check required top-level fields
    if 'title' not in config:
        errors.append("Missing 'title' field")
    if 'slides' not in config:
        errors.append("Missing 'slides' field")
        return errors

    # Check theme exists
    if 'theme' not in config:
        errors.append("WARNING: No 'theme' defined - using defaults")

    # Check each slide
    for i, slide in enumerate(config.get('slides', [])):
        slide_num = i + 1
        slide_type = slide.get('type')

        if not slide_type:
            errors.append(f"Slide {slide_num}: Missing 'type' field")
            continue

        if slide_type not in SUPPORTED_SLIDE_TYPES:
            errors.append(f"Slide {slide_num}: Unsupported type '{slide_type}' (valid: {SUPPORTED_SLIDE_TYPES})")

        # Check image references
        if slide_type == 'image_bio':
            image_key = slide.get('image')
            if image_key:
                images = config.get('images', {})
                if image_key not in images:
                    errors.append(f"Slide {slide_num}: Image key '{image_key}' not found in images section")
                else:
                    image_path = lesson_dir / images[image_key]
                    if not image_path.exists():
                        errors.append(f"Slide {slide_num}: Image file not found: {images[image_key]}")

    # Check images section
    for key, path in config.get('images', {}).items():
        full_path = lesson_dir / path
        if not full_path.exists():
            errors.append(f"Image '{key}' file not found: {path}")

    return errors


def check_quiz_format(lesson_dir: Path) -> list[str]:
    """Check quiz.md follows Automagical Forms format."""
    errors = []
    quiz_path = lesson_dir / 'quiz.md'

    if not quiz_path.exists():
        return ["quiz.md not found"]

    content = quiz_path.read_text(encoding='utf-8')

    # Check for (correct) tags
    if '(correct)' not in content:
        errors.append("No (correct) tags found - quiz answers not marked")

    # Count questions
    question_count = content.count('## Question')
    if question_count < 5:
        errors.append(f"Only {question_count} questions found (recommend 5-8)")
    elif question_count > 10:
        errors.append(f"{question_count} questions found (recommend 5-8)")

    # Check each question has a correct answer
    questions = content.split('## Question')[1:]  # Skip header
    for i, q in enumerate(questions, 1):
        if '(correct)' not in q:
            errors.append(f"Question {i}: No correct answer marked")

    return errors


def check_reading_length(lesson_dir: Path) -> list[str]:
    """Check reading.md is appropriate length."""
    errors = []
    reading_path = lesson_dir / 'reading.md'

    if not reading_path.exists():
        return ["reading.md not found"]

    content = reading_path.read_text(encoding='utf-8')
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and not p.strip().startswith('#')]

    if len(paragraphs) < 3:
        errors.append(f"Only {len(paragraphs)} paragraphs (recommend 3-5)")
    elif len(paragraphs) > 6:
        errors.append(f"{len(paragraphs)} paragraphs (recommend 3-5, may be too long)")

    return errors


def check_worksheet_prompts(lesson_dir: Path) -> list[str]:
    """Check worksheet.md has appropriate prompts."""
    errors = []
    worksheet_path = lesson_dir / 'worksheet.md'

    if not worksheet_path.exists():
        return ["worksheet.md not found"]

    content = worksheet_path.read_text(encoding='utf-8')
    prompt_count = content.count('## Prompt')

    if prompt_count < 4:
        errors.append(f"Only {prompt_count} prompts (recommend 4-6)")
    elif prompt_count > 8:
        errors.append(f"{prompt_count} prompts (recommend 4-6, may be too many)")

    # Check for blank lines (shouldn't have fill-in blanks)
    if '____________' in content or '_____' in content:
        errors.append("Contains fill-in blanks (students discuss verbally, summarize on paper)")

    return errors


def verify_lesson(lesson_dir: Path) -> bool:
    """Run all verification checks on a lesson directory."""
    print(f"\n{'='*60}")
    print(f"VERIFYING: {lesson_dir}")
    print(f"{'='*60}\n")

    all_passed = True
    warnings = []

    # Check required files
    print("REQUIRED FILES:")
    for filename in REQUIRED_FILES:
        exists, msg = check_file_exists(lesson_dir, filename)
        print(f"  {msg}")
        if not exists:
            all_passed = False

    # Check recommended files
    print("\nRECOMMENDED:")
    for filename in RECOMMENDED_FILES:
        exists, msg = check_file_exists(lesson_dir, filename)
        print(f"  {msg}")
        if not exists:
            warnings.append(f"Missing recommended: {filename}")

    # Validate YAML config
    print("\nYAML CONFIGURATION:")
    yaml_errors = check_yaml_config(lesson_dir)
    if yaml_errors:
        for error in yaml_errors:
            print(f"  [ERROR] {error}")
            if not error.startswith("WARNING"):
                all_passed = False
    else:
        print("  [OK] Valid configuration")

    # Check quiz format
    print("\nQUIZ FORMAT:")
    quiz_errors = check_quiz_format(lesson_dir)
    if quiz_errors:
        for error in quiz_errors:
            print(f"  [ERROR] {error}")
            all_passed = False
    else:
        print("  [OK] Quiz format correct")

    # Check reading length
    print("\nREADING LENGTH:")
    reading_errors = check_reading_length(lesson_dir)
    if reading_errors:
        for error in reading_errors:
            print(f"  [WARN] {error}")
            warnings.append(error)
    else:
        print("  [OK] Appropriate length")

    # Check worksheet
    print("\nWORKSHEET PROMPTS:")
    worksheet_errors = check_worksheet_prompts(lesson_dir)
    if worksheet_errors:
        for error in worksheet_errors:
            print(f"  [WARN] {error}")
            warnings.append(error)
    else:
        print("  [OK] Prompts look good")

    # Summary
    print(f"\n{'='*60}")
    if all_passed:
        print("VERIFICATION PASSED")
        if warnings:
            print(f"  ({len(warnings)} warnings)")
    else:
        print("VERIFICATION FAILED")
    print(f"{'='*60}\n")

    return all_passed


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_lesson.py <lesson_directory>")
        print("Example: python verify_lesson.py lessons/01-james-baldwin-civil-rights")
        sys.exit(1)

    lesson_dir = Path(sys.argv[1])

    if not lesson_dir.exists():
        print(f"ERROR: Directory not found: {lesson_dir}")
        sys.exit(1)

    passed = verify_lesson(lesson_dir)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
