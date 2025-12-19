export interface GoogleUser {
  email: string;
  name: string;
  picture: string;
}

export interface Course {
  id: string;
  name: string;
  section?: string;
  descriptionHeading?: string;
  description?: string;
  room?: string;
  ownerId: string;
  creationTime?: string;
  updateTime?: string;
  enrollmentCode?: string;
  courseState?: string;
  alternateLink?: string;
  teacherGroupEmail?: string;
  courseGroupEmail?: string;
  guardiansEnabled?: boolean;
  calendarId?: string;
}

export interface Student {
  courseId: string;
  userId: string;
  profile: {
    id: string;
    name: {
      givenName: string;
      familyName: string;
      fullName: string;
    };
    emailAddress: string;
    photoUrl?: string;
  };
}

export interface CoursesResponse {
  courses?: Course[];
  nextPageToken?: string;
}

export interface StudentsResponse {
  students?: Student[];
  nextPageToken?: string;
}

export interface Invitation {
  id: string;
  userId: string;
  courseId: string;
  role: string;
}

export interface InvitationsResponse {
  invitations?: Invitation[];
  nextPageToken?: string;
}

/**
 * Frontline TEAMS roster data (imported from CSV)
 */
export interface FrontlineStudent {
  studentName: string; // "Last, First Middle"
  course: string;      // "CLGTRN DC", "INPRAC", etc.
  section: string;     // Section number
  period: string;      // "01", "02", etc.
  day: string;         // "A", "B", etc.
  teacher: string;     // "Last, First"
}

export interface FrontlineRoster {
  students: FrontlineStudent[];
  importedAt: string;  // ISO timestamp
  fileName: string;
}

/**
 * Comparison result types
 */
export interface ComparisonResult {
  period: string;
  courseName: string;
  gcCourseId?: string;
  gcCourseName?: string;
  frontlineStudents: string[];
  gcStudents: string[];
  gcInvited: string[];       // Invited but not yet accepted
  missingFromGC: string[];   // In Frontline but not in GC (not even invited)
  pendingInGC: string[];     // In Frontline and invited, but not accepted
  extraInGC: string[];       // In GC but not in Frontline
  matched: string[];         // In both (accepted)
}

export interface RosterDiff {
  comparisons: ComparisonResult[];
  unmatchedPeriods: string[];
  summary: {
    totalFrontline: number;
    totalGC: number;
    totalInvited: number;
    totalMissing: number;
    totalPending: number;
    totalExtra: number;
    totalMatched: number;
  };
}
