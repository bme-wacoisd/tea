/**
 * Frontline TEAMS Roster Sync - Background Service Worker
 */

// Listen for installation
chrome.runtime.onInstalled.addListener((details) => {
  console.log('TEAMS Sync Extension installed:', details.reason);

  // Set default settings
  chrome.storage.local.get(['settings'], (result) => {
    if (!result.settings) {
      chrome.storage.local.set({
        settings: {
          autoExtract: true,
          showNotifications: true,
          gcCourseId: ''
        }
      });
    }
  });
});

// Listen for messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Background received message:', request.action);

  switch (request.action) {
    case 'dataExtracted':
      // Store the extracted data
      chrome.storage.local.set({
        frontlineData: request.data,
        lastExtracted: new Date().toISOString()
      });

      // Notify any open popups
      chrome.runtime.sendMessage({
        action: 'dataUpdated',
        data: request.data
      }).catch(() => {
        // Popup might not be open, that's okay
      });
      break;

    case 'getStoredData':
      chrome.storage.local.get(['frontlineData', 'lastExtracted'], (result) => {
        sendResponse(result);
      });
      return true; // Keep channel open for async response

    case 'clearData':
      chrome.storage.local.remove(['frontlineData', 'lastExtracted'], () => {
        sendResponse({ success: true });
      });
      return true;

    case 'storeGoogleClassroomData':
      chrome.storage.local.set({
        googleClassroomData: request.data,
        gcLastSync: new Date().toISOString()
      });
      sendResponse({ success: true });
      return true;
  }
});

// Listen for tab updates to detect navigation to TEAMS pages
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    if (tab.url.includes('teams.hosting')) {
      // Update extension icon to show it's active
      chrome.action.setIcon({
        tabId: tabId,
        path: {
          '16': 'icons/icon16-active.png',
          '48': 'icons/icon48-active.png',
          '128': 'icons/icon128-active.png'
        }
      }).catch(() => {
        // Fallback if active icons don't exist
      });

      // Badge to indicate TEAMS page
      chrome.action.setBadgeText({
        tabId: tabId,
        text: '✓'
      }).catch(() => {});

      chrome.action.setBadgeBackgroundColor({
        tabId: tabId,
        color: '#34a853'
      }).catch(() => {});
    } else {
      // Reset icon for non-TEAMS pages
      chrome.action.setBadgeText({
        tabId: tabId,
        text: ''
      }).catch(() => {});
    }
  }
});

// Context menu for quick actions
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'extract-roster',
    title: 'Extract Roster Data',
    contexts: ['page'],
    documentUrlPatterns: ['https://*.teams.hosting/*']
  });

  chrome.contextMenus.create({
    id: 'export-csv',
    title: 'Export to CSV',
    contexts: ['page'],
    documentUrlPatterns: ['https://*.teams.hosting/*']
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  switch (info.menuItemId) {
    case 'extract-roster':
      chrome.tabs.sendMessage(tab.id, { action: 'extractData' });
      break;
    case 'export-csv':
      // Trigger CSV export through content script
      chrome.tabs.sendMessage(tab.id, { action: 'exportCSV' });
      break;
  }
});
