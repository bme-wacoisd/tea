# Claude AI Instructions for Grow Texas Teachers Lessons

This document provides context and instructions for AI assistants working on this project.

## Project Overview

This repository contains lesson materials for a **Grow Your Own** educator preparation program. Students are 9th-12th grade future educators who will eventually teach pre-K through high school.

### Key Constraints

- **Reading levels vary widely** - Write clearly and accessibly
- **Independent lessons** - No prerequisites; each lesson stands alone
- **Lesson duration** - 30-40 minutes total
- **Mixed grade levels** - Students come from overlapping courses with different requirements

### Teaching Model (CRITICAL for understanding assignment distribution)

**Fluid schedule, self-contained lessons**: Mr. Edwards has a complex teaching environment:
- Students range from grades 9-12
- Some students have 15 hours/week, others only 3 hours/week
- Students leave the classroom frequently to shadow-teach in elementary classrooms on unsynchronized schedules
- Course types (Instructional Practices vs Communications) are administrative distinctions, not content silos

**Strategy**: Teach self-contained 30-45 minute lessons with group work and a quiz at the end. No prerequisites between lessons. This means:
- A student with only 3 hours/week won't complete all assignments, but that's expected
- Lessons are ready to teach whenever students are present
- Enough grades will accumulate by end of six weeks to meet district policy

**Assignment distribution**: Our `create_lesson_assignment.py` script assigns EVERY lesson to ALL students across all 8 periods. The `deduplicate_assignments.py` script then ensures multi-period students only get ONE copy (via round-robin distribution across their enrolled periods).

**This means**: A student enrolled in "Instructional Practices" periods can and should complete quizzes that might seem like "Communications" content. All students get all quizzes - the course type distinction is for scheduling, not content access.

### Course Resources

Downloaded course materials are in the `output/` folder, scraped from:
- Instructional Practices: https://www.growtexasteachers.org/practices
- Practicum: https://www.growtexasteachers.org/practicum

Reference these materials when creating lessons but adapt content for the specific format below.

### TEKS (Texas Essential Knowledge and Skills)

Lesson plans must align to TEKS for the courses being taught. TEKS reference materials:

**Source files (ALWAYS check these for alignment):**
- `teks/*.pdf` - Top-level TEKS PDF documents (e.g., `communication-and-technology-in-education.pdf`)
- `teks/practices/generated/` - Instructional Practices course materials (converted to markdown)
- `teks/practices/*.pdf` - Additional Instructional Practices PDFs
- `teks/practicum/generated/` - Practicum course materials (converted to markdown)
- `teks/practicum/*.pdf` - Additional Practicum PDFs

**Key TEKS for Instructional Practices (Course 2):**
- **TEKS 4**: The student understands the learner and the learning process (relationships, rapport, effective instruction)
- **TEKS 5**: The student understands instructional planning and delivery
- **TEKS 7**: The student creates an effective learning environment (safety, universal design, classroom management)

**Key TEKS for Practicum (Course 3):**
- **TEKS 1-3**: Foundations of teaching and professional development
- **TEKS 6**: Assessment and evaluation

**Key TEKS for Communication and Technology in Education:**
- **TEKS 130.123(c)(4)**: The student uses technology tools to enhance learning
- **TEKS 130.123(c)(6)**: The student understands digital citizenship

**Format in lesson plans (use table format):**
```markdown
| TEKS | Standard |
|------|----------|
| 4 | **The student understands the learner...** Description of alignment |
| 5 | **The student understands instructional planning...** Description |
```

---

## Lesson Template Structure

Each lesson goes in `lessons/XX-lesson-name/` and contains:

### 1. `slides.md` - Presentation Slides

**Purpose**: Slides for instructor to present to class

**Content focus**: "How to teach X" - practical teaching strategies

**Format**:
```markdown
# Lesson Title

---

## Slide Title

- Bullet point
- Another point

Speaker notes: Additional context for presenter

---

## Next Slide
```

### 2. `reading.md` - Read-Aloud Text

**Purpose**: 3-5 paragraphs for instructor to read aloud while students follow along

**Guidelines**:
- Clear, engaging prose
- Accessible vocabulary
- Introduces key concepts
- Sets context for group work

### 3. `worksheet.md` - Group Discussion Prompts

**Purpose**: Discussion prompts for small group work

**Guidelines**:
- NO blank lines for writing (students summarize on paper)
- Students read prompts on their computers
- Designed for verbal discussion
- Instructor circulates to scaffold conversations
- Include 4-6 discussion prompts
- Progress from basic understanding to application

