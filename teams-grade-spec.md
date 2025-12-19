# Frontline TEAMS Gradebook - Technical Documentation for Chrome Extension Development

## Overview

This document provides detailed instructions for implementing a Chrome extension that imports grades from Google Classroom into Frontline TEAMS ERP & SIS.

---

## Page Structure

The gradebook uses a **four-quadrant table layout** with separate nested tables:

```
Top Left (Headers)       | Top Right (Assignment Headers)
#tableHeaderTable[0]     | #tableHeaderTable[1]
-------------------------+---------------------------
Bottom Left (Students)   | Bottom Right (Grades)
#tableHeaderTable[2]     | #tableHeaderTable[3]
```

**Important:** There are **4 tables with id=tableHeaderTable** - select them using document.querySelectorAll and index them.

---

## DOM Element Reference

### Student Data (Bottom Left Table - Index 2)

**Cell ID Pattern:** r{rowNum}td{colNum}

| Column | Cell ID Pattern | Content | CSS Class |
|--------|-----------------|---------|-----------|
| 0 | r{N}td0 | Row number (1, 2, 3...) | defaultGrading |
| 1 | r{N}td1 | **Local ID** (student ID) | defaultGrading |
| 2 | r{N}td2 | **Student Name** (Last, First) | studentNameGrading |
| 3 | r{N}td3 | Grade Level | defaultGrading |
| 4 | r{N}td4 | School Code | defaultGrading |
| 5-11 | r{N}td5-11 | D, S, G, A links | defaultGrading |

**Row Numbers:**
- Rows 0-2: Header rows
- Rows 3+: Student data rows (first student is row 7)

### Grade Cells (Bottom Right Table - Index 3)

**Grade Link ID Pattern:** {studentLocalId}^{assignmentId}

Example: 30008159^6546912 = Student 30008159 grade for assignment 6546912

---

## Data Extraction Functions

### Extract All Students

```javascript
function extractStudents() {
  const students = [];
  for (let row = 7; row <= 50; row++) {
    const localIdCell = document.getElementById("r" + row + "td1");
    if (!localIdCell) continue;
    const localId = localIdCell.textContent.trim();
    if (/^[0-9]+$/.test(localId) && localId.length >= 5) {
      const nameCell = document.getElementById("r" + row + "td2");
      students.push({
        localId: localId,
        name: nameCell?.textContent?.trim() || "",
        rowNum: row
      });
    }
  }
  return students;
}
```

### Extract All Assignments

```javascript
function extractAssignments() {
  const assignments = [];
  const seenIds = {};
  const allLinks = document.getElementsByTagName("a");
  for (let i = 0; i < allLinks.length; i++) {
    const href = allLinks[i].getAttribute("href") || "";
    const match = href.match(/assignmentId=([0-9]+)/);
    if (match && !seenIds[match[1]]) {
      seenIds[match[1]] = true;
      const name = allLinks[i].textContent.trim();
      if (name && name.length > 0 && name.length < 60) {
        assignments.push({ id: match[1], name: name });
      }
    }
  }
  return assignments;
}
```

---

## Grade Entry Mechanism

### Step 1: Click Grade Cell to Activate Edit Mode

When you click a grade link, the system:
1. Replaces the link with a text input
2. Input has id=replaceObjectParam1
3. Input has onchange=secGrdLocalSaveCellValueGB(this)

### Step 2: Enter New Grade Value

```javascript
function setGradeValue(studentId, assignmentId, newValue) {
  const linkId = studentId + "^" + assignmentId;
  const gradeLink = document.getElementById(linkId);
  if (!gradeLink) throw new Error("Grade cell not found");
  gradeLink.click();
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const input = document.getElementById("replaceObjectParam1");
      if (!input) { reject(new Error("Input not found")); return; }
      input.value = newValue;
      input.onchange();
      resolve(true);
    }, 100);
  });
}
```

---

## Important TEAMS JavaScript Functions

| Function | Purpose |
|----------|---------|
| secGrdLocalSaveCellValueGB(el) | Saves a single grade cell |
| secGrdLocalCalculateCellValue() | Recalculates averages |
| TeamsBlockUI.blockPageLite() | Shows loading overlay |

---

## URL Patterns

| Page | URL Pattern |
|------|-------------|
| Section Search | /grading/EntryPointSectionGradingSearchResultsAction.do |
| Gradebook View | /grading/SectionGradingSearchResultsSelectAction.do |
| Assignment Setup | /grading/ReloadSetupAction.do?assignmentId={id} |
| Grade Cycle Change | /grading/GradebookSectionStartAction.do?selectedGradeCycle={MP1-MP6} |

---

## Matching Students Between Systems

**Challenge:** Google Classroom uses email/Google ID, TEAMS uses Local ID.

**Approaches:**
1. **Name Matching** - Match on Last, First format
2. **Student ID Mapping** - Create mapping table in extension storage
3. **Email Domain Mapping** - If email = {studentID}@waco.k12.tx.us

---

## Extension Architecture

```
extension/
  manifest.json
  background.js          # Service worker for Google Classroom API
  content-script.js      # Injected into TEAMS pages
  popup/
    popup.html
    popup.js
  lib/
    teams-api.js
    classroom-api.js
    student-matcher.js
```

**Permissions Needed:**
- https://waco.teams.hosting/* - TEAMS access
- https://classroom.googleapis.com/* - Google Classroom API
- identity - For Google OAuth
