import { useState, useEffect } from 'react';
import { GoogleUser, Course, FrontlineRoster, RosterDiff, Student } from '../types';
import { getAllStudents, getStudents } from '../googleApi';
import { loadFrontlineRoster, compareRosters, compareForPeriod, extractPeriodFromGCName } from '../lib/rosterCompare';
import ClassList from './ClassList';
import FrontlineImport from './FrontlineImport';
import RosterComparison from './RosterComparison';

type ViewMode = 'classes' | 'compare-all';

interface DashboardProps {
  user: GoogleUser;
  onLogout: () => void;
}

function Dashboard({ user, onLogout }: DashboardProps) {
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('classes');
  const [frontlineRoster, setFrontlineRoster] = useState<FrontlineRoster | null>(null);
  const [comparisonDiff, setComparisonDiff] = useState<RosterDiff | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Load Frontline roster from localStorage on mount
  useEffect(() => {
    const stored = loadFrontlineRoster();
    if (stored) {
      setFrontlineRoster(stored);
    }
  }, []);

  const handleImport = (roster: FrontlineRoster | null) => {
    setFrontlineRoster(roster);
    setComparisonDiff(null);
  };

  const handleCompareAll = async () => {
    if (!frontlineRoster) {
      setError('Please import Frontline roster first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getAllStudents(setLoadingMessage);

      const diff = compareRosters(
        frontlineRoster.students,
        data.courses,
        data.studentsByCourse,
        data.invitedByCourse
      );
      setComparisonDiff(diff);
      setViewMode('compare-all');
    } catch (err) {
      setError(`Failed to load Google Classroom data: ${err}`);
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleSelectCourse = (course: Course) => {
    setSelectedCourse(course);
  };

  const handleBackToClasses = () => {
    setSelectedCourse(null);
    setViewMode('classes');
    setComparisonDiff(null);
  };

  return (
    <div className="container">
      <div className="user-info">
        <div className="user-details">
          <img src={user.picture} alt={user.name} className="user-avatar" />
          <div>
            <div className="user-name">{user.name}</div>
            <div style={{ fontSize: '0.875rem', color: '#666' }}>
              {user.email}
            </div>
          </div>
        </div>
        <button onClick={onLogout} className="button button-secondary">
          Logout
        </button>
      </div>

      {/* Frontline Import Panel */}
      <div className="panel import-panel">
        <FrontlineImport onImport={handleImport} roster={frontlineRoster} />
      </div>

      {error && <div className="error">{error}</div>}

      {/* View Mode Toggle and Compare Button */}
      {!selectedCourse && (
        <div className="view-controls">
          <div className="view-toggle">
            <button
              className={`toggle-btn ${viewMode === 'classes' ? 'active' : ''}`}
              onClick={() => setViewMode('classes')}
            >
              My Classes
            </button>
            <button
              className={`toggle-btn ${viewMode === 'compare-all' ? 'active' : ''}`}
              onClick={() => setViewMode('compare-all')}
              disabled={!comparisonDiff}
            >
              Compare All
            </button>
          </div>
          <button
            className="button button-primary"
            onClick={handleCompareAll}
            disabled={loading || !frontlineRoster}
          >
            {loading ? loadingMessage || 'Loading...' : 'Compare with Google Classroom'}
          </button>
        </div>
      )}

      {/* Main Content */}
      {selectedCourse ? (
        <div>
          <button
            onClick={handleBackToClasses}
            className="button button-secondary back-button"
          >
            ← Back to Classes
          </button>
          <StudentListWithComparison
            course={selectedCourse}
            frontlineRoster={frontlineRoster}
          />
        </div>
      ) : viewMode === 'compare-all' && comparisonDiff ? (
        <RosterComparison diff={comparisonDiff} />
      ) : (
        <ClassList onSelectCourse={handleSelectCourse} />
      )}
    </div>
  );
}

// Enhanced StudentList with comparison
interface StudentListWithComparisonProps {
  course: Course;
  frontlineRoster: FrontlineRoster | null;
}

function StudentListWithComparison({
  course,
  frontlineRoster,
}: StudentListWithComparisonProps) {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState(false);

  useEffect(() => {
    loadStudents();
  }, [course.id]);

  const loadStudents = async () => {
    try {
      setLoading(true);
      setError(null);
      const fetchedStudents = await getStudents(course.id);
      setStudents(fetchedStudents);
    } catch (err) {
      console.error('Error fetching students:', err);
      setError('Failed to load students. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const period = extractPeriodFromGCName(course.name);
  const canCompare = frontlineRoster && period;

  const comparison = canCompare
    ? compareForPeriod(frontlineRoster.students, period, students)
    : null;

  const getInitials = (name: string) => {
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <div className="students-section">
      <div className="section-header">
        <div>
          <h2>
            {course.name} - Students ({loading ? '...' : students.length})
          </h2>
          {course.section && (
            <p style={{ color: '#666', marginBottom: '1rem' }}>{course.section}</p>
          )}
        </div>
        {canCompare && (
          <button
            className={`button ${showComparison ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setShowComparison(!showComparison)}
          >
            {showComparison ? 'Hide Comparison' : 'Compare with Frontline'}
          </button>
        )}
      </div>

      {loading && <div className="loading">Loading students...</div>}

      {error && (
        <div>
          <div className="error">{error}</div>
          <button onClick={loadStudents} className="button button-primary">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && showComparison && comparison && (
        <div className="single-comparison">
          <RosterComparison
            diff={{
              comparisons: [comparison],
              unmatchedPeriods: [],
              summary: {
                totalFrontline: comparison.frontlineStudents.length,
                totalGC: comparison.gcStudents.length,
                totalInvited: comparison.gcInvited.length,
                totalMissing: comparison.missingFromGC.length,
                totalPending: comparison.pendingInGC.length,
                totalExtra: comparison.extraInGC.length,
                totalMatched: comparison.matched.length,
              },
            }}
            singlePeriod={period || undefined}
          />
        </div>
      )}

      {!loading && !error && !showComparison && students.length === 0 && (
        <div className="loading">No students enrolled in this course.</div>
      )}

      {!loading && !error && !showComparison && students.length > 0 && (
        <div className="students-list">
          {students.map((student) => (
            <div key={student.userId} className="student-card">
              {student.profile.photoUrl ? (
                <img
                  src={student.profile.photoUrl}
                  alt={student.profile.name.fullName}
                  className="student-avatar"
                />
              ) : (
                <div className="student-avatar">
                  {getInitials(student.profile.name.fullName)}
                </div>
              )}
              <div className="student-info">
                <div className="student-name">
                  {student.profile.name.fullName}
                </div>
                <div className="student-email">
                  {student.profile.emailAddress}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Dashboard;