**Format**:
```markdown
# Group Discussion: [Topic]

## Prompt 1: [Title]
[Discussion question or scenario]

## Prompt 2: [Title]
[Discussion question or scenario]
```

### 4. `quiz.md` - Assessment Quiz

**Purpose**: Google Classroom quiz (created via Automagical Forms)

**Automagical Forms Format**:
- Mark correct answers with `(correct)` tag
- 5-8 questions per quiz
- Mix of question types: multiple choice, true/false

**Example Format**:
```markdown
# Quiz: [Topic]

## Question 1
What is the primary purpose of differentiated instruction?

A. To make lessons easier for all students
B. To address diverse learning needs in a classroom (correct)
C. To reduce teacher workload
D. To standardize curriculum delivery

## Question 2
True or False: Scaffolding means providing permanent support to struggling learners.

A. True
B. False (correct)
```

**Quiz Settings** (for Google Classroom):
- Hidden answer key
- Do not show answers at end
- Randomize question order for each student
- No retakes allowed

### 5. `lesson-plan.md` - Formal Lesson Plan

**Purpose**: Documentation for dean and instructional specialist

**Header format** (no placeholders!):
```markdown
# Lesson Plan: [Title]

**Course**: Grow Your Own Educator Preparation Program
**Grade Level**: 9-12 (Future Educators)
**Duration**: 35-40 minutes
**Instructor**: Brian Edwards (brian.edwards@wacoisd.org)
**Date Prepared**: [INSERT TODAY'S ACTUAL DATE]
```

**IMPORTANT**: Always use the actual current date when creating lessons. Never use placeholders like "___" or "[date]".

**Required sections**:
- Lesson Title and Duration
- Learning Objectives (2-3 measurable objectives)
- Texas TEKS alignment (use table format)
- Materials needed
- Lesson sequence with timing
- Assessment strategy
- Differentiation notes

---

## Creating a New Lesson

1. Create folder: `lessons/XX-descriptive-name/`
2. Create all 6 required files (see template structure above)
3. **Fill in instructor**: Brian Edwards (brian.edwards@wacoisd.org)
4. **Fill in date prepared**: Use current date (not placeholder)
5. Generate Google artifacts:
   - `python slides.py lessons/XX-lesson-name/slides.yaml` → Google Slides
   - `python quiz.py lessons/XX-lesson-name/quiz.md` → Google Form
   - `python lesson_plans_to_drive.py` → PDFs to Google Drive
6. Verify all content is complete (no placeholders like "___________________")

## Style Guidelines

- **Tone**: Professional but approachable
- **Perspective**: Preparing future educators
- **Focus**: Practical teaching strategies they can use
- **Examples**: Include concrete classroom scenarios
- **Accessibility**: Clear language, defined terms

---

## Teaching Principles (Critical)

**These principles guide all lesson content. Follow them carefully.**

### Meta-Teaching: Embody, Don't Just Describe

**This is the most important principle.** Each lesson teaches future educators "how to teach X" by featuring a master teacher (Baldwin, Richardson, Sanderson, etc.). The lesson materials must EMBODY that person's approach, not just describe it.

- **The instructor IS the example** - When teaching "How to teach history like Richardson," the instructor teaches a mini history lesson USING Richardson's methods
- **The materials ARE the model** - The reading, slides, and activities should demonstrate the approach, not just explain it
- **Show, don't preach** - Less "here's what Richardson does" and more "watch me do it Richardson's way"
- **Practice what it preaches** - If Baldwin says "show, don't describe," the lesson must show, not describe

**Examples:**
- Baldwin lesson: Uses Baldwin's direct voice, his actual quotes, tells stories of specific people (Ruby Bridges age 6, John Lewis age 23)
- Richardson lesson: Connects historical patterns to present-day situations, starts with stories before patterns
- Sanderson lesson: Opens with concrete examples before abstractions, emphasizes visual intuition

**The test:** Could a student learn the teaching approach just by experiencing the lesson, even if you removed all the explicit explanations of the method?

### First Principles Approach
- **Teach from first principles** - Build concepts from the ground up
- **Define key terms EARLY** - In the reading and slides, define essential vocabulary at the start, not buried later
- **Branch from definitions** - Once a term is defined, show how it connects to related concepts
- **Avoid jargon** - Use plain language; when technical terms are necessary, explain them
- **Spell out acronyms** on first use (e.g., "English Language Learners (ELL)")
- **Don't assume prior knowledge** - Each lesson stands alone

