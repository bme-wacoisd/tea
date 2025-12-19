import { useState, useEffect } from 'react';
import { Course, Student } from '../types';
import { getStudents } from '../googleApi';

interface StudentListProps {
  course: Course;
}

function StudentList({ course }: StudentListProps) {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const getInitials = (name: string) => {
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <div className="students-section">
      <h2>
        {course.name} - Students ({loading ? '...' : students.length})
      </h2>
      {course.section && (
        <p style={{ color: '#666', marginBottom: '1rem' }}>{course.section}</p>
      )}

      {loading && <div className="loading">Loading students...</div>}

      {error && (
        <div>
          <div className="error">{error}</div>
          <button onClick={loadStudents} className="button button-primary">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && students.length === 0 && (
        <div className="loading">No students enrolled in this course.</div>
      )}

      {!loading && !error && students.length > 0 && (
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

export default StudentList;
