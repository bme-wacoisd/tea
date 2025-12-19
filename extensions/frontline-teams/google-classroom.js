/**
 * Google Classroom API Integration
 * Uses launchWebAuthFlow - no secrets in code, client ID stored locally by user
 */

const GoogleClassroom = {
  accessToken: null,

  SCOPES: [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.profile.emails'
  ].join(' '),

  /**
   * Get client ID from local storage (user must set this in settings)
   */
  async getClientId() {
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(['googleClientId'], (result) => {
        if (result.googleClientId) {
          resolve(result.googleClientId);
        } else {
          reject(new Error('Google Client ID not configured. Go to Settings to add it.'));
        }
      });
    });
  },

  /**
   * Save client ID to local storage
   */
  async setClientId(clientId) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ googleClientId: clientId }, resolve);
    });
  },

  /**
   * Authenticate using launchWebAuthFlow (no secrets in manifest)
   */
  async authenticate() {
    const clientId = await this.getClientId();
    const redirectUri = chrome.identity.getRedirectURL();

    const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
    authUrl.searchParams.set('client_id', clientId);
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('response_type', 'token');
    authUrl.searchParams.set('scope', this.SCOPES);
    authUrl.searchParams.set('prompt', 'consent');

    return new Promise((resolve, reject) => {
      chrome.identity.launchWebAuthFlow(
        { url: authUrl.toString(), interactive: true },
        (responseUrl) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }

          // Extract access token from URL fragment
          const url = new URL(responseUrl);
          const params = new URLSearchParams(url.hash.substring(1));
          const token = params.get('access_token');

          if (token) {
            this.accessToken = token;
            // Store token with expiry
            const expiresIn = parseInt(params.get('expires_in') || '3600');
            chrome.storage.local.set({
              gcAccessToken: token,
              gcTokenExpiry: Date.now() + (expiresIn * 1000)
            });
            resolve(token);
          } else {
            reject(new Error('No access token in response'));
          }
        }
      );
    });
  },

  /**
   * Get stored token if still valid
   */
  async getStoredToken() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['gcAccessToken', 'gcTokenExpiry'], (result) => {
        if (result.gcAccessToken && result.gcTokenExpiry > Date.now()) {
          this.accessToken = result.gcAccessToken;
          resolve(result.gcAccessToken);
        } else {
          resolve(null);
        }
      });
    });
  },

  /**
   * Ensure we have a valid token
   */
  async ensureAuth() {
    let token = await this.getStoredToken();
    if (!token) {
      token = await this.authenticate();
    }
    return token;
  },

  /**
   * Clear stored credentials
   */
  async logout() {
    this.accessToken = null;
    return new Promise((resolve) => {
      chrome.storage.local.remove(['gcAccessToken', 'gcTokenExpiry'], resolve);
    });
  },

  /**
   * Make authenticated API request
   */
  async apiRequest(endpoint) {
    await this.ensureAuth();

    const url = `https://classroom.googleapis.com/v1/${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`
      }
    });

    if (response.status === 401) {
      await this.logout();
      await this.authenticate();
      return this.apiRequest(endpoint);
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error?.message || `API error: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Get all courses for the teacher
   */
  async getCourses() {
    const courses = [];
    let pageToken = null;

    do {
      const params = new URLSearchParams({
        teacherId: 'me',
        courseStates: 'ACTIVE',
        pageSize: '100'
      });
      if (pageToken) params.append('pageToken', pageToken);

      const response = await this.apiRequest(`courses?${params}`);
      if (response.courses) courses.push(...response.courses);
      pageToken = response.nextPageToken;
    } while (pageToken);

    return courses;
  },

  /**
   * Get all students in a course
   */
  async getStudents(courseId) {
    const students = [];
    let pageToken = null;

    do {
      const params = new URLSearchParams({ pageSize: '100' });
      if (pageToken) params.append('pageToken', pageToken);

      const response = await this.apiRequest(`courses/${courseId}/students?${params}`);
      if (response.students) students.push(...response.students);
      pageToken = response.nextPageToken;
    } while (pageToken);

    return students;
  },

  /**
   * Fetch all Google Classroom data
   */
  async fetchAllData(progressCallback) {
    const result = {
      courses: [],
      studentsByCourse: {},
      allStudents: [],
      fetchedAt: new Date().toISOString()
    };

    if (progressCallback) progressCallback('Connecting to Google Classroom...');
    await this.ensureAuth();

    if (progressCallback) progressCallback('Fetching courses...');
    const courses = await this.getCourses();
    result.courses = courses;

    for (let i = 0; i < courses.length; i++) {
      const course = courses[i];
      if (progressCallback) {
        progressCallback(`Fetching ${course.name} (${i + 1}/${courses.length})...`);
      }

      try {
        const students = await this.getStudents(course.id);
        const mappedStudents = students.map(s => ({
          courseId: course.id,
          courseName: course.name,
          name: s.profile?.name?.fullName || '',
          email: s.profile?.emailAddress || '',
          givenName: s.profile?.name?.givenName || '',
          familyName: s.profile?.name?.familyName || ''
        }));

        result.studentsByCourse[course.id] = {
          course: course,
          students: mappedStudents
        };
        result.allStudents.push(...mappedStudents);
      } catch (error) {
        console.error(`Error fetching ${course.name}:`, error);
      }
    }

    // Store for later use
    chrome.storage.local.set({
      googleClassroomData: result,
      gcLastSync: result.fetchedAt
    });

    return result;
  }
};

if (typeof window !== 'undefined') {
  window.GoogleClassroom = GoogleClassroom;
}
