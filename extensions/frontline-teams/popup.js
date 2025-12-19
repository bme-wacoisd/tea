/**
 * Frontline TEAMS Roster Sync - Popup
 * One-shot comparison between Frontline TEAMS and Google Classroom
 */

(function() {
  'use strict';

  const elements = {};
  let frontlineData = null;
  let gcData = null;

  async function init() {
    cacheElements();
    await loadSettings();
    await loadStoredData();
    await checkCurrentPage();
    setupEventListeners();
  }

  function cacheElements() {
    const ids = [
      'page-status', 'extract-btn', 'extract-all-btn', 'compare-btn', 'data-section',
      'student-count', 'course-count', 'extract-time', 'student-list',
      'comparison-section', 'matched-count', 'missing-count', 'extra-count',
      'missing-list', 'missing-students', 'extra-list', 'extra-students',
      'export-csv-btn', 'copy-btn', 'gc-client-id', 'day-count', 'clear-data-btn'
    ];
    ids.forEach(id => {
      elements[id] = document.getElementById(id.replace(/-/g, ''));
      if (!elements[id]) elements[id] = document.getElementById(id);
    });
    // Manual mapping for elements with different naming
    elements.pageStatus = document.getElementById('page-status');
    elements.extractBtn = document.getElementById('extract-btn');
    elements.extractAllBtn = document.getElementById('extract-all-btn');
    elements.compareBtn = document.getElementById('compare-btn');
    elements.dataSection = document.getElementById('data-section');
    elements.studentCount = document.getElementById('student-count');
    elements.courseCount = document.getElementById('course-count');
    elements.extractTime = document.getElementById('extract-time');
    elements.studentList = document.getElementById('student-list');
    elements.comparisonSection = document.getElementById('comparison-section');
    elements.matchedCount = document.getElementById('matched-count');
    elements.missingCount = document.getElementById('missing-count');
    elements.extraCount = document.getElementById('extra-count');
    elements.missingList = document.getElementById('missing-list');
    elements.missingStudents = document.getElementById('missing-students');
    elements.extraList = document.getElementById('extra-list');
    elements.extraStudents = document.getElementById('extra-students');
    elements.exportCsvBtn = document.getElementById('export-csv-btn');
    elements.copyBtn = document.getElementById('copy-btn');
    elements.gcClientId = document.getElementById('gc-client-id');
    elements.dayCount = document.getElementById('day-count');
    elements.clearDataBtn = document.getElementById('clear-data-btn');
    elements.markAttendanceBtn = document.getElementById('mark-attendance-btn');
  }

  async function loadSettings() {
    return new Promise(resolve => {
      chrome.storage.local.get(['googleClientId', 'dayCount'], result => {
        if (elements.gcClientId && result.googleClientId) {
          elements.gcClientId.value = result.googleClientId;
        }
        if (elements.dayCount) {
          elements.dayCount.value = result.dayCount || '3';
        }
        resolve();
      });
    });
  }

  function saveSettings() {
    const settings = {};
    if (elements.gcClientId?.value) {
      settings.googleClientId = elements.gcClientId.value.trim();
    }
    if (elements.dayCount?.value) {
      settings.dayCount = elements.dayCount.value;
    }
    chrome.storage.local.set(settings);
  }

  async function loadStoredData() {
    return new Promise(resolve => {
      chrome.storage.local.get(['frontlineData', 'googleClassroomData', 'frontlineHistory'], result => {
        if (result.frontlineData) {
          frontlineData = result.frontlineData;
          displayFrontlineData(frontlineData);
        }
        if (result.googleClassroomData) {
          gcData = result.googleClassroomData;
        }
        resolve();
      });
    });
  }

  async function checkCurrentPage() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab.url || !tab.url.includes('teams.hosting')) {
        updateStatus('warning', '⚠️', 'Go to waco.teams.hosting to extract data');
        return;
      }

      chrome.tabs.sendMessage(tab.id, { action: 'getPageInfo' }, response => {
        if (chrome.runtime.lastError) {
          updateStatus('warning', '🔄', 'Reload the TEAMS page');
          return;
        }

        if (response?.pageType === 'attendance') {
          updateStatus('success', '✅', 'Ready: Attendance page detected');
          if (elements.extractBtn) elements.extractBtn.disabled = false;
          if (elements.extractAllBtn) elements.extractAllBtn.disabled = false;
          if (elements.markAttendanceBtn) elements.markAttendanceBtn.disabled = false;
        } else if (response?.pageType === 'roster') {
          updateStatus('success', '✅', 'Ready: Roster page detected');
          if (elements.extractBtn) elements.extractBtn.disabled = false;
        } else {
          updateStatus('warning', 'ℹ️', 'Navigate to Take Classroom Attendance');
        }
      });
    } catch (error) {
      updateStatus('error', '❌', 'Error: ' + error.message);
    }
  }

  function updateStatus(type, icon, message) {
    if (!elements.pageStatus) return;
    elements.pageStatus.className = `status-card ${type}`;
    elements.pageStatus.innerHTML = `
      <span class="status-icon">${icon}</span>
      <span class="status-text">${message}</span>
    `;
  }

  function displayFrontlineData(data) {
    if (!data) return;

    if (elements.dataSection) elements.dataSection.classList.remove('hidden');

    const students = data.students || [];
    const realStudents = students.filter(s => s.studentName && !s.isPlaceholder);
    const uniqueCourses = new Set(students.map(s => s.courseDescription || s.courseId).filter(Boolean));
    const uniquePeriods = new Set(students.map(s => s.period).filter(Boolean));

    if (elements.studentCount) elements.studentCount.textContent = realStudents.length;
    if (elements.courseCount) elements.courseCount.textContent = uniquePeriods.size;

    if (elements.extractTime && (data.lastExtracted || data.extractedAt)) {
      const date = new Date(data.lastExtracted || data.extractedAt);
      elements.extractTime.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Show extraction info
    if (elements.studentList) {
      elements.studentList.innerHTML = '';

      // Check if this is a class list page (no actual students)
      if (data.pageType === 'classlist' || (data.classes && realStudents.length === 0)) {
        const warning = document.createElement('div');
        warning.className = 'extraction-warning';
        warning.innerHTML = `
          <strong>Class List Detected</strong><br>
          <small>
            Found ${data.classCount || uniquePeriods.size} classes/periods.<br>
            <br>
            Click <strong>"Extract All Classes"</strong> to automatically<br>
            navigate through each class and extract all students.
          </small>
        `;
        elements.studentList.appendChild(warning);

        // Keep extract button enabled so user can start automatic extraction
        if (elements.extractAllBtn) elements.extractAllBtn.disabled = false;
        // Don't enable compare button if no real students
        if (elements.compareBtn) elements.compareBtn.disabled = true;
        return;
      }

      if (data.multiDay && data.arrangements) {
        // Multi-day extraction - show arrangements found
        const info = document.createElement('div');
        info.className = 'extraction-info';
        info.innerHTML = `
          <strong>Multi-day extraction complete</strong><br>
          <small>
            Found ${data.uniqueArrangementsFound} unique day arrangements<br>
            Checked ${data.daysChecked} school days, skipped ${data.emptyDays} holidays<br>
            Dates: ${data.arrangements.map(a => a.date).join(', ')}
          </small>
        `;
        elements.studentList.appendChild(info);
      } else if (data.date) {
        const info = document.createElement('div');
        info.className = 'extraction-info';
        info.innerHTML = `<small>Extracted from: ${data.date}</small>`;
        elements.studentList.appendChild(info);
      }

      // Show student count with names preview
      if (realStudents.length > 0) {
        const studentInfo = document.createElement('div');
        studentInfo.className = 'student-preview';
        const preview = realStudents.slice(0, 5).map(s => escapeHtml(s.studentName)).join(', ');
        const more = realStudents.length > 5 ? ` +${realStudents.length - 5} more` : '';
        studentInfo.innerHTML = `<strong>${realStudents.length} students:</strong> ${preview}${more}`;
        elements.studentList.appendChild(studentInfo);
      }

      // Show periods summary
      if (uniquePeriods.size > 0) {
        const periodInfo = document.createElement('div');
        periodInfo.className = 'period-summary';
        periodInfo.innerHTML = `<strong>Periods:</strong> ${Array.from(uniquePeriods).sort().join(', ')}`;
        elements.studentList.appendChild(periodInfo);
      }
    }

    if (elements.exportCsvBtn) elements.exportCsvBtn.disabled = false;
    if (elements.copyBtn) elements.copyBtn.disabled = false;
    if (elements.compareBtn) elements.compareBtn.disabled = (realStudents.length === 0);
  }

  async function extractData() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (elements.extractBtn) {
        elements.extractBtn.disabled = true;
        elements.extractBtn.textContent = 'Extracting...';
      }

      chrome.tabs.sendMessage(tab.id, { action: 'extractData' }, response => {
        if (elements.extractBtn) {
          elements.extractBtn.disabled = false;
          elements.extractBtn.textContent = 'Extract Today Only';
        }

        if (chrome.runtime.lastError) {
          updateStatus('error', '❌', 'Reload the TEAMS page and try again');
          return;
        }

        if (response?.students?.length > 0) {
          frontlineData = response;
          displayFrontlineData(response);
          updateStatus('success', '✅', `Extracted ${response.students.length} records`);
        } else {
          updateStatus('warning', '⚠️', 'No data found on this page');
        }
      });
    } catch (error) {
      updateStatus('error', '❌', error.message);
      if (elements.extractBtn) {
        elements.extractBtn.disabled = false;
        elements.extractBtn.textContent = 'Extract Today Only';
      }
    }
  }

  /**
   * Extract from multiple days automatically (A/B/C day support)
   */
  async function extractAllDays() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (elements.extractAllBtn) {
        elements.extractAllBtn.disabled = true;
        elements.extractAllBtn.innerHTML = '<span class="btn-icon">⏳</span> Scanning...';
      }

      updateStatus('info', '🔄', 'Starting multi-day extraction...');

      // Start the extraction - it will send progress messages
      chrome.tabs.sendMessage(tab.id, { action: 'extractMultipleDays' }, response => {
        if (chrome.runtime.lastError) {
          updateStatus('error', '❌', 'Reload the TEAMS page and try again');
          resetExtractAllButton();
          return;
        }

        if (!response?.started) {
          updateStatus('error', '❌', 'Failed to start extraction');
          resetExtractAllButton();
        }
        // Results will come via extractionComplete message
      });
    } catch (error) {
      updateStatus('error', '❌', error.message);
      resetExtractAllButton();
    }
  }

  function resetExtractAllButton() {
    if (elements.extractAllBtn) {
      elements.extractAllBtn.disabled = false;
      elements.extractAllBtn.innerHTML = '<span class="btn-icon">📋</span> Extract All Classes';
    }
  }

  /**
   * Start attendance marking across all classes
   */
  async function startAttendanceSession() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (elements.markAttendanceBtn) {
        elements.markAttendanceBtn.disabled = true;
        elements.markAttendanceBtn.innerHTML = '<span class="btn-icon">⏳</span> Starting...';
      }

      updateStatus('info', '🔄', 'Starting attendance marking...');

      chrome.tabs.sendMessage(tab.id, { action: 'startAttendanceSession' }, response => {
        if (chrome.runtime.lastError) {
          updateStatus('error', '❌', 'Reload the TEAMS page and try again');
          resetMarkAttendanceButton();
          return;
        }

        if (response?.success) {
          updateStatus('info', '✓', `Started attendance for ${response.classCount} classes`);
        } else {
          updateStatus('error', '❌', response?.message || 'Failed to start');
          resetMarkAttendanceButton();
        }
      });
    } catch (error) {
      updateStatus('error', '❌', error.message);
      resetMarkAttendanceButton();
    }
  }

  function resetMarkAttendanceButton() {
    if (elements.markAttendanceBtn) {
      elements.markAttendanceBtn.disabled = false;
      elements.markAttendanceBtn.innerHTML = '<span class="btn-icon">✓</span> Mark Attendance (All Classes)';
    }
  }

  async function runComparison() {
    // Check for Google Client ID
    const clientId = elements.gcClientId?.value?.trim();
    if (!clientId) {
      updateStatus('error', '❌', 'Enter Google Client ID in Settings');
      return;
    }

    // Save client ID
    await GoogleClassroom.setClientId(clientId);

    if (!frontlineData?.students?.length) {
      updateStatus('error', '❌', 'Extract Frontline data first');
      return;
    }

    if (elements.compareBtn) {
      elements.compareBtn.disabled = true;
      elements.compareBtn.innerHTML = '<span class="btn-icon">⏳</span> Connecting...';
    }

    try {
      // Fetch Google Classroom data
      gcData = await GoogleClassroom.fetchAllData(msg => {
        updateStatus('info', '🔄', msg);
      });

      updateStatus('info', '🔄', 'Comparing rosters...');

      // Run comparison
      const results = RosterCompare.compare(frontlineData, gcData);

      // Display results
      displayComparisonResults(results);

      updateStatus('success', '✅', `Found ${results.issues.length} discrepancies`);

    } catch (error) {
      console.error('Comparison error:', error);
      updateStatus('error', '❌', error.message);
    } finally {
      if (elements.compareBtn) {
        elements.compareBtn.disabled = false;
        elements.compareBtn.innerHTML = '<span class="btn-icon">🔍</span> Compare with Google Classroom';
      }
    }
  }

  function displayComparisonResults(results) {
    if (elements.comparisonSection) {
      elements.comparisonSection.classList.remove('hidden');
    }

    if (elements.matchedCount) elements.matchedCount.textContent = results.summary.matched;
    if (elements.missingCount) elements.missingCount.textContent = results.summary.missingFromGC;
    if (elements.extraCount) elements.extraCount.textContent = results.summary.extraInGC;

    // Display missing students by period
    if (results.missingFromGC.length > 0 && elements.missingList && elements.missingStudents) {
      elements.missingList.classList.remove('hidden');

      // Group by period
      const byPeriod = {};
      for (const s of results.missingFromGC) {
        const p = s.period || 'Unknown';
        if (!byPeriod[p]) byPeriod[p] = [];
        byPeriod[p].push(s);
      }

      let html = '';
      for (const [period, students] of Object.entries(byPeriod).sort((a, b) => a[0].localeCompare(b[0]))) {
        const course = students[0]?.gcCourse || students[0]?.course || '';
        html += `<li class="period-group"><strong>Period ${escapeHtml(period)}</strong> (${escapeHtml(course)})<ul>`;
        html += students.map(s => `<li>${escapeHtml(s.name)}</li>`).join('');
        html += '</ul></li>';
      }
      elements.missingStudents.innerHTML = html;
    } else if (elements.missingList) {
      elements.missingList.classList.add('hidden');
    }

    // Display extra students by period
    if (results.extraInGC.length > 0 && elements.extraList && elements.extraStudents) {
      elements.extraList.classList.remove('hidden');

      // Group by period
      const byPeriod = {};
      for (const s of results.extraInGC) {
        const p = s.period || 'Unknown';
        if (!byPeriod[p]) byPeriod[p] = [];
        byPeriod[p].push(s);
      }

      let html = '';
      for (const [period, students] of Object.entries(byPeriod).sort((a, b) => a[0].localeCompare(b[0]))) {
        const course = students[0]?.gcCourse || '';
        html += `<li class="period-group"><strong>Period ${escapeHtml(period)}</strong> (${escapeHtml(course)})<ul>`;
        html += students.map(s => `<li>${escapeHtml(s.name)}${s.email ? ` <small>${escapeHtml(s.email)}</small>` : ''}</li>`).join('');
        html += '</ul></li>';
      }
      elements.extraStudents.innerHTML = html;
    } else if (elements.extraList) {
      elements.extraList.classList.add('hidden');
    }

    // Show unmatched periods warning
    if (results.unmatchedPeriods?.length > 0) {
      const warning = document.createElement('div');
      warning.className = 'unmatched-warning';
      warning.innerHTML = `<strong>⚠️ No GC class found for:</strong> ${results.unmatchedPeriods.map(p => `Period ${p.period}`).join(', ')}`;
      if (elements.comparisonSection) {
        const existing = elements.comparisonSection.querySelector('.unmatched-warning');
        if (existing) existing.remove();
        elements.comparisonSection.insertBefore(warning, elements.comparisonSection.firstChild.nextSibling);
      }
    }

    // Store results
    chrome.storage.local.set({
      lastComparison: results,
      lastComparisonTime: new Date().toISOString()
    });
  }

  function exportCSV() {
    if (!frontlineData?.students) return;

    const headers = ['Student Name', 'Course', 'Section', 'Period', 'Day', 'Teacher'];
    const rows = [
      headers.join(','),
      ...frontlineData.students.map(s => [
        `"${(s.studentName || '').replace(/"/g, '""')}"`,
        `"${(s.courseDescription || s.courseId || '').replace(/"/g, '""')}"`,
        s.sectionId || '',
        s.period || '',
        s.day || '',
        `"${(s.teacherName || '').replace(/"/g, '""')}"`
      ].join(','))
    ];

    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `frontline-roster-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copyToClipboard() {
    if (!frontlineData?.students) return;

    const text = frontlineData.students.map(s =>
      `${s.studentName || ''} - ${s.courseDescription || s.courseId || ''} - Period ${s.period || ''}`
    ).join('\n');

    try {
      await navigator.clipboard.writeText(text);
      if (elements.copyBtn) {
        elements.copyBtn.innerHTML = '<span class="btn-icon">✅</span> Copied!';
        setTimeout(() => {
          elements.copyBtn.innerHTML = '<span class="btn-icon">📋</span> Copy to Clipboard';
        }, 2000);
      }
    } catch (error) {
      console.error('Copy failed:', error);
    }
  }

  function clearAllData() {
    chrome.storage.local.remove([
      'frontlineData', 'frontlineHistory', 'googleClassroomData',
      'gcAccessToken', 'gcTokenExpiry', 'lastComparison'
    ], () => {
      frontlineData = null;
      gcData = null;
      if (elements.dataSection) elements.dataSection.classList.add('hidden');
      if (elements.comparisonSection) elements.comparisonSection.classList.add('hidden');
      updateStatus('success', '✅', 'All data cleared');
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  function setupEventListeners() {
    if (elements.extractBtn) {
      elements.extractBtn.addEventListener('click', extractData);
    }
    if (elements.extractAllBtn) {
      elements.extractAllBtn.addEventListener('click', extractAllDays);
    }
    if (elements.compareBtn) {
      elements.compareBtn.addEventListener('click', runComparison);
    }
    if (elements.exportCsvBtn) {
      elements.exportCsvBtn.addEventListener('click', exportCSV);
    }
    if (elements.copyBtn) {
      elements.copyBtn.addEventListener('click', copyToClipboard);
    }
    if (elements.gcClientId) {
      elements.gcClientId.addEventListener('change', saveSettings);
    }
    if (elements.dayCount) {
      elements.dayCount.addEventListener('change', saveSettings);
    }
    if (elements.clearDataBtn) {
      elements.clearDataBtn.addEventListener('click', clearAllData);
    }
    if (elements.markAttendanceBtn) {
      elements.markAttendanceBtn.addEventListener('click', startAttendanceSession);
    }

    // Listen for messages from content script
    chrome.runtime.onMessage.addListener((request) => {
      if (request.action === 'dataExtracted' && request.data) {
        frontlineData = request.data;
        displayFrontlineData(request.data);
      }
      if (request.action === 'extractionProgress') {
        updateStatus('info', '🔄', request.message);
      }
      if (request.action === 'extractionComplete') {
        frontlineData = request.data;
        displayFrontlineData(request.data);
        resetExtractAllButton();

        const msg = request.data?.multiDay
          ? `Found ${request.data.uniqueArrangementsFound} day types, ${request.data.recordCount} records`
          : `Extracted ${request.data?.recordCount || 0} records`;
        updateStatus('success', '✅', msg);
      }
      if (request.action === 'attendanceComplete') {
        const { totalMarked, classesProcessed } = request.data || {};
        updateStatus('success', '✅', `Done! Marked ${totalMarked} absences across ${classesProcessed} classes`);
        resetMarkAttendanceButton();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
