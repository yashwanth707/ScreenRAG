/**
 * Question card.
 */

import React from 'react';
import styles from './QuestionCard.module.css';

const DIFFICULTY_COLORS = {
  basic: 'emerald',
  intermediate: 'amber',
  advanced: 'rose',
};

export default function QuestionCard({ questionText, questionNumber, topic, difficulty }) {
  const diffColor = DIFFICULTY_COLORS[difficulty] || 'violet';

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.label}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          Question {questionNumber}
        </span>
        <div className={styles.tags}>
          {topic && (
            <span className={`badge badge-cyan`}>
              {topic.replace(/_/g, ' ')}
            </span>
          )}
          {difficulty && (
            <span className={`badge badge-${diffColor}`}>
              {difficulty}
            </span>
          )}
        </div>
      </div>
      <p className={styles.questionText}>{questionText}</p>
    </div>
  );
}
