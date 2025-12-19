# Frontline TEAMS Roster Sync

Chrome extension to extract student rosters from Frontline TEAMS and compare with Google Classroom.

## Features

- **Extract Roster Data**: Automatically extracts student data from "Take Classroom Attendance" and "Class Roster List" pages
- **Export to CSV**: Export extracted data to CSV for backup or import
- **Compare with Google Classroom**: Identify students missing from or extra in Google Classroom
- **Visual Indicators**: Floating button on TEAMS pages for quick extraction
- **Auto-extraction**: Optionally auto-extract data when navigating to roster pages

## Installation

### Method 1: Load as Unpacked Extension (Developer Mode)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extensions/frontline-teams` folder
5. The extension icon will appear in your toolbar

### Method 2: Pack Extension (for distribution)

1. Go to `chrome://extensions/`
2. Click **Pack extension**
3. Select the `extensions/frontline-teams` folder
4. Share the generated `.crx` file

## Usage

### Extracting Data

1. Navigate to Frontline TEAMS: https://waco.teams.hosting/
2. Go to **Take Classroom Attendance** or **Class Roster List**
3. Click the floating **📋 Extract Roster** button, OR
4. Click the extension icon and click **Extract Roster Data**

### Viewing Extracted Data

- Click the extension icon to see:
  - Number of students extracted
  - Number of courses
  - Last extraction time
  - Preview of student list

### Exporting Data

- Click **Export as CSV** to download the roster as a CSV file
- Click **Copy to Clipboard** to copy student list

### Comparing with Google Classroom

1. First, connect Google Classroom via the [web app](https://bme-wacoisd.github.io/google-classroom/)
2. Click **Compare with Google Classroom**
3. See:
  - ✅ **Matched**: Students in both TEAMS and Google Classroom
  - ⚠️ **Missing**: Students in TEAMS but not in Google Classroom
  - ℹ️ **Extra**: Students in Google Classroom but not in TEAMS

## Supported Pages

| Page | URL Pattern | Data Extracted |
|------|-------------|----------------|
| Take Classroom Attendance | `/studattend/*` | Period, Course, Section, Teacher |
| Class Roster List | `/ClassRosterList*` | Student Name, Course, Section, Status |

## Privacy

- All data stays local in your browser
- No data is sent to external servers
- Uses Chrome's local storage API

## Troubleshooting

### Extension not working?

1. Make sure you're on `https://waco.teams.hosting/`
2. Reload the page after installing the extension
3. Check that the extension has permissions for the site

### No data extracted?

- Navigate to a page with student data (attendance or roster page)
- Wait for the page to fully load
- Try clicking the extract button manually

## Development

```bash
# Directory structure
extensions/frontline-teams/
├── manifest.json      # Extension manifest (v3)
├── content.js         # Content script (runs on TEAMS pages)
├── content.css        # Styles for floating button/notifications
├── popup.html         # Extension popup UI
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── background.js      # Service worker
└── icons/            # Extension icons
```

## License

Internal use - Waco ISD
