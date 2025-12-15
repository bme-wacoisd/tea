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

**Required sections**:
- Lesson Title and Duration
- Learning Objectives (2-3 measurable objectives)
- Texas TEKS alignment (if applicable)
- Materials needed
- Lesson sequence with timing
- Assessment strategy
- Differentiation notes

---

## Creating a New Lesson

1. Create folder: `lessons/XX-descriptive-name/`
2. Copy structure from `lessons/templates/`
3. Adapt content to topic while maintaining format
4. Ensure all 5 files are complete
5. Test quiz format with Automagical Forms

## Style Guidelines

- **Tone**: Professional but approachable
- **Perspective**: Preparing future educators
- **Focus**: Practical teaching strategies they can use
- **Examples**: Include concrete classroom scenarios
- **Accessibility**: Clear language, defined terms

---

## Teaching Principles (Critical)

**These principles guide all lesson content. Follow them carefully.**

### First Principles Approach
- **Teach from first principles** - Build concepts from the ground up
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

## Resources

- [Automagical Forms](https://automagicalapps.com/forms) - Quiz creation tool
- [Automagical Forms FAQ](https://automagicalapps.com/forms-faq) - Format help
- Course materials in `output/` folder
