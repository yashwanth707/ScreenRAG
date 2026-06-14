/**
 * SummaryPage — Step 3: Session Results
 *
 * Fetches and displays the complete interview summary:
 * - AI-generated analysis
 * - Q&A transcript
 * - Confidence score
 * - Download and restart actions
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession, STEPS } from '../context/SessionContext';
import { getSummary } from '../api/client';
import SessionSummary from '../components/SessionSummary/SessionSummary';
import styles from './SummaryPage.module.css';

export default function SummaryPage() {
  const navigate = useNavigate();
  const { sessionId, resetSession } = useSession();

  const [summaryData, setSummaryData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSummary = async () => {
      if (!sessionId) return;

      setIsLoading(true);
      setError(null);

      try {
        const data = await getSummary(sessionId);
        setSummaryData(data);
      } catch (err) {
        console.error('Failed to fetch summary:', err);
        setError(
          err.response?.data?.detail || 'Failed to generate summary. Please try again.'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchSummary();
  }, [sessionId]);

  const handleRestart = () => {
    resetSession();
    navigate('/');
  };

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.logoIcon}>◆</span>
          <span className={styles.logoText}>ScreenRAG</span>
        </div>
        <h2 className={styles.headerTitle}>Interview Summary</h2>
        <div className={styles.headerRight} />
      </header>

      {/* Content */}
      <main className={styles.main}>
        <div className={styles.container}>
          {isLoading && (
            <div className={styles.loadingState}>
              <div className="spinner" />
              <h3>Generating your interview summary...</h3>
              <p>Our AI is analyzing your responses</p>
            </div>
          )}

          {error && (
            <div className={styles.errorState}>
              <div className={styles.errorIcon}>⚠️</div>
              <h3>Something went wrong</h3>
              <p>{error}</p>
              <button className="btn btn-primary" onClick={() => window.location.reload()}>
                Try Again
              </button>
            </div>
          )}

          {summaryData && (
            <div className="animate-fade-in-up">
              <SessionSummary data={summaryData} onRestart={handleRestart} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