### Clarity and Differentiation
- **Differentiate concepts from similar ones** - Explicitly compare and contrast related ideas
- **Clarify opposites** - Help students understand what something is by explaining what it is NOT
- **Don't bury the lede** - Lead with the most important point, then elaborate
- **Front-load key takeaways** - Students should grasp the core idea even if they zone out partway through

### Deep Learning Goals
- **Prioritize connections** - The most important outcome is "light bulb moments" where students connect ideas
- **Encourage combining concepts** - Help students see how ideas relate and build on each other
- **Support riffing and exploration** - Create space for students to extend ideas in their own directions
- **Develop informed taste** - Help students form preferences about HOW they will teach, not just WHAT to teach
- **Build intuition** - Move beyond rules to gut feelings about good teaching practice

### Practical Application
- **Make it actionable** - Every concept should connect to something they can DO in a classroom
- **Use concrete scenarios** - Abstract principles need grounding in specific examples
- **Honor their future students** - Always connect back to the children they will eventually teach

---

## Slide Presentation Guidelines

### CRITICAL: Content Must Be Separate From Code

**NEVER hardcode slide content in Python scripts.** All lesson-specific content must be in configuration files.

### Workflow

1. **Content lives in YAML**: Each lesson has `slides.yaml` defining all slide content
2. **Script is generic**: `create_slides_from_yaml.py` reads YAML and generates slides
3. **Run with**: `python create_slides_from_yaml.py lessons/XX-lesson-name/slides.yaml`

### File Structure for Each Lesson
```
lessons/XX-lesson-name/
├── slides.yaml       # Slide content configuration (REQUIRED)
├── slides.md         # Human-readable content planning
├── assets/           # Images referenced in slides.yaml
│   └── *.jpg
├── reading.md
├── worksheet.md
├── quiz.md
└── lesson-plan.md
```

### YAML Configuration Structure
```yaml
title: "Presentation Title"
subtitle: "Subtitle"

theme:  # Vary colors between lessons!
  primary: {r: 0.1, g: 0.2, b: 0.4}
  secondary: {r: 0.2, g: 0.6, b: 0.6}
  accent1: {r: 0.95, g: 0.75, b: 0.2}
  accent2: {r: 0.95, g: 0.4, b: 0.35}
  background: {r: 1.0, g: 0.98, b: 0.94}
  text: {r: 0.2, g: 0.2, b: 0.25}

images:
  subject_photo: "assets/photo.jpg"

slides:
  - type: title
  - type: big_idea
    main_text: "Key message"
  - type: image_bio
    title: "Person Name"
    image: subject_photo
  # ... etc
```

### Supported Slide Types
- `title` - Title slide (uses presentation title/subtitle)
- `big_idea` - Full-bleed background with main message
- `image_bio` - Image with biographical text
- `quote` - Large quote with attribution
- `table` - Styled data table
- `comparison` - Two-column IS/IS NOT style
- `two_column` - Two columns of bullets
- `bullets` - Bullet points with accent markers
- `numbered` - Numbered list items
- `closing` - Final quote slide with CTA

### Slide Dimensions (IMPORTANT)

Google Slides uses a fixed 16:9 aspect ratio that **cannot be changed via the API**:
- **Width**: 10 inches (720 points)
- **Height**: 5.625 inches (405 points)

All slide coordinates in `create_slides_from_yaml.py` are designed for this size. Do not assume other dimensions.

### Visual Design Principles
- **Vary the theme/color palette for each lesson** - Don't reuse colors
- **Minimal text per slide** - Short phrases, not paragraphs
- **Tables are effective** - Use for comparisons, IS/IS NOT content
- **Eye-catching but not distracting** - Professional, engaging

### Color Palette Ideas (rotate between lessons)
- Deep blue + gold + coral (warm, classic)
- Teal + cream + charcoal (modern, calm)
- Purple + orange + white (energetic)
- Forest green + tan + burgundy (earthy)
- Navy + mint + peach (fresh)

### Google API Setup

**Required APIs** (enable in Google Cloud Console):
- Google Slides API
- Google Drive API

