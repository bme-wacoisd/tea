/**
 * Compare Frontline TEAMS roster with Google Classroom
 * Frontline is source of truth
 */

const RosterCompare = {
  /**
   * Extract period number from Frontline period (handles "01" -> 1, "1" -> 1)
   */
  extractPeriod(period) {
    if (!period) return null;
    const num = parseInt(String(period).replace(/^0+/, ''), 10);
    return isNaN(num) ? null : num;
  },

  /**
   * Check if a Google Classroom class name matches a Frontline period
   * Matches: "3 Chemistry" for period "03", "Period 3 - Math" for period "3", etc.
   */
  classMatchesPeriod(gcClassName, frontlinePeriod) {
    if (!gcClassName || !frontlinePeriod) return false;

    const period = this.extractPeriod(frontlinePeriod);
    if (period === null) return false;

    const className = gcClassName.toLowerCase().trim();

    // Pattern 1: Class starts with period number followed by space (e.g., "3 Chemistry")
    if (new RegExp(`^${period}\\s`).test(className)) return true;

    // Pattern 2: Class starts with period number followed by dash (e.g., "3-Chemistry")
    if (new RegExp(`^${period}-`).test(className)) return true;

    // Pattern 3: "Period X" or "Per X" anywhere in name
    if (new RegExp(`period\\s*${period}\\b`, 'i').test(className)) return true;
    if (new RegExp(`per\\s*${period}\\b`, 'i').test(className)) return true;

    // Pattern 4: "(X)" in class name (e.g., "Chemistry (3)")
    if (new RegExp(`\\(${period}\\)`).test(className)) return true;

    // Pattern 5: "P X" or "Pd X" (e.g., "P3 Chemistry" or "Pd 3 Chemistry")
    if (new RegExp(`\\bp${period}\\b`, 'i').test(className)) return true;
    if (new RegExp(`\\bpd\\s*${period}\\b`, 'i').test(className)) return true;

    return false;
  },

  /**
   * Find the Google Classroom course that matches a Frontline period
   */
  findMatchingGCCourse(frontlinePeriod, gcCourses) {
    for (const course of gcCourses) {
      if (this.classMatchesPeriod(course.name, frontlinePeriod)) {
        return course;
      }
    }
    return null;
  },

  /**
   * Normalize student name for comparison
   */
  normalizeName(name) {
    if (!name) return '';
    return name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, ' ')
      .replace(/,\s*/g, ', '); // Normalize "Last,First" to "Last, First"
  },

  /**
   * Parse "Last, First" format to {first, last}
   */
  parseName(name) {
    const normalized = this.normalizeName(name);
    if (normalized.includes(',')) {
      const [last, first] = normalized.split(',').map(s => s.trim());
      return { first, last, full: `${first} ${last}` };
    }
    const parts = normalized.split(' ');
    return {
      first: parts[0] || '',
      last: parts.slice(1).join(' ') || '',
      full: normalized
    };
  },

  /**
   * Check if two names match (handles "Last, First" vs "First Last")
   */
  namesMatch(name1, name2) {
    const n1 = this.parseName(name1);
    const n2 = this.parseName(name2);

    // Exact match on full name
    if (n1.full === n2.full) return true;

    // Match first and last separately
    if (n1.first === n2.first && n1.last === n2.last) return true;

    // Try reversed
    if (n1.first === n2.last && n1.last === n2.first) return true;

    return false;
  },

  /**
   * Find matching student in Google Classroom by name
   */
  findInGoogleClassroom(frontlineStudent, gcStudents) {
    for (const gc of gcStudents) {
      if (this.namesMatch(frontlineStudent, gc.name)) {
        return gc;
      }
    }
    return null;
  },

  /**
   * Main comparison function - compares by period/class
   * @param frontlineData - Data extracted from Frontline TEAMS
   * @param gcData - Data from Google Classroom API
   * @returns Comparison results
   */
  compare(frontlineData, gcData) {
    const results = {
      timestamp: new Date().toISOString(),
      summary: {
        totalFrontline: 0,
        totalGoogleClassroom: 0,
        matched: 0,
        missingFromGC: 0,
        extraInGC: 0,
        periodsMatched: 0,
        periodsUnmatched: 0
      },
      byPeriod: {},
      issues: [],
      missingFromGC: [],
      extraInGC: [],
      unmatchedPeriods: []
    };

    const gcCourses = gcData.courses || [];

    // Group Frontline students by period
    const frontlineByPeriod = new Map();
    for (const record of (frontlineData.students || [])) {
      const period = record.period;
      if (!period) continue;

      if (!frontlineByPeriod.has(period)) {
        frontlineByPeriod.set(period, {
          period,
          courseDesc: record.courseDescription || record.courseId,
          students: new Map()
        });
      }

      const name = this.normalizeName(record.studentName);
      if (name && !frontlineByPeriod.get(period).students.has(name)) {
        frontlineByPeriod.get(period).students.set(name, {
          name: record.studentName,
          normalized: name,
          raw: record
        });
      }
    }

    // Group GC students by course
    const gcByCourse = new Map();
    for (const course of gcCourses) {
      const courseStudents = (gcData.studentsByCourse[course.id]?.students || []);
      gcByCourse.set(course.id, {
        course,
        students: new Map()
      });

      for (const student of courseStudents) {
        const name = this.normalizeName(student.name);
        if (name) {
          gcByCourse.get(course.id).students.set(name, {
            name: student.name,
            email: student.email,
            normalized: name
          });
        }
      }
    }

    // Compare each Frontline period with matching GC course
    for (const [period, flData] of frontlineByPeriod) {
      const matchingCourse = this.findMatchingGCCourse(period, gcCourses);

      results.byPeriod[period] = {
        period,
        frontlineCourse: flData.courseDesc,
        gcCourse: matchingCourse?.name || null,
        matched: [],
        missingFromGC: [],
        extraInGC: []
      };

      if (!matchingCourse) {
        // No matching GC course for this period
        results.unmatchedPeriods.push({
          period,
          frontlineCourse: flData.courseDesc,
          studentCount: flData.students.size
        });
        results.summary.periodsUnmatched++;

        // All students in this period are "missing" from GC
        for (const [, student] of flData.students) {
          results.missingFromGC.push({
            name: student.name,
            period,
            course: flData.courseDesc,
            reason: `No GC class found for period ${period}`
          });
          results.summary.missingFromGC++;
        }
        continue;
      }

      results.summary.periodsMatched++;
      const gcCourseData = gcByCourse.get(matchingCourse.id);
      const gcStudentsInCourse = gcCourseData?.students || new Map();

      // Find students in Frontline but not in GC course
      for (const [flName, flStudent] of flData.students) {
        let found = false;
        let matchedGCName = null;

        // Try exact match first
        if (gcStudentsInCourse.has(flName)) {
          found = true;
          matchedGCName = flName;
        } else {
          // Try fuzzy match
          for (const [gcName] of gcStudentsInCourse) {
            if (this.namesMatch(flName, gcName)) {
              found = true;
              matchedGCName = gcName;
              break;
            }
          }
        }

        if (found) {
          results.byPeriod[period].matched.push(flStudent.name);
          results.summary.matched++;
        } else {
          results.byPeriod[period].missingFromGC.push(flStudent.name);
          results.missingFromGC.push({
            name: flStudent.name,
            period,
            course: flData.courseDesc,
            gcCourse: matchingCourse.name
          });
          results.summary.missingFromGC++;
        }
      }

      // Find students in GC course but not in Frontline
      for (const [gcName, gcStudent] of gcStudentsInCourse) {
        let found = false;

        if (flData.students.has(gcName)) {
          found = true;
        } else {
          for (const [flName] of flData.students) {
            if (this.namesMatch(gcName, flName)) {
              found = true;
              break;
            }
          }
        }

        if (!found) {
          results.byPeriod[period].extraInGC.push(gcStudent.name);
          results.extraInGC.push({
            name: gcStudent.name,
            email: gcStudent.email,
            period,
            gcCourse: matchingCourse.name
          });
          results.summary.extraInGC++;
        }
      }
    }

    // Count totals
    results.summary.totalFrontline = Array.from(frontlineByPeriod.values())
      .reduce((sum, p) => sum + p.students.size, 0);
    results.summary.totalGoogleClassroom = Array.from(gcByCourse.values())
      .reduce((sum, c) => sum + c.students.size, 0);

    // Build issues list for display
    results.issues = [
      ...results.missingFromGC.map(s => ({
        type: 'missing',
        severity: 'error',
        message: `Period ${s.period}: ${s.name} not in Google Classroom`,
        student: s.name,
        period: s.period,
        course: s.gcCourse || s.course
      })),
      ...results.extraInGC.map(s => ({
        type: 'extra',
        severity: 'warning',
        message: `Period ${s.period}: ${s.name} in GC but not in Frontline`,
        student: s.name,
        email: s.email,
        period: s.period,
        course: s.gcCourse
      }))
    ];

    // Sort by period, then by type, then by name
    results.issues.sort((a, b) => {
      const periodA = this.extractPeriod(a.period) || 99;
      const periodB = this.extractPeriod(b.period) || 99;
      if (periodA !== periodB) return periodA - periodB;
      if (a.type !== b.type) return a.type === 'missing' ? -1 : 1;
      return a.student.localeCompare(b.student);
    });

    return results;
  }
};

if (typeof window !== 'undefined') {
  window.RosterCompare = RosterCompare;
}
