import type { ComparisonResult, RosterDiff } from '../types';

interface RosterComparisonProps {
  diff: RosterDiff;
  singlePeriod?: string;
}

function RosterComparison({ diff, singlePeriod }: RosterComparisonProps) {
  const comparisons = singlePeriod
    ? diff.comparisons.filter((c) => c.period === singlePeriod)
    : diff.comparisons;

  if (comparisons.length === 0) {
    return (
      <div className="comparison-empty">
        No comparison data available for this period.
      </div>
    );
  }

  return (
    <div className="roster-comparison">
      {!singlePeriod && (
        <div className="comparison-summary">
          <h3>Comparison Summary</h3>
          <div className="summary-stats">
            <div className="stat">
              <span className="stat-value">{diff.summary.totalFrontline}</span>
              <span className="stat-label">Frontline</span>
            </div>
            <div className="stat">
              <span className="stat-value">{diff.summary.totalGC}</span>
              <span className="stat-label">Enrolled in GC</span>
            </div>
            <div className="stat stat-matched">
              <span className="stat-value">{diff.summary.totalMatched}</span>
              <span className="stat-label">Matched</span>
            </div>
            <div className="stat stat-pending">
              <span className="stat-value">{diff.summary.totalPending}</span>
              <span className="stat-label">Pending Invite</span>
            </div>
            <div className="stat stat-missing">
              <span className="stat-value">{diff.summary.totalMissing}</span>
              <span className="stat-label">Not Invited</span>
            </div>
            <div className="stat stat-extra">
              <span className="stat-value">{diff.summary.totalExtra}</span>
              <span className="stat-label">Extra in GC</span>
            </div>
          </div>
          {diff.unmatchedPeriods.length > 0 && (
            <div className="unmatched-warning">
              No matching GC course found for periods:{' '}
              {diff.unmatchedPeriods.join(', ')}
            </div>
          )}
        </div>
      )}

      {comparisons.map((comparison) => (
        <PeriodComparison key={comparison.period} comparison={comparison} />
      ))}
    </div>
  );
}

interface PeriodComparisonProps {
  comparison: ComparisonResult;
}

function PeriodComparison({ comparison }: PeriodComparisonProps) {
  const {
    period,
    courseName,
    gcCourseName,
    frontlineStudents,
    gcStudents,
    missingFromGC,
    pendingInGC,
    extraInGC,
    matched,
  } = comparison;

  const hasIssues = missingFromGC.length > 0 || extraInGC.length > 0;

  return (
    <div className={`period-comparison ${hasIssues ? 'has-issues' : ''}`}>
      <div className="period-header">
        <div className="period-info">
          <span className="period-badge">Period {period}</span>
          <span className="course-names">
            <span className="frontline-course">{courseName}</span>
            {gcCourseName && (
              <>
                <span className="arrow">→</span>
                <span className="gc-course">{gcCourseName}</span>
              </>
            )}
          </span>
        </div>
        <div className="period-stats">
          {matched.length > 0 && (
            <span className="badge badge-success">{matched.length} matched</span>
          )}
          {pendingInGC.length > 0 && (
            <span className="badge badge-pending">{pendingInGC.length} pending</span>
          )}
          {missingFromGC.length > 0 && (
            <span className="badge badge-error">
              {missingFromGC.length} not invited
            </span>
          )}
          {extraInGC.length > 0 && (
            <span className="badge badge-warning">{extraInGC.length} extra</span>
          )}
        </div>
      </div>

      <div className="diff-container">
        <div className="diff-column frontline-column">
          <div className="column-header">
            <span className="column-title">Frontline (Source of Truth)</span>
            <span className="column-count">{frontlineStudents.length}</span>
          </div>
          <div className="student-list">
            {frontlineStudents.map((name) => {
              const isMissing = missingFromGC.includes(name);
              const isPending = pendingInGC.includes(name);
              const isMatched = matched.includes(name);
              let className = 'student-row';
              let icon = '';
              if (isMissing) {
                className += ' missing';
                icon = '❌';
              } else if (isPending) {
                className += ' pending';
                icon = '⏳';
              } else if (isMatched) {
                className += ' matched';
                icon = '✓';
              }
              return (
                <div key={name} className={className}>
                  <span className="status-icon">{icon}</span>
                  <span className="student-name">{name}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="diff-column gc-column">
          <div className="column-header">
            <span className="column-title">Google Classroom</span>
            <span className="column-count">{gcStudents.length}</span>
          </div>
          <div className="student-list">
            {gcStudents.length === 0 ? (
              <div className="no-students">No GC course matched</div>
            ) : (
              gcStudents.map((name) => {
                const isExtra = extraInGC.includes(name);
                return (
                  <div
                    key={name}
                    className={`student-row ${isExtra ? 'extra' : 'matched'}`}
                  >
                    <span className="status-icon">
                      {isExtra ? '⚠️' : '✓'}
                    </span>
                    <span className="student-name">{name}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default RosterComparison;