**Authentication**:
1. Create OAuth Desktop App credentials at https://console.cloud.google.com/
2. Download and rename to `credentials.json`
3. Place in project root (it's gitignored)
4. First run opens browser for authorization
5. Token saved to `token.pickle` for subsequent runs

---

## Complete Lesson Creation Process

### Step 1: Create Folder Structure
```bash
mkdir lessons/XX-lesson-name
mkdir lessons/XX-lesson-name/assets
```

### Step 2: Create All Required Files
Create these files in the lesson folder:
1. `slides.yaml` - Slide content configuration
2. `slides.md` - Human-readable slide planning
3. `reading.md` - Read-aloud text (3-5 paragraphs)
4. `worksheet.md` - Group discussion prompts (4-6 prompts)
5. `quiz.md` - Assessment quiz (5-8 questions, Automagical Forms format)
6. `lesson-plan.md` - Formal lesson plan

### Step 3: Add Assets
Place any images (photos, diagrams) in the `assets/` folder. Reference them in `slides.yaml`.

### Step 4: Verify Lesson
```bash
python verify_lesson.py lessons/XX-lesson-name
```

This checks:
- All required files exist
- YAML configuration is valid
- Slide types are supported
- Images referenced in YAML exist
- Quiz format is correct (has correct answers marked)
- Reading length is appropriate
- Worksheet has enough prompts

### Step 5: Generate Google Slides
```bash
python create_slides_from_yaml.py lessons/XX-lesson-name/slides.yaml
```

### Step 6: Visual Verification
Open the generated presentation URL and verify:
- All slides fit on screen (no content cut off)
- Text is readable
- Images display correctly
- Colors look good

---

## Project Scripts Reference

### `slides.py`
**Purpose**: Generate Google Slides presentations from YAML config
**Usage**: `python slides.py <path_to_slides.yaml>`
**Notes**: Generic script - reads all content from YAML, never hardcodes lesson content. Includes verification before generation.

### `quiz.py`
**Purpose**: Generate Google Forms quizzes from markdown
**Usage**: `python quiz.py <path_to_quiz.md>`
**Notes**: Parses quiz.md format, creates form with correct answers marked, configures quiz settings automatically. Includes verification.

### `doc.py`
**Purpose**: Generate Google Docs from markdown content
**Usage**: `python doc.py <path_to_markdown.md>`
**Notes**: Creates formatted Google Docs from markdown files.

### `verify.py`
**Purpose**: Validate lesson materials before generating Google artifacts
**Usage**: `python verify.py <lesson_directory>`
**Notes**: Checks file existence, YAML validity, quiz format, content length.

### `convert_lesson.py`
**Purpose**: Convert markdown files to PDF/PowerPoint (offline fallback)
**Usage**: `python convert_lesson.py <lesson_directory>`
**Notes**: Creates lesson-plan.pdf and slides.pptx for offline use.

### `scrape_and_convert.py`
**Purpose**: Scrape PowerPoint files from growtexasteachers.org courses
**Usage**: `python scrape_and_convert.py [--output DIR] [--url URL NAME]`
**Notes**: Downloads course materials to `output/` folder for reference.

---

## Resources

- [Automagical Forms](https://automagicalapps.com/forms) - Quiz creation tool
- [Automagical Forms FAQ](https://automagicalapps.com/forms-faq) - Format help
- [Google Cloud Console](https://console.cloud.google.com/) - For Slides API credentials
- Course materials in `output/` folder

---

## Google Classroom Management

### Student Environment
- **School Chromebooks** - All students use district-issued Chromebooks
- **School accounts** - Students are logged in with their school Google accounts (@wacoisd.org)
- **"Not accepted" invites are REAL** - Students who haven't accepted their class invites need to do so manually. This is a common issue with high school students.

### Scripts

**`scripts/deduplicate_assignments.py`** - Remove duplicate assignments for multi-period students
- Students enrolled in multiple class periods receive duplicate assignments when work is assigned to all periods at once
- This script identifies duplicates (same title across courses) and removes all but one per student
- Uses round-robin distribution to spread assignments evenly across periods
- Handles "empty assignees" errors by trying alternate periods

```bash
python scripts/deduplicate_assignments.py              # Dry run (preview)
python scripts/deduplicate_assignments.py --apply      # Make changes
python scripts/deduplicate_assignments.py --apply -y   # Skip confirmation
```

**`scripts/classroom_status.py`** - Status report comparing Frontline TEAMS roster to Google Classroom
- Reports students who haven't accepted invites
- Checks for remaining duplicate assignments
- Compares Frontline roster (source of truth) to Classroom enrollment
- Uses `name-mappings.csv` for name differences between systems
- Uses `ab-frontline-roster-2025-12-11.csv` as source of truth

```bash
python scripts/classroom_status.py
```

**`scripts/send_classroom_reminders.py`** - Send email reminders via Gmail API
- Sends personalized reminders to students who haven't accepted class invites
- Multi-period students who accepted some but not all get a special message
- Does NOT spam students who have already accepted all classes
- Dry run by default to preview emails before sending

```bash
python scripts/send_classroom_reminders.py              # Preview emails
python scripts/send_classroom_reminders.py --send       # Actually send
python scripts/send_classroom_reminders.py --send -y    # Send without confirmation
```

### Data Files
- `credentials.json` - OAuth credentials (gitignored)
- `token_dedup.json` - Token for dedup script (gitignored)
- `token_classroom.pickle` - Token for status script (gitignored)
- `token_reminders.json` - Token for email reminders script (gitignored)
- `token_assignment.json` - Token for assignment creation scripts (gitignored)
- `token_quiz_check.json` - Token for quiz completion check (gitignored)
- `name-mappings.csv` - Maps Frontline names to Google Classroom names
- `ab-frontline-roster-2025-12-11.csv` - Frontline TEAMS roster export

### Course Names (CRITICAL)

The 8 class periods alternate between course types:

| Period | Course Name |
|--------|-------------|
| 1 | 1 Instructional Practices & Practicum |
| 2 | 2 Communications and Technology |
| 3 | 3 Instructional Practices & Practicum |
| 4 | 4 Communications and Technology |
| 5 | 5 Instructional Practices & Practicum |
| 6 | 6 Communications and Technology |
| 7 | 7 Instructional Practices & Practicum |
| 8 | 8 Communications and Technology |

**Pattern**: Odd periods = Instructional Practices & Practicum, Even periods = Communications and Technology

**IMPORTANT**: These exact course names must be used in all scripts. Common mistake is getting periods 3-4 and 7-8 swapped.

### Creating Lesson Assignments

**`scripts/create_lesson_assignment.py`** - Complete lesson assignment pipeline
- Creates Google Form with anti-cheat settings (shuffle questions, no answers shown, require login)
- **Enables email collection** (`emailCollectionType: VERIFIED`) so we can identify respondents
- Creates Google Slides presentation
- Distributes assignment across all 8 periods with round-robin for multi-period students
- Uses `associatedWithDeveloper: true` for API grading
- Shares form with wacoisd.org domain for proper title display in Classroom
- Due date: Feb 13, 2026 at 8:00 AM Central

```bash
python scripts/create_lesson_assignment.py lessons/XX-lesson-name --dry-run   # Preview
python scripts/create_lesson_assignment.py lessons/XX-lesson-name             # Create
```

**`scripts/delete_and_recreate_lesson.py`** - Delete and recreate lesson assignments
- Finds existing assignments by title
- Deletes from all 8 courses
- Recreates with latest content

```bash
python scripts/delete_and_recreate_lesson.py lessons/XX-lesson-name --dry-run  # Preview
python scripts/delete_and_recreate_lesson.py lessons/XX-lesson-name            # Execute
```

**`scripts/check_quiz_completions.py`** - Find completed quizzes and report scores
- Checks Google Forms responses for all quiz forms
- Cross-references with Classroom submission states
- Reports students who completed quizzes but didn't click "Turn In"
- Requires email collection enabled on forms (see enable_form_email_collection.py)

```bash
python scripts/check_quiz_completions.py
```

**`scripts/enable_form_email_collection.py`** - Fix forms to collect respondent emails
- Updates all quiz forms to collect verified email addresses
- Required for identifying which student submitted each response
- Run once to fix all existing forms

```bash
python scripts/enable_form_email_collection.py --dry-run  # Preview
python scripts/enable_form_email_collection.py            # Apply
```

### Google Classroom API Notes

**CRITICAL - No notifications by design**:
- Assignments created via the Classroom API do NOT send email notifications to students
- Only assignments created through the Classroom web UI trigger email notifications
- This is a built-in API behavior - we don't need to do anything special to avoid spam
- NEVER sacrifice features (due dates, etc.) to "avoid notifications" - API already handles this
- **Web UI actions DO notify**: If you manually create/delete/modify assignments in the web UI, students get emails. Use our scripts instead to avoid notification spam.

**Materials cannot be updated after creation**:
- The `updateMask` parameter does NOT support `materials`
- To fix material titles/links, you must delete and recreate the assignment
- Share forms with wacoisd.org domain BEFORE creating assignment for proper title display

**Due time requires due date**:
- When updating `dueTime`, you MUST include `dueDate` in the `updateMask`
- Use: `updateMask='dueDate,dueTime'`

**Form title display**:
- By default, form links using responderUri (`/e/.../viewform`) show "Google Forms: Sign-in"
- Fix: Use direct form URL (`/d/{form_id}/viewform`) AND enable link sharing ("anyone" as reader)
- When you pass a Google Forms URL as a `link` material, Classroom auto-converts it to a `form` material and fetches the proper title from the form metadata

**Assignment titles**:
- The OAuth app name shows as "Assignment via [APP_NAME]" in the assignment footer
- App name is set in Google Cloud Console OAuth consent screen, not via API

**Calendar events**:
- Assignments created via the API do NOT create Google Calendar events
- Only assignments created through the Classroom web UI create calendar events
- This is beneficial - no calendar clutter for students from API-created assignments
- Verified with `scripts/check_calendar_events.py`

**Form email collection (CRITICAL)**:
- Forms MUST have `emailCollectionType: VERIFIED` to identify who submitted responses
- Without this, form responses show as anonymous and we can't match them to students
- The `create_lesson_assignment.py` script automatically enables this setting
- Use `scripts/enable_form_email_collection.py` to fix existing forms

**Quiz completion vs Classroom turn-in**:
- Students often complete the quiz (Google Form) but forget to click "Turn In" in Classroom
- The form response exists but Classroom shows the assignment as "CREATED" not "TURNED_IN"
- Use `scripts/check_quiz_completions.py` to find all form completions regardless of Classroom state
- Future: `scripts/sync_quiz_grades.py` will auto-turn-in and enter grades for completed quizzes

---

## Student Data and Tracking System

### Student Email Formats (CRITICAL)

Waco ISD students have **TWO email addresses** that can be used interchangeably:

1. **Name Email**: `firstname.lastname@student.wacoisd.org`
   - Example: `allison.leyva@student.wacoisd.org`

2. **ID Email**: `s########@student.wacoisd.org`
   - The `s` prefix stands for "student"
   - The number is their Student ID
   - Example: `s30004214@student.wacoisd.org` (Allinson Leyva)

**When students submit Google Forms**, they may use either email. The form response will show whichever email they used at the time.

**To look up a student by ID email**: Remove the `s` prefix to get the Student ID (e.g., `s30020013` → Student ID `30020013`).

### Student Lookup Table

The `scripts/build_student_lookup.py` script creates a comprehensive student roster:

**Output locations** (all containing PII - never commit to git):
- `student_lookup/students_latest.csv` - Latest CSV (gitignored)
- `student_lookup/students_YYYY-MM-DD.csv` - Dated archive (gitignored)
- `~/Documents/gyo-student-roster/` - Human-readable reports

**Data includes**:
- Student ID
- Name (Frontline spelling)
- Name (Google Classroom spelling)
- ID Email
- Name Email
- Periods enrolled
- Course types (Instructional Practices, Communications)

```bash
python scripts/build_student_lookup.py --dry-run  # Preview
python scripts/build_student_lookup.py            # Build lookup table
```

### GYO Grade Tracking Spreadsheet

A Google Sheets spreadsheet tracks all assignments and quiz completions:

**Spreadsheet**: "GYO Grade Tracking"
**URL stored in**: `tracking_spreadsheet_id.txt` (gitignored)
**Managed by**: `scripts/sheets_tracker.py`

**Sheets**:
1. **Assignments** - All created lesson assignments
   - Assignment Title, Form ID, Form URL, Slides ID, Slides URL
   - Total Points, Created At, Updated At, Status (ACTIVE/DELETED)

2. **Quiz Completions** - All form responses/quiz submissions
   - Response ID, Assignment Title, Student Email, Student Name
   - Score, Total Points, Percentage, Submitted At
   - Synced to Classroom (YES/NO), Sync Time, Notes

3. **Students** - Student lookup data (built by build_student_lookup.py)

**Scripts integrated with tracker**:
- `create_lesson_assignment.py` - Records new assignments
- `delete_and_recreate_lesson.py` - Marks assignments as DELETED
- `sync_quiz_completions.py` - Fetches form responses and records completions
- `backfill_tracker.py` - One-time backfill of existing data

### Sync Scripts

**`scripts/sync_quiz_completions.py`** - Fetch new quiz completions
```bash
python scripts/sync_quiz_completions.py --dry-run  # Preview
python scripts/sync_quiz_completions.py            # Sync completions
```

**`scripts/backfill_tracker.py`** - One-time backfill of existing data
```bash
python scripts/backfill_tracker.py --dry-run  # Preview
python scripts/backfill_tracker.py            # Execute backfill
```

### Token Files (all gitignored)

Each script uses its own OAuth token file to avoid scope conflicts:
- `token_assignment.json` - Assignment creation
- `token_sheets.json` - Sheets tracker
- `token_sync.json` - Quiz sync
- `token_student_lookup.json` - Student lookup builder
- `token_backfill.json` - Backfill script
- `token_dedup.json` - Deduplication
- `token_classroom.pickle` - Classroom status
- `token_reminders.json` - Email reminders
- `token_quiz_check.json` - Quiz completion check

### Name Mappings

Some students have different name spellings in Frontline TEAMS vs Google Classroom:

**File**: `~/google-classroom/waco-teams-hosting/rosters/name-mappings.csv`

Example:
```csv
"Frontline Teams","Google Classroom"
"Leyva, Allinson Ruth","Allison Leyva"
"Hernandez, Leana Rose","Leana Cruz"
```

---

## Reading.md Writing Guidelines

**Structure for readings featuring master teachers/educators**:
- Do NOT start the first paragraph with the individual's name
- Open with a compelling scene, question, or universal concept
- Introduce the specific educator in paragraph 2 or later
- Embody the teaching approach being described, don't just explain it

**Example structure**:
1. **Hook**: Universal observation, compelling scene, or thought-provoking question
2. **Context**: Introduce the educator and their key insight
3. **Framework**: Explain the practical approach or methodology
4. **Application**: Connect to classroom practice
5. **Closing**: Memorable takeaway or call to action

---

## Primary Content Source: Knight Lesson Plans

The file `teks/knight-lesson-plans-extracted/knight-lesson-plans.md` contains the base curriculum content that inspires our lessons. This is a comprehensive semester curriculum covering three units across 18 weeks.

### Source Structure

**UNIT 1: Professional Identity & Classroom Foundations (Weeks 1-6)**
- Week 1: Professional Standards & The Teaching Profession
- Week 2: Understanding Learners & Human Development
- Week 3: Creating Effective Learning Environments
- Week 4: Assessment & Feedback
- Week 5: Professional Responsibilities & Unit 1 Synthesis

**UNIT 2: Instructional Planning & Curriculum Development (Weeks 7-12)**
- Week 7: Understanding TEKS & Instructional Planning
- Week 8: Instructional Theories & Differentiation
- Week 9: Creating Instructional Materials & Resources
- Week 10: Unit Planning & Microteaching Preparation
- Week 11: Professional Ethics & Responsibilities
- Week 12: Unit 2 Synthesis & Portfolio Development

**UNIT 3: Professional Growth & Career Readiness (Weeks 13-18)**
- Week 13: Observation and Evaluation Skills
- Week 14: Mentorship and Professional Relationships
- Week 15: Employment Readiness and Certification
- Week 16: Practicum Culmination and Documentation
- Week 17: Final Portfolio Development
- Week 18: Presentations and Course Celebration

### Adaptation Approach

When creating lessons from this source:

1. **Do NOT create 1:1 lesson mappings** - The source uses 45-minute blocks; our lessons are 30-40 minutes with different artifacts
2. **Zoom into captivating elements** - Go deeper on compelling topics rather than shallow coverage
3. **Feature master teachers** - When possible, connect concepts to real educators who exemplify the approach
4. **Research rabbit holes** - For rich topics (Piaget, Vygotsky, Bloom's Taxonomy), research deeply and bring fresh insights
5. **Define terms from first principles** - Source assumes more background; our lessons must define everything clearly
6. **Front-load key concepts** - Our reading and slides lead with the most important ideas

### Key Educators & Frameworks to Feature

From the source material, these warrant deep exploration:

**Historical Educators:**
- Horace Mann - Father of American Public Education (1840s)
- John Dewey - Progressive Education, Learning by Doing
- Maria Montessori - Child-centered, self-directed learning
- Jean Piaget - Stages of Cognitive Development
- Lev Vygotsky - Zone of Proximal Development, Scaffolding
- Erik Erikson - Psychosocial Development Stages
- B.F. Skinner - Behaviorism, Reinforcement
- Albert Bandura - Social Learning Theory, Modeling

**Modern Educators to Research:**
- Rita Pierson - "Every Kid Needs a Champion" TED Talk
- Carol Tomlinson - Differentiation Framework
- Grant Wiggins & Jay McTighe - Backward Design (Understanding by Design)
- Patrick Lencioni - 5 Dysfunctions of a Team
- Ruben Puentedura - SAMR Model for technology integration

**Key Frameworks:**
- Bloom's Taxonomy (6 cognitive levels)
- Universal Design for Learning (UDL) - 3 principles
- 4 Ways to Differentiate (Content, Process, Product, Environment)
- Backward Design (3 stages)
- SAMR Model (Substitution, Augmentation, Modification, Redefinition)
- Assessment Types (Formative, Summative, Diagnostic)
- The Assessment Cycle

### Lesson Topic Clusters

When creating lessons, consider these thematic clusters:

1. **Building Relationships** - Rita Pierson, relationship strategies, knowing students
2. **How Students Learn** - Piaget, Vygotsky, constructivism vs. behaviorism
3. **Classroom Design** - UDL, physical environment, grouping strategies
4. **Planning Backwards** - Backward design, objectives, alignment
5. **Reaching All Learners** - Differentiation, IEPs, 504s, English learners
6. **Assessment for Learning** - Formative assessment, feedback, questioning
7. **Professional Ethics** - Boundaries, mandatory reporting, confidentiality
8. **Technology as a Tool** - SAMR model, purposeful integration

---

## Web Application (React/TypeScript)

### Tech Stack
- React 18 + TypeScript
- Vite 6
- Turborepo (monorepo)
- npm (packageManager)
- Vitest (unit testing)
- Playwright (E2E testing)

### Project Structure (Node.js Apps)
```
tea/
├── apps/
│   └── web/                 # React application
│       ├── src/
│       │   ├── components/  # React components
│       │   ├── App.tsx
│       │   ├── googleApi.ts # Google API utilities
│       │   └── types.ts     # TypeScript types
│       ├── e2e/             # Playwright tests
│       └── package.json
├── packages/                # Shared packages
├── extensions/              # Chrome extensions
│   └── frontline-teams/     # Frontline TEAMS grade sync extension
├── .github/
│   └── workflows/           # GitHub Actions CI
├── turbo.json
└── package.json
```

### Development Commands
```bash
npm run dev          # Start dev server (http://localhost:3000)
npm run build        # Production build
npm run type-check   # TypeScript checking
npm run lint         # ESLint
npm run test         # Run Vitest unit tests
npm run test:e2e     # Run Playwright E2E tests
```

### Deployment
The React app is deployed to GitHub Pages at https://bme-wacoisd.github.io/google-classroom/

```bash
npm run build
npx gh-pages -d apps/web/dist
```

---

## Chrome Extension: Frontline TEAMS Grade Sync

Located in `extensions/frontline-teams/`. This extension syncs grades from Google Classroom to Frontline TEAMS (the district SIS).

**Key Files:**
- `manifest.json` - Extension configuration
- `background.js` - Service worker
- `content.js` - Content script for TEAMS pages
- `google-classroom.js` - Classroom API integration
- `popup.html/js/css` - Extension popup UI

---

## WBL Group Planner

Generate a Work-Based Learning schedule report to help form student groups.

**Schedule Structure:**
| Day Type | Morning | Afternoon |
|----------|---------|-----------|
| A-Day | Periods 1, 2 (~90 min) | Periods 3, 4 (~90 min) |
| B-Day | Periods 5, 6 (~90 min) | Periods 7, 8 (~90 min) |

**Generate Report:**
```bash
python scripts/generate_wbl_report.py
npx md-to-pdf waco-teams-hosting/wbl-group-planner.md --stylesheet waco-teams-hosting/pdf-style.css
```

**Output (gitignored - contains student PII):**
- `waco-teams-hosting/wbl-group-planner.md`
- `waco-teams-hosting/wbl-group-planner.pdf`

**Group Stability Ratings:**
- ★★★ = Together ALL day types (best for long projects)
- ★★ = Together most days
- ★ = Together some days

---

## Development Workflow (for Node.js apps)

### 1. Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/<issue-number>-<short-description>
```

### 2. Implement & Test
```bash
npm run type-check
npm run lint
npm run test
npm run build
```

### 3. Commit
```bash
git commit -m "feat(scope): description

Closes #<issue-number>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 4. Create PR
```bash
gh pr create --title "feat(scope): description" --body "## Summary
- What this PR does

## Test Plan
- [ ] Tests pass
- [ ] Manual testing completed

Closes #<issue-number>"
```

### 5. Merge
```bash
gh pr merge --squash --delete-branch
```
