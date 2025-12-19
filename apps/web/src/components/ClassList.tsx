import { useState, useEffect } from 'react';
import { Course } from '../types';
import { getCourses } from '../googleApi';

interface ClassListProps {
  onSelectCourse: (course: Course) => void;
}

function ClassList({ onSelectCourse }: ClassListProps) {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      setLoading(true);
      setError(null);
      const fetchedCourses = await getCourses();
      setCourses(fetchedCourses);
    } catch (err) {
      console.error('Error fetching courses:', err);
      setError('Failed to load courses. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading courses...</div>;
  }

  if (error) {
    return (
      <div>
        <div className="error">{error}</div>
        <button onClick={loadCourses} className="button button-primary">
          Retry
        </button>
      </div>
    );
  }

  if (courses.length === 0) {
    return (
      <div className="loading">
        No courses found. Make sure you have access to Google Classroom courses.
      </div>
    );
  }

  const getRandomGradient = (index: number) => {
    const gradients = [
      'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
    ];
    return gradients[index % gradients.length];
  };

  return (
    <div>
      <h2 style={{ marginBottom: '1.5rem', color: '#333' }}>
        My Classes ({courses.length})
      </h2>
      <div className="classes-grid">
        {courses.map((course, index) => (
          <div
            key={course.id}
            className="class-card"
            onClick={() => onSelectCourse(course)}
          >
            <div
              className="class-header"
              style={{ background: getRandomGradient(index) }}
            >
              <div>
                <div className="class-name">{course.name}</div>
                {course.section && (
                  <div className="class-section">{course.section}</div>
                )}
              </div>
            </div>
            <div className="class-body">
              {course.descriptionHeading && (
                <div className="class-description">
                  {course.descriptionHeading}
                </div>
              )}
              <div className="class-meta">
                <span>{course.room || 'No room'}</span>
                <span>→</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ClassList;
