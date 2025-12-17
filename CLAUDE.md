# Claude AI Instructions for Grow Texas Teachers Lessons

This document provides context and instructions for AI assistants working on this project.

## Project Overview

This repository contains lesson materials for a **Grow Your Own** educator preparation program. Students are 9th-12th grade future educators who will eventually teach pre-K through high school.

### Key Constraints

- **Reading levels vary widely** - Write clearly and accessibly
- **Independent lessons** - No prerequisites; each lesson stands alone
- **Lesson duration** - 30-40 minutes total
- **Mixed grade levels** - Students come from overlapping courses with different requirements

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
- `name-mappings.csv` - Maps Frontline names to Google Classroom names
- `ab-frontline-roster-2025-12-11.csv` - Frontline TEAMS roster export
