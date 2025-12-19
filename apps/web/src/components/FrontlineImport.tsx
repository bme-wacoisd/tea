import { useRef, useState } from 'react';
import type { FrontlineRoster, FrontlineStudent } from '../types';
import {
  parseFrontlineCSV,
  saveFrontlineRoster,
  loadFrontlineRoster,
  clearFrontlineRoster,
  getUniquePeriods,
  getStudentsForPeriod,
  getCourseNameForPeriod,
} from '../lib/rosterCompare';

interface FrontlineImportProps {
  onImport: (roster: FrontlineRoster) => void;
  roster: FrontlineRoster | null;
}

interface PreviewData {
  students: FrontlineStudent[];
  fileName: string;
}

function FrontlineImport({ onImport, roster }: FrontlineImportProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);

    try {
      const content = await file.text();
      const students = parseFrontlineCSV(content);

      if (students.length === 0) {
        setError('No students found in CSV. Check the file format.');
        return;
      }

      setPreview({ students, fileName: file.name });
    } catch (err) {
      setError(`Failed to read file: ${err}`);
    }
  };

  const handleConfirmImport = () => {
    if (!preview) return;

    const savedRoster = saveFrontlineRoster(preview.students, preview.fileName);
    onImport(savedRoster);
    setPreview(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleCancelPreview = () => {
    setPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleClearData = () => {
    clearFrontlineRoster();
    onImport(null as unknown as FrontlineRoster);
  };

  const handleReload = () => {
    const stored = loadFrontlineRoster();
    if (stored) {
      onImport(stored);
    }
  };

  if (preview) {
    const periods = getUniquePeriods(preview.students);
    return (
      <div className="import-preview">
        <h3>Import Preview: {preview.fileName}</h3>
        <p>
          Found <strong>{preview.students.length}</strong> records across{' '}
          <strong>{periods.length}</strong> periods
        </p>

        <div className="preview-periods">
          {periods.map((period) => {
            const students = getStudentsForPeriod(preview.students, period);
            const course = getCourseNameForPeriod(preview.students, period);
            return (
              <div key={period} className="preview-period">
                <span className="period-badge">Period {period}</span>
                <span className="course-name">{course}</span>
                <span className="student-count">{students.length} students</span>
              </div>
            );
          })}
        </div>

        <div className="preview-actions">
          <button
            className="button button-primary"
            onClick={handleConfirmImport}
          >
            Import Data
          </button>
          <button
            className="button button-secondary"
            onClick={handleCancelPreview}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="frontline-import">
      <div className="import-header">
        <h3>Frontline TEAMS Roster</h3>
        {roster && (
          <span className="import-status">
            Imported: {new Date(roster.importedAt).toLocaleDateString()}
          </span>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      {roster ? (
        <div className="roster-summary">
          <p>
            <strong>{roster.students.length}</strong> records from{' '}
            <strong>{roster.fileName}</strong>
          </p>
          <div className="summary-periods">
            {getUniquePeriods(roster.students).map((period) => {
              const count = getStudentsForPeriod(roster.students, period).length;
              return (
                <span key={period} className="period-chip">
                  P{period}: {count}
                </span>
              );
            })}
          </div>
          <div className="roster-actions">
            <label className="button button-secondary">
              Re-import CSV
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </label>
            <button
              className="button button-secondary"
              onClick={handleClearData}
            >
              Clear Data
            </button>
          </div>
        </div>
      ) : (
        <div className="no-roster">
          <p>No Frontline roster imported. Import a CSV to compare with Google Classroom.</p>
          <label className="button button-primary">
            Import CSV
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </label>
          <button
            className="button button-secondary"
            onClick={handleReload}
            style={{ marginLeft: '0.5rem' }}
          >
            Load from Storage
          </button>
        </div>
      )}
    </div>
  );
}

export default FrontlineImport;
