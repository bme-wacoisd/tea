/**
 * Frontline TEAMS Content Script
 * Extracts student roster data from Take Classroom Attendance
 * Handles A/B/C day rotating schedules with automatic multi-day extraction
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    uniqueDaysNeeded: 3,      // Number of distinct day arrangements to find
    maxWeeksBack: 3,          // Maximum weeks to search back
    maxDaysBack: 21,          // 3 weeks
    extractionDelay: 2000,    // Wait for page to load after date change
  };

  /**
   * Detect which page type we're on
   */
  function detectPageType() {
    const pageTitle = document.querySelector('.pageTitle');
    if (pageTitle) {
      const title = pageTitle.textContent.trim().toLowerCase();
      if (title.includes('attendance')) return 'attendance';
      if (title.includes('roster')) return 'roster';
    }
    if (document.getElementById('tableBodyTable')) return 'attendance';
    if (document.getElementById('scheduleTableBodyTable')) return 'roster';
    return 'unknown';
  }

  /**
   * Get current selected date from the page
   */
  function getCurrentDate() {
    // Look for date picker or date display
    const dateInput = document.querySelector('input[name*="date"], input[name*="Date"], #attendanceDate');
    if (dateInput) return dateInput.value;

    const dateDisplay = document.querySelector('.selectedDate, .current-date, [id*="date"]');
    if (dateDisplay) return dateDisplay.textContent.trim();

    return new Date().toISOString().split('T')[0];
  }

  /**
   * Get the day type (A, B, C, etc.) from the page if displayed
   */
  function getDayType() {
    // Look for day type indicator
    const dayIndicators = document.querySelectorAll('.dayType, .day-indicator, [class*="day-type"]');
    for (const el of dayIndicators) {
      const text = el.textContent.trim();
      if (/^[A-Z]\s*Day$/i.test(text)) {
        return text.charAt(0).toUpperCase();
      }
    }

    // Check table headers or cells for day info
    const dayHeader = document.querySelector('[columnid="rfdCalDayCodeId"]');
    if (dayHeader) {
      const dayCell = document.querySelector('td[title]');
      // Day code might be in cells
    }

    return null;
  }

  /**
   * Extract column headers from table
   */
  function extractColumnHeaders(tableId) {
    const headerTable = document.getElementById(tableId + 'HeaderTable') ||
                        document.querySelector(`#${tableId}Table thead, #${tableId} thead`);
    if (!headerTable) return [];

    const headers = [];
    const headerCells = headerTable.querySelectorAll('th');

    headerCells.forEach((th, index) => {
      const columnId = th.getAttribute('columnid') || `col_${index}`;
      const titleDiv = th.querySelector('.table-handle');
      const title = titleDiv ? titleDiv.getAttribute('title') || titleDiv.textContent : th.textContent;
      headers.push({ index, columnId, title: title.trim() });
    });

    return headers;
  }

  /**
   * Check if we're on the class list page (no students) vs a class roster page (has students)
   */
  function isClassListPage() {
    // Check if page title says "Section Periods" - that's the class list
    const titleSpan = document.querySelector('.sst-title');
    if (titleSpan && titleSpan.textContent.includes('Section Periods')) {
      return true;
    }
    // Check if there's no studentFullName column
    const hasStudentColumn = document.querySelector('th[columnid="studentFullName"], th[columnid="studentName"]');
    return !hasStudentColumn;
  }

  /**
   * Get list of class rows to click through
   */
  function getClassRows() {
    const tableBody = document.getElementById('tableBodyTable');
    if (!tableBody) return [];
    return Array.from(tableBody.querySelectorAll('tr[id^="table-row-"]'));
  }

  /**
   * Extract class info from the section periods list (attendance page)
   */
  function extractClassList() {
    const tableBody = document.getElementById('tableBodyTable');
    if (!tableBody) return [];

    const headers = extractColumnHeaders('table');
    const rows = tableBody.querySelectorAll('tr[id^="table-row-"]');
    const classes = [];

    rows.forEach((row, index) => {
      const cells = row.querySelectorAll('td');
      const rowData = {};

      headers.forEach((header, idx) => {
        if (cells[idx]) {
          rowData[header.columnId] = cells[idx].getAttribute('title') || cells[idx].textContent.trim();
        }
      });

      classes.push({
        index,
        rowId: row.id,
        period: rowData.stuCalPeriodId || '',
        courseDescription: rowData.locCourseShortDesc || '',
        courseId: rowData.distCourseId || '',
        sectionId: rowData.locCrsSectionId || '',
        term: rowData.studentCalTermType || '',
        day: rowData.rfdCalDayCodeId || '',
        teacherName: rowData.teacherName || '',
        element: row
      });
    });

    return classes;
  }

  /**
   * Extract student roster from a class detail page
   */
  function extractStudentRoster() {
    // Look for the roster table - try multiple possible table IDs
    // Class Roster List has: table2BodyTable (main roster), tableBodyTable (dropped), scheduleTableBodyTable
    const possibleIds = [
      'table2BodyTable',      // Main roster table on Class Roster List
      'rosterTableBodyTable', // Possible roster table ID
      'tableBodyTable',       // Generic table
      'scheduleTableBodyTable' // Schedule table
    ];

    let tableBody = null;
    let tableId = '';

    for (const id of possibleIds) {
      const el = document.getElementById(id);
      if (el && el.querySelectorAll('tr').length > 0) {
        tableBody = el;
        tableId = id.replace('BodyTable', '');
        console.log('TEAMS Sync: Found roster table:', id, 'with', el.querySelectorAll('tr').length, 'rows');
        break;
      }
    }

    if (!tableBody) {
      console.log('TEAMS Sync: No roster table found');
      return [];
    }

    const headers = extractColumnHeaders(tableId);
    console.log('TEAMS Sync: Headers:', headers.map(h => h.columnId));

    // Try multiple row selectors
    let rows = tableBody.querySelectorAll('tr.odd, tr.even');
    if (rows.length === 0) {
      rows = tableBody.querySelectorAll('tr[id^="table-row-"]');
    }
    if (rows.length === 0) {
      rows = tableBody.querySelectorAll('tr');
    }

    console.log('TEAMS Sync: Found', rows.length, 'rows');

    const students = [];

    rows.forEach((row, rowIndex) => {
      const cells = row.querySelectorAll('td');
      if (cells.length === 0) return;

      const rowData = {};

      // Try header-based extraction first
      if (headers.length > 0) {
        headers.forEach((header, index) => {
          if (cells[index]) {
            rowData[header.columnId] = cells[index].getAttribute('title') || cells[index].textContent.trim();
          }
        });
      } else {
        // Fallback: just get all cell values by index
        cells.forEach((cell, idx) => {
          rowData[`col${idx}`] = cell.getAttribute('title') || cell.textContent.trim();
        });
      }

      // Extract student name - check multiple possible column IDs and positions
      let studentName = rowData.studentFullName || rowData.studentName || rowData.stuName || '';

      // If no name found by column ID, try to find it in raw cells
      if (!studentName) {
        // Student name is often in the 2nd column (after checkbox)
        for (let i = 0; i < Math.min(cells.length, 4); i++) {
          const text = cells[i].getAttribute('title') || cells[i].textContent.trim();
          // Look for text that looks like a name (has comma for Last, First format)
          if (text && text.includes(',') && !text.match(/^\d/) && text.length > 3) {
            studentName = text;
            break;
          }
        }
      }

      if (studentName && studentName !== '' && !studentName.startsWith('[')) {
        students.push({
          studentName,
          studentId: rowData.perId || rowData.studentId || rowData.col2 || '',
          grade: rowData.rfsGradeCode || rowData.stuGradeLevel || rowData.col4 || '',
          gender: rowData.perGender || rowData.col3 || '',
          raw: rowData
        });
      }
    });

    console.log('TEAMS Sync: Extracted', students.length, 'students');
    return students;
  }

  /**
   * Click on a class row and wait for roster to load
   */
  async function clickClassRow(row) {
    return new Promise((resolve) => {
      // Find clickable element in the row
      const clickable = row.querySelector('a, td[onclick], .clickable') || row.querySelector('td');
      if (clickable) {
        clickable.click();
      } else {
        row.click();
      }
      // Wait for page to potentially update
      setTimeout(resolve, 1500);
    });
  }

  /**
   * Extract all class/student data from the attendance table
   * Now handles both class list page and roster pages
   */
  function extractAttendanceData() {
    // First check if we're on class list vs roster
    if (isClassListPage()) {
      console.log('TEAMS Sync: On class list page (no students visible)');
      // Return the class list info
      const classes = extractClassList();
      return {
        pageType: 'classlist',
        extractedAt: new Date().toISOString(),
        date: getCurrentDate(),
        message: 'This page shows classes, not students. Use "Extract All Days" to navigate into each class.',
        classCount: classes.length,
        classes: classes,
        students: [], // No students on this page
        recordCount: 0
      };
    }

    // We're on a roster page - extract students
    const students = extractStudentRoster();
    const tableBody = document.getElementById('tableBodyTable') || document.getElementById('rosterTableBodyTable');
    const headers = extractColumnHeaders('table') || extractColumnHeaders('rosterTable');

    // Try to get class info from page
    const classInfo = {
      period: document.querySelector('[name="period"], #period')?.value || '',
      courseId: document.querySelector('[name="courseId"], #courseId')?.value || '',
      sectionId: document.querySelector('[name="sectionId"], #sectionId')?.value || ''
    };

    const dayTypes = new Set();
    const records = students.map(s => ({
      ...s,
      ...classInfo,
      day: s.raw?.rfdCalDayCodeId || ''
    }));

    records.forEach(r => {
      if (r.day) dayTypes.add(r.day);
    });

    return {
      pageType: 'roster',
      extractedAt: new Date().toISOString(),
      date: getCurrentDate(),
      dayType: dayTypes.size === 1 ? Array.from(dayTypes)[0] : null,
      dayTypes: Array.from(dayTypes),
      headers,
      recordCount: records.length,
      uniqueStudents: new Set(records.map(r => r.studentName)).size,
      students: records
    };
  }

  /**
   * Extract data from Class Roster List page
   */
  function extractRosterData() {
    const possibleIds = ['rosterTableBodyTable', 'scheduleTableBodyTable', 'tableBodyTable'];
    let tableBody = null;
    let tableId = '';

    for (const id of possibleIds) {
      tableBody = document.getElementById(id);
      if (tableBody) {
        tableId = id.replace('BodyTable', '');
        break;
      }
    }

    if (!tableBody) {
      tableBody = document.querySelector('.ssTable tbody');
    }

    if (!tableBody) return null;

    const headers = extractColumnHeaders(tableId || 'table');
    const rows = tableBody.querySelectorAll('tr.odd, tr.even, tr[id^="table-row-"]');
    const records = [];

    rows.forEach(row => {
      const cells = row.querySelectorAll('td');
      if (cells.length === 0) return;

      const rowData = {};
      headers.forEach((header, index) => {
        if (cells[index]) {
          rowData[header.columnId] = cells[index].getAttribute('title') || cells[index].textContent.trim();
        }
      });

      records.push({
        rowId: row.id || `row_${records.length}`,
        studentId: rowData.studentId || '',
        studentName: rowData.studentName || rowData.studentFullName || '',
        grade: rowData.stuGradeLevel || '',
        status: rowData.studentCrsReqSchedStatus || '',
        courseId: rowData.courseId || rowData.distCourseId || '',
        courseDescription: rowData.locCourseShortDesc || '',
        sectionId: rowData.locCrsSectionId || '',
        term: rowData.studentCalTermType || '',
        period: rowData.stuCalPeriodId || '',
        day: rowData.rfdCalDayCodeId || '',
        teacher: rowData.locCrsSecTeacherSeqId || rowData.teacherName || '',
        room: rowData.locationRoomNumber || '',
        raw: rowData
      });
    });

    return {
      pageType: 'roster',
      extractedAt: new Date().toISOString(),
      date: getCurrentDate(),
      headers,
      studentCount: records.length,
      students: records
    };
  }

  /**
   * Main extraction function
   */
  function extractData() {
    const pageType = detectPageType();
    console.log('TEAMS Sync: Page type:', pageType);

    switch (pageType) {
      case 'attendance':
        return extractAttendanceData();
      case 'roster':
        return extractRosterData();
      default:
        return {
          pageType: 'unknown',
          url: window.location.href,
          message: 'Navigate to Take Classroom Attendance page'
        };
    }
  }

  /**
   * Save extracted data, merging with existing data from other days
   */
  function saveToStorage(data) {
    if (!data || !data.students) return;

    chrome.storage.local.get(['frontlineData', 'frontlineHistory'], (result) => {
      const history = result.frontlineHistory || [];

      // Add current extraction to history
      history.unshift({
        date: data.date,
        dayType: data.dayType,
        extractedAt: data.extractedAt,
        recordCount: data.recordCount
      });

      // Keep last 30 extractions
      if (history.length > 30) history.length = 30;

      // Merge with existing data
      const existing = result.frontlineData || { students: [], allClasses: new Set() };
      const mergedStudents = [...(existing.students || [])];
      const seenKeys = new Set(mergedStudents.map(s =>
        `${s.studentName}-${s.courseId}-${s.period}-${s.day}`
      ));

      for (const student of data.students) {
        const key = `${student.studentName}-${student.courseId}-${student.period}-${student.day}`;
        if (!seenKeys.has(key)) {
          mergedStudents.push(student);
          seenKeys.add(key);
        }
      }

      const merged = {
        ...data,
        students: mergedStudents,
        recordCount: mergedStudents.length,
        lastExtracted: data.extractedAt,
        extractionCount: history.length
      };

      chrome.storage.local.set({
        frontlineData: merged,
        frontlineHistory: history,
        lastExtracted: new Date().toISOString()
      });

      console.log('TEAMS Sync: Saved', mergedStudents.length, 'total records');
    });
  }

  /**
   * Add floating extract button
   */
  function addExtractButton() {
    if (document.getElementById('teams-sync-button')) return;

    const button = document.createElement('button');
    button.id = 'teams-sync-button';
    button.innerHTML = '📋 Extract Roster';
    button.title = 'Extract for Google Classroom sync';

    button.addEventListener('click', () => {
      const data = extractData();
      if (data && data.students) {
        saveToStorage(data);
        showNotification(`Extracted ${data.recordCount || data.students.length} records`);
        chrome.runtime.sendMessage({ action: 'dataExtracted', data });
      } else {
        showNotification('No data found', 'error');
      }
    });

    document.body.appendChild(button);
  }

  /**
   * Show notification
   */
  function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `teams-sync-notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => {
      notification.classList.add('fade-out');
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  /**
   * Check if a date is a weekend
   */
  function isWeekend(date) {
    const day = date.getDay();
    return day === 0 || day === 6; // Sunday = 0, Saturday = 6
  }

  /**
   * Format date as MM/DD/YYYY for Frontline
   */
  function formatDateForFrontline(date) {
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const yyyy = date.getFullYear();
    return `${mm}/${dd}/${yyyy}`;
  }

  /**
   * Find and interact with the date picker
   */
  function findDateInput() {
    // Try various selectors for the date input
    const selectors = [
      'input[name*="attendanceDate"]',
      'input[name*="AttendanceDate"]',
      'input[name*="date"]',
      'input.datepicker',
      'input[type="text"][onclick*="calendar"]',
      '#attendanceDate',
      'input[id*="date" i]'
    ];

    for (const selector of selectors) {
      const input = document.querySelector(selector);
      if (input) return input;
    }

    // Look for any input near a calendar icon
    const calendarIcons = document.querySelectorAll('img[src*="calendar"], .fa-calendar, [class*="calendar"]');
    for (const icon of calendarIcons) {
      const parent = icon.closest('td, div, span');
      if (parent) {
        const input = parent.querySelector('input') || parent.previousElementSibling;
        if (input && input.tagName === 'INPUT') return input;
      }
    }

    return null;
  }

  /**
   * Change the date and trigger page reload
   */
  async function changeDate(newDate) {
    const dateInput = findDateInput();
    if (!dateInput) {
      console.error('TEAMS Sync: Could not find date input');
      return false;
    }

    const dateStr = formatDateForFrontline(newDate);
    console.log('TEAMS Sync: Changing date to', dateStr);

    // Set the value
    dateInput.value = dateStr;

    // Trigger change events
    dateInput.dispatchEvent(new Event('change', { bubbles: true }));
    dateInput.dispatchEvent(new Event('blur', { bubbles: true }));

    // Look for a "Go" or refresh button
    const goButtons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
    for (const btn of goButtons) {
      const text = (btn.value || btn.textContent || '').toLowerCase();
      if (text.includes('go') || text.includes('refresh') || text.includes('search')) {
        btn.click();
        return true;
      }
    }

    // Try submitting the form
    const form = dateInput.closest('form');
    if (form) {
      // Look for submit function or button
      const submitBtn = form.querySelector('input[type="submit"], button[type="submit"]');
      if (submitBtn) {
        submitBtn.click();
        return true;
      }
    }

    // Trigger onchange if it exists
    if (dateInput.onchange) {
      dateInput.onchange();
      return true;
    }

    return true;
  }

  /**
   * Wait for page content to update
   */
  function waitForUpdate(timeout = 3000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const tableBody = document.getElementById('tableBodyTable');
      const initialContent = tableBody?.innerHTML || '';

      const checkUpdate = () => {
        const currentContent = tableBody?.innerHTML || '';
        if (currentContent !== initialContent || Date.now() - startTime > timeout) {
          setTimeout(resolve, 500); // Extra wait for rendering
        } else {
          setTimeout(checkUpdate, 200);
        }
      };

      setTimeout(checkUpdate, 500);
    });
  }

  /**
   * Generate a signature for the class arrangement (to detect A/B/C days)
   * Based on which course/period combinations are present
   */
  function getClassArrangementSignature(data) {
    if (!data?.students?.length) return null;

    // Create a signature from unique course-period combinations
    const combinations = new Set();
    for (const student of data.students) {
      const key = `${student.period || ''}-${student.courseId || student.courseDescription || ''}`;
      combinations.add(key);
    }

    // Sort and join to create consistent signature
    return Array.from(combinations).sort().join('|');
  }

  /**
   * Click a row and trigger double-click to open class roster
   */
  async function selectAndOpenClass(row, index) {
    return new Promise((resolve, reject) => {
      try {
        console.log('TEAMS Sync: Opening class at index', index, 'row:', row.id);

        // Remove selection from any currently selected row
        const selectedRows = document.querySelectorAll('#tableBodyTable tr.tableSelected');
        selectedRows.forEach(r => r.classList.remove('tableSelected'));

        // Click to select this row
        row.click();
        row.classList.add('tableSelected');

        // Wait a moment for selection
        setTimeout(() => {
          // Try to trigger double-click (which calls tableOnDoubleClick)
          const dblClickEvent = new MouseEvent('dblclick', {
            bubbles: true,
            cancelable: true,
            view: window
          });
          row.dispatchEvent(dblClickEvent);

          // Also try calling the global tableOnDoubleClick if it exists
          if (typeof window.tableOnDoubleClick === 'function') {
            console.log('TEAMS Sync: Calling tableOnDoubleClick directly');
            window.tableOnDoubleClick(row);
          }

          // Also try calling the submit function directly if it exists
          if (typeof window.submitSectionAttendanceSearchResult === 'function') {
            console.log('TEAMS Sync: Calling submitSectionAttendanceSearchResult');
            window.submitSectionAttendanceSearchResult();
          }

          // The page will navigate - resolve after a delay
          setTimeout(resolve, 500);
        }, 300);
      } catch (err) {
        console.error('TEAMS Sync: Error selecting class:', err);
        reject(err);
      }
    });
  }

  /**
   * Wait for page to navigate and load roster
   */
  function waitForRosterPage(timeout = 10000) {
    return new Promise((resolve) => {
      const startTime = Date.now();

      const checkForRoster = () => {
        // Look for student name column (indicates we're on a roster page)
        const hasStudentCol = document.querySelector('th[columnid="studentFullName"], th[columnid="studentName"]');
        // Or look for a roster table with student rows
        const hasStudentRows = document.querySelectorAll('tr.odd td, tr.even td').length > 0;

        if (hasStudentCol || (Date.now() - startTime > timeout)) {
          setTimeout(resolve, 500); // Extra wait for content
        } else {
          setTimeout(checkForRoster, 300);
        }
      };

      checkForRoster();
    });
  }

  /**
   * Get extraction session from chrome.storage.local
   */
  async function getExtractionSession() {
    return new Promise(resolve => {
      chrome.storage.local.get(['extractionSession'], result => {
        resolve(result.extractionSession || null);
      });
    });
  }

  /**
   * Save extraction session to chrome.storage.local
   */
  async function saveExtractionSession(session) {
    return new Promise(resolve => {
      chrome.storage.local.set({ extractionSession: session }, resolve);
    });
  }

  /**
   * Clear extraction session
   */
  async function clearExtractionSession() {
    return new Promise(resolve => {
      chrome.storage.local.remove(['extractionSession'], resolve);
    });
  }

  /**
   * Extract students from ALL classes by navigating through each one
   * This is the main automation function
   */
  async function extractAllClassesAutomatically(progressCallback) {
    const allStudents = [];
    const classesExtracted = [];

    // Get list of classes first
    const classes = extractClassList();

    if (classes.length === 0) {
      if (progressCallback) progressCallback('No classes found');
      return { students: [], classes: [] };
    }

    // Get existing session from chrome.storage.local
    let sessionData = await getExtractionSession();

    // If this is a fresh start, initialize
    if (!sessionData || !sessionData.inProgress || sessionData.classes.length === 0) {
      sessionData = {
        classes: classes.map(c => ({
          period: c.period,
          courseDescription: c.courseDescription,
          courseId: c.courseId,
          sectionId: c.sectionId,
          day: c.day,
          term: c.term,
          teacherName: c.teacherName,
          rowId: c.rowId
        })),
        students: [],
        currentIndex: 0,
        returnUrl: window.location.href,
        inProgress: true,
        startedAt: new Date().toISOString()
      };
      await saveExtractionSession(sessionData);
      console.log('TEAMS Sync: Started new extraction session');
    } else {
      console.log('TEAMS Sync: Resuming extraction session at index', sessionData.currentIndex);
    }

    if (progressCallback) {
      progressCallback(`Starting extraction of ${sessionData.classes.length} classes...`);
    }

    // Get current class to process
    const currentIndex = sessionData.currentIndex;
    if (currentIndex < sessionData.classes.length) {
      const classInfo = sessionData.classes[currentIndex];
      if (progressCallback) {
        progressCallback(`Opening Period ${classInfo.period} - ${classInfo.courseDescription} (${currentIndex + 1}/${sessionData.classes.length})...`);
      }

      // Find the row element
      const rows = document.querySelectorAll('#tableBodyTable tr[id^="table-row-"]');
      const row = rows[currentIndex];

      if (row) {
        // Update index for next iteration
        sessionData.currentIndex = currentIndex + 1;
        await saveExtractionSession(sessionData);

        // Navigate to the class roster
        await selectAndOpenClass(row, currentIndex);
        // Page will navigate - the next page load will continue extraction
      } else {
        console.error('TEAMS Sync: Could not find row at index', currentIndex);
      }
    }

    return sessionData;
  }

  /**
   * Check if we're in the middle of an extraction session and continue
   */
  async function checkAndContinueExtraction() {
    const sessionData = await getExtractionSession();

    if (!sessionData || !sessionData.inProgress) {
      console.log('TEAMS Sync: No active extraction session');
      return null;
    }

    console.log('TEAMS Sync: Found active session, currentIndex:', sessionData.currentIndex);

    // We're on a roster page - extract students
    if (!isClassListPage()) {
      const students = extractStudentRoster();
      const currentIndex = sessionData.currentIndex - 1; // We incremented before navigation
      const classInfo = sessionData.classes[currentIndex];

      if (classInfo && students.length > 0) {
        // Add class info to each student
        const studentsWithClass = students.map(s => ({
          ...s,
          period: classInfo.period,
          courseDescription: classInfo.courseDescription,
          courseId: classInfo.courseId,
          sectionId: classInfo.sectionId,
          day: classInfo.day,
          teacherName: classInfo.teacherName
        }));

        sessionData.students.push(...studentsWithClass);
        await saveExtractionSession(sessionData);

        console.log(`TEAMS Sync: Extracted ${students.length} students from ${classInfo.courseDescription}`);
      } else if (classInfo) {
        console.log(`TEAMS Sync: No students found for ${classInfo.courseDescription}`);
      }

      // Wait for user to click Cancel button to return to class list
      if (sessionData.currentIndex < sessionData.classes.length) {
        // DO NOT auto-navigate - wait for user to click Cancel button
        const remaining = sessionData.classes.length - sessionData.currentIndex;
        console.log('TEAMS Sync: Waiting for user to click Cancel. Remaining:', remaining);
        showNotification(`Got ${students.length} from Period ${classInfo?.period || '?'}. Click CANCEL (${remaining} left)`);
        // Extraction will resume automatically when user navigates back to class list
      } else {
        // Done! Save final results and clear session
        const finalResults = {
          pageType: 'roster',
          extractedAt: new Date().toISOString(),
          multiClass: true,
          classCount: sessionData.classes.length,
          students: sessionData.students,
          recordCount: sessionData.students.length,
          classes: sessionData.classes
        };

        // Save to chrome storage
        chrome.storage.local.set({ frontlineData: finalResults }, () => {
          console.log('TEAMS Sync: Extraction complete!', finalResults.recordCount, 'students from', finalResults.classCount, 'classes');
        });

        // Clear extraction session
        await clearExtractionSession();

        showNotification(`Done! Extracted ${finalResults.recordCount} students from ${finalResults.classCount} classes`);

        // Notify popup
        chrome.runtime.sendMessage({
          action: 'extractionComplete',
          data: finalResults
        });

        return finalResults;
      }
    } else {
      // We're back on class list - continue to next class
      if (sessionData.currentIndex < sessionData.classes.length) {
        // Longer delay to avoid rate limiting and session issues
        console.log('TEAMS Sync: Back on class list, continuing in 2s...');
        setTimeout(() => {
          extractAllClassesAutomatically((msg) => {
            chrome.runtime.sendMessage({ action: 'extractionProgress', message: msg });
          });
        }, 2000);
      }
    }

    return null;
  }

  /**
   * Automatically extract data from multiple days to capture all rotations
   */
  async function extractMultipleDays(progressCallback) {
    // First, check if we're on class list page
    if (isClassListPage()) {
      if (progressCallback) {
        progressCallback('Detected class list page. Extracting class information...');
      }

      const classes = extractClassList();

      if (classes.length === 0) {
        return {
          pageType: 'classlist',
          error: 'No classes found. Please navigate to Take Classroom Attendance.',
          students: [],
          recordCount: 0
        };
      }

      // On class list page, we can only get class info, not students
      // Return the classes with instruction
      const result = {
        pageType: 'classlist',
        extractedAt: new Date().toISOString(),
        message: 'To get student names, click on a class row in TEAMS to view its roster, then extract from that page.',
        classCount: classes.length,
        classes: classes.map(c => ({
          period: c.period,
          courseDescription: c.courseDescription,
          courseId: c.courseId,
          sectionId: c.sectionId,
          day: c.day,
          term: c.term,
          teacherName: c.teacherName
        })),
        // Create placeholder records with class info but no students
        students: classes.map(c => ({
          period: c.period,
          courseDescription: c.courseDescription,
          courseId: c.courseId,
          sectionId: c.sectionId,
          day: c.day,
          teacherName: c.teacherName,
          studentName: `[Click Period ${c.period} in TEAMS to see students]`,
          isPlaceholder: true
        })),
        recordCount: classes.length
      };

      if (progressCallback) {
        progressCallback(`Found ${classes.length} classes. Click each class in TEAMS to view student rosters.`);
      }

      return result;
    }

    // We're on a roster page - extract students normally
    const uniqueArrangements = new Map();
    const allStudents = [];
    let currentDate = new Date();
    let daysChecked = 0;
    let emptyDays = 0;

    // Get config from storage
    const config = await new Promise(resolve => {
      chrome.storage.local.get(['dayCount'], result => {
        resolve({
          uniqueDaysNeeded: parseInt(result.dayCount) || CONFIG.uniqueDaysNeeded
        });
      });
    });

    if (progressCallback) {
      progressCallback(`Starting extraction from roster page...`);
    }

    // Try to extract from current page first
    const currentData = extractAttendanceData();
    if (currentData?.students?.length > 0) {
      for (const student of currentData.students) {
        student.extractedDate = formatDateForFrontline(currentDate);
      }
      allStudents.push(...currentData.students);

      if (progressCallback) {
        progressCallback(`Extracted ${currentData.students.length} students from current page`);
      }
    }

    // Compile results
    const result = {
      pageType: 'roster',
      extractedAt: new Date().toISOString(),
      multiDay: false,
      daysChecked: 1,
      emptyDays: 0,
      uniqueArrangementsFound: 1,
      students: allStudents,
      recordCount: allStudents.length
    };

    // Deduplicate students
    const seen = new Set();
    result.students = result.students.filter(s => {
      const key = `${s.studentName}-${s.courseId}-${s.period}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    result.recordCount = result.students.length;

    if (progressCallback) {
      progressCallback(`Done! Extracted ${result.recordCount} student records`);
    }

    return result;
  }

  /**
   * Detect if we're on a Class Roster List page (attendance marking page)
   */
  function isClassRosterListPage() {
    // Check page title
    const pageTitle = document.querySelector('.pageTitle');
    if (pageTitle && pageTitle.textContent.trim().toLowerCase().includes('class roster list')) {
      return true;
    }
    // Check for studentAttendanceType radio buttons (the P/A-R/T columns)
    const attendRadio = document.querySelector('input[name^="studentAttendanceType_"]');
    return !!attendRadio;
  }

  /**
   * Mark attendance for students who have red "A" indicator
   * Red "A" means they have absences and need attendance marked today
   */
  function markAttendanceForAbsentStudents() {
    if (!isClassRosterListPage()) {
      console.log('TEAMS Sync: Not on Class Roster List page');
      return { success: false, message: 'Not on Class Roster List page', marked: 0 };
    }

    const results = {
      checked: 0,
      marked: 0,
      alreadyMarked: 0,
      skipped: 0,
      students: []
    };

    // Find all student rows (odd/even class in table2BodyTable)
    const studentRows = document.querySelectorAll('#table2BodyTable tbody tr.odd, #table2BodyTable tbody tr.even');

    studentRows.forEach((row, index) => {
      results.checked++;

      // Find the "A" indicator (attendAll link) in the S A G column
      const attendAllLink = row.querySelector('a[name="attendAll"]');
      if (!attendAllLink) {
        results.skipped++;
        return;
      }

      // Check if the "A" span has red class (indicates student needs attendance marked)
      const aSpan = attendAllLink.querySelector('span.infoBoxB');
      if (!aSpan) {
        results.skipped++;
        return;
      }

      const isRed = aSpan.classList.contains('red');

      // Get student name from row (2nd column)
      const nameTd = row.querySelector('td:nth-child(2)');
      const studentName = nameTd ? nameTd.textContent.trim() : `Student ${index}`;

      if (isRed) {
        // Student has red indicator - mark them absent
        // Find the ABS radio button for this row
        const absRadio = row.querySelector(`input[name="studentAttendanceType_${index}"][value="ABS"]`);

        if (absRadio && !absRadio.checked) {
          absRadio.click();
          results.marked++;
          results.students.push({ name: studentName, action: 'marked absent' });
          console.log('TEAMS Sync: Marked absent:', studentName);
        } else if (absRadio && absRadio.checked) {
          results.alreadyMarked++;
          results.students.push({ name: studentName, action: 'already marked' });
        } else {
          // Try alternative selector with dynamic ID
          const absRadioAlt = row.querySelector(`input[id^="studentAttendanceType${index}ABS"]`);
          if (absRadioAlt && !absRadioAlt.checked) {
            absRadioAlt.click();
            results.marked++;
            results.students.push({ name: studentName, action: 'marked absent' });
            console.log('TEAMS Sync: Marked absent (alt):', studentName);
          } else if (absRadioAlt && absRadioAlt.checked) {
            results.alreadyMarked++;
          } else {
            results.skipped++;
          }
        }
      } else {
        // Student has green indicator - skip
        results.skipped++;
      }
    });

    console.log('TEAMS Sync: Attendance marking complete', results);

    // Show notification
    if (results.marked > 0) {
      showNotification(`Marked ${results.marked} student(s) absent. Click POST when ready.`);
    } else if (results.alreadyMarked > 0) {
      showNotification(`All ${results.alreadyMarked} absent student(s) already marked.`);
    } else {
      showNotification('No students needed attendance marking (all green).');
    }

    return {
      success: true,
      message: `Checked ${results.checked}, marked ${results.marked}, already marked ${results.alreadyMarked}`,
      ...results
    };
  }

  /**
   * Get attendance session from chrome.storage.local
   */
  async function getAttendanceSession() {
    return new Promise(resolve => {
      chrome.storage.local.get(['attendanceSession'], result => {
        resolve(result.attendanceSession || null);
      });
    });
  }

  /**
   * Save attendance session to chrome.storage.local
   */
  async function saveAttendanceSession(session) {
    return new Promise(resolve => {
      chrome.storage.local.set({ attendanceSession: session }, resolve);
    });
  }

  /**
   * Clear attendance session
   */
  async function clearAttendanceSession() {
    return new Promise(resolve => {
      chrome.storage.local.remove(['attendanceSession'], resolve);
    });
  }

  /**
   * Start automatic attendance marking through all classes
   */
  async function startAttendanceSession() {
    // Must be on class list page to start
    if (!isClassListPage()) {
      return { success: false, message: 'Navigate to Take Classroom Attendance page first' };
    }

    const classes = extractClassList();
    if (classes.length === 0) {
      return { success: false, message: 'No classes found' };
    }

    const session = {
      classes: classes.map(c => ({
        period: c.period,
        courseDescription: c.courseDescription,
        rowId: c.rowId
      })),
      currentIndex: 0,
      totalMarked: 0,
      classesProcessed: 0,
      inProgress: true,
      startedAt: new Date().toISOString()
    };

    await saveAttendanceSession(session);
    showNotification(`Starting attendance for ${classes.length} classes...`);

    // Navigate to first class
    const rows = document.querySelectorAll('#tableBodyTable tr[id^="table-row-"]');
    if (rows[0]) {
      await selectAndOpenClass(rows[0], 0);
    }

    return { success: true, started: true, classCount: classes.length };
  }

  /**
   * Continue attendance session after page load
   */
  async function continueAttendanceSession() {
    const session = await getAttendanceSession();

    if (!session || !session.inProgress) {
      return null;
    }

    // If we're on a roster page, mark attendance
    if (isClassRosterListPage()) {
      const currentIndex = session.currentIndex;
      const classInfo = session.classes[currentIndex];

      console.log('TEAMS Sync: Marking attendance for', classInfo?.courseDescription || `class ${currentIndex}`);

      // Mark attendance for students with red indicator
      const result = markAttendanceForAbsentStudents();

      // Update session
      session.currentIndex++;
      session.classesProcessed++;
      session.totalMarked += result.marked || 0;
      await saveAttendanceSession(session);

      // Show status
      const remaining = session.classes.length - session.currentIndex;
      if (remaining > 0) {
        showNotification(`Period ${classInfo?.period}: ${result.marked || 0} marked. Click POST then CANCEL (${remaining} left)`);
      } else {
        // Done!
        showNotification(`Done! Marked ${session.totalMarked} total absences across ${session.classesProcessed} classes`);
        await clearAttendanceSession();

        chrome.runtime.sendMessage({
          action: 'attendanceComplete',
          data: {
            totalMarked: session.totalMarked,
            classesProcessed: session.classesProcessed
          }
        });
      }

      return result;
    }

    // If we're back on class list, navigate to next class
    if (isClassListPage() && session.currentIndex < session.classes.length) {
      const rows = document.querySelectorAll('#tableBodyTable tr[id^="table-row-"]');
      const row = rows[session.currentIndex];

      if (row) {
        console.log('TEAMS Sync: Navigating to class', session.currentIndex);
        setTimeout(() => {
          selectAndOpenClass(row, session.currentIndex);
        }, 1500);
      }
    }

    return null;
  }

  // Message listener
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      switch (request.action) {
        case 'extractData':
          const data = extractData();
          if (data) saveToStorage(data);
          sendResponse(data);
          break;
        case 'extractMultipleDays':
        case 'extractAllClasses':
          // Check if we're on class list page - start automatic extraction
          if (isClassListPage()) {
            chrome.runtime.sendMessage({ action: 'extractionProgress', message: 'Starting automatic class extraction...' });
            extractAllClassesAutomatically((msg) => {
              chrome.runtime.sendMessage({ action: 'extractionProgress', message: msg });
            });
            sendResponse({ started: true, mode: 'automatic' });
          } else {
            // We're on a roster page - just extract current page
            extractMultipleDays((msg) => {
              chrome.runtime.sendMessage({ action: 'extractionProgress', message: msg });
            }).then(data => {
              if (data) saveToStorage(data);
              chrome.runtime.sendMessage({ action: 'extractionComplete', data });
            });
            sendResponse({ started: true, mode: 'single' });
          }
          break;
        case 'cancelExtraction':
          // Clear extraction session
          sessionStorage.removeItem('teamsRosterExtraction');
          sendResponse({ cancelled: true });
          break;
        case 'markAttendance':
          // Single page attendance marking
          const markResult = markAttendanceForAbsentStudents();
          sendResponse(markResult);
          break;
        case 'startAttendanceSession':
          // Start walking through all classes to mark attendance
          startAttendanceSession().then(result => {
            sendResponse(result);
          });
          return true; // async
        case 'cancelAttendance':
          clearAttendanceSession().then(() => {
            sendResponse({ cancelled: true });
          });
          return true;
        case 'getPageInfo':
          sendResponse({
            pageType: detectPageType(),
            isClassList: isClassListPage(),
            isRosterPage: isClassRosterListPage(),
            date: getCurrentDate(),
            dayType: getDayType(),
            url: window.location.href
          });
          break;
        case 'clearData':
          chrome.storage.local.remove(['frontlineData', 'frontlineHistory', 'extractionSession', 'attendanceSession'], () => {
            console.log('TEAMS Sync: Cleared all data including sessions');
            sendResponse({ success: true });
          });
          return true;
      }
      return true;
    });
  }

  // Initialize
  function init() {
    console.log('TEAMS Sync: Loaded on', window.location.href);
    addExtractButton();

    const pageType = detectPageType();
    const onClassList = isClassListPage();
    const onRosterPage = isClassRosterListPage();
    console.log('TEAMS Sync: Page type:', pageType, 'isClassList:', onClassList, 'isRosterPage:', onRosterPage);

    // Check for in-progress attendance session first
    chrome.storage.local.get(['attendanceSession'], (result) => {
      if (result.attendanceSession?.inProgress) {
        console.log('TEAMS Sync: Found active attendance session, index:', result.attendanceSession.currentIndex);
        setTimeout(() => {
          continueAttendanceSession();
        }, 2000);
        return;
      }

      // Then check for in-progress extraction session
      chrome.storage.local.get(['extractionSession'], (result2) => {
        if (result2.extractionSession?.inProgress) {
          console.log('TEAMS Sync: Found active extraction session, index:', result2.extractionSession.currentIndex);
          // Longer delay to let TEAMS fully initialize
          setTimeout(() => {
            checkAndContinueExtraction();
          }, 2500);
          return; // Don't auto-extract if in a session
        }

        // Auto-extract if on attendance/roster page (but not class list)
        if (pageType === 'attendance' && !onClassList) {
          setTimeout(() => {
            const data = extractData();
            if (data && data.students && data.students.length > 0) {
              saveToStorage(data);
              console.log('TEAMS Sync: Auto-extracted', data.recordCount, 'records');
            }
          }, 1500);
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.TEAMSSync = { extractData, detectPageType, getCurrentDate, getDayType, markAttendanceForAbsentStudents, isClassRosterListPage };
})();
