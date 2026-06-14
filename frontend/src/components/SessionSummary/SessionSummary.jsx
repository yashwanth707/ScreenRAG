/**
 * Displays the complete interview summary.
 */

import React from 'react';
import styles from './SessionSummary.module.css';

const ROLE_DISPLAY = {
  ai_ml: 'AI/ML Engineer',
  backend: 'Backend Engineer',
  data_science: 'Data Scientist',
};

function ScoreRing({ score, label, size = 72 }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 10) * circumference;

  const getColor = (s) => {
    if (s >= 7) return 'var(--accent-emerald)';
    if (s >= 5) return 'var(--accent-amber)';
    return 'var(--accent-rose)';
  };

  return (
    <div className={styles.scoreRing}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(148, 163, 184, 0.1)"
          strokeWidth="4"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColor(score)}
          strokeWidth="4"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
        />
      </svg>
      <div className={styles.scoreRingInner}>
        <span className={styles.scoreRingValue} style={{ color: getColor(score) }}>
          {score}
        </span>
      </div>
      <span className={styles.scoreRingLabel}>{label}</span>
    </div>
  );
}

export default function SessionSummary({ data, onRestart }) {
  if (!data) return null;

  const { candidate_name, role, questions_asked, answers_given, qa_pairs, analysis } = data;
  const voiceAgg = analysis?.voice_aggregate;

  const handleDownload = () => {
    let content = `Interview Summary — ${ROLE_DISPLAY[role] || role}\n`;
    content += `Candidate: ${candidate_name}\n`;
    content += `Date: ${new Date().toLocaleDateString()}\n`;
    content += `Questions: ${questions_asked} | Answers: ${answers_given}\n`;
    content += `Confidence Score: ${analysis.confidence_score}/10\n`;

    if (voiceAgg) {
      content += `\nVoice Analytics:\n`;
      content += `  Avg Response Latency: ${voiceAgg.avg_response_latency}s\n`;
      content += `  Avg Naturalness: ${voiceAgg.avg_naturalness}/10\n`;
      content += `  Avg WPM: ${voiceAgg.avg_wpm}\n`;
      content += `  Total Fillers: ${voiceAgg.total_fillers}\n`;
      content += `  Avg Confidence: ${voiceAgg.avg_confidence}/10\n`;
      content += `  Voice Answers: ${voiceAgg.voice_answers_count}\n`;
    }

    content += `\n${'='.repeat(60)}\n\n`;


    qa_pairs.forEach((qa) => {
      const mode = qa.answer_mode === 'voice' ? ' [VOICE]' : '';
      content += `Q${qa.question_number} [${qa.topic || 'general'}] (${qa.difficulty || '-'})${mode}:\n`;
      content += `${qa.question_text}\n\n`;
      content += `Answer:\n${qa.answer_text || '(No answer)'}\n`;

      if (qa.voice_metrics) {
        const vm = qa.voice_metrics;
        content += `  Voice Metrics: WPM=${vm.wpm}, Naturalness=${vm.naturalness_score}/10, `;
        content += `Confidence=${vm.confidence_score}/10, Fillers=${vm.filler_count}, `;
        content += `Latency=${vm.response_latency}s\n`;
      }

      content += `\n${'-'.repeat(40)}\n\n`;
    });


    content += `\n${'='.repeat(60)}\n`;
    content += `ANALYSIS\n${'='.repeat(60)}\n\n`;
    content += `Topics Covered: ${analysis.topics_covered.join(', ')}\n\n`;
    content += `Strengths:\n${analysis.strengths.map((s) => `  • ${s}`).join('\n')}\n\n`;
    content += `Areas for Improvement:\n${analysis.areas_for_improvement.map((a) => `  • ${a}`).join('\n')}\n\n`;
    content += `Overall Assessment:\n${analysis.overall_assessment}\n`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `interview_summary_${candidate_name?.replace(/\s+/g, '_') || 'candidate'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getScoreBadgeClass = (score) => {
    if (score >= 7) return 'badge-emerald';
    if (score >= 5) return 'badge-amber';
    return 'badge-rose';
  };

  return (
    <div className={styles.summary}>

      <div className={`glass-card ${styles.infoCard}`}>
        <div className={styles.infoGrid}>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Candidate</span>
            <span className={styles.infoValue}>{candidate_name}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Role</span>
            <span className={styles.infoValue}>{ROLE_DISPLAY[role] || role}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Questions</span>
            <span className={styles.infoValue}>{questions_asked}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Confidence</span>
            <span className={`${styles.infoValue} ${styles.scoreValue}`}>
              {analysis.confidence_score}/10
            </span>
          </div>
        </div>
      </div>


      {voiceAgg && voiceAgg.voice_answers_count > 0 && (
        <div className={`glass-card ${styles.voicePanel}`}>
          <h3 className={styles.sectionTitle}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
            Voice Analytics
            <span className="badge badge-violet">{voiceAgg.voice_answers_count} voice answers</span>
          </h3>

          <div className={styles.voiceScoreGrid}>
            <ScoreRing score={voiceAgg.avg_naturalness} label="Naturalness" />
            <ScoreRing score={voiceAgg.avg_confidence} label="Confidence" />

            <div className={styles.voiceStat}>
              <span className={styles.voiceStatValue}>{voiceAgg.avg_response_latency}s</span>
              <span className={styles.voiceStatLabel}>Avg Latency</span>
            </div>
            <div className={styles.voiceStat}>
              <span className={styles.voiceStatValue}>{voiceAgg.avg_wpm}</span>
              <span className={styles.voiceStatLabel}>Avg WPM</span>
            </div>
            <div className={styles.voiceStat}>
              <span className={styles.voiceStatValue}>{voiceAgg.total_fillers}</span>
              <span className={styles.voiceStatLabel}>Total Fillers</span>
            </div>
          </div>
        </div>
      )}


      <div className={styles.analysisSection}>
        <h3 className={styles.sectionTitle}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
          Feedback & Insights
        </h3>


        <div className={styles.analysisBlock}>
          <h4 className={styles.blockTitle}>Topics Covered</h4>
          <div className={styles.topicTags}>
            {analysis.topics_covered.map((topic, i) => (
              <span key={i} className="badge badge-cyan">
                {topic.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>


        <div className={styles.analysisBlock}>
          <h4 className={`${styles.blockTitle} ${styles.strengthTitle}`}>
            ✦ What You Did Great
          </h4>
          <ul className={styles.list}>
            {analysis.strengths.map((s, i) => (
              <li key={i} className={styles.strengthItem}>{s}</li>
            ))}
          </ul>
        </div>


        <div className={styles.analysisBlock}>
          <h4 className={`${styles.blockTitle} ${styles.improvementTitle}`}>
            ▲ Opportunities to Grow
          </h4>
          <ul className={styles.list}>
            {analysis.areas_for_improvement.map((a, i) => (
              <li key={i} className={styles.improvementItem}>{a}</li>
            ))}
          </ul>
        </div>


        {analysis.overall_assessment && (
          <div className={`glass-card ${styles.assessmentCard}`}>
            <p className={styles.assessmentText}>
              &ldquo;{analysis.overall_assessment}&rdquo;
            </p>
          </div>
        )}
      </div>


      <div className={styles.transcriptSection}>
        <h3 className={styles.sectionTitle}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          Interview Transcript
        </h3>

        <div className={styles.qaList}>
          {qa_pairs.map((qa, i) => (
            <div key={i} className={`glass-card ${styles.qaCard}`}>
              <div className={styles.qaHeader}>
                <span className={styles.qaNumber}>Q{qa.question_number}</span>
                {qa.topic && <span className="badge badge-violet">{qa.topic.replace(/_/g, ' ')}</span>}
                {qa.difficulty && <span className={`badge badge-${qa.difficulty === 'advanced' ? 'rose' : qa.difficulty === 'basic' ? 'emerald' : 'amber'}`}>{qa.difficulty}</span>}
                {qa.answer_mode === 'voice' && (
                  <span className="badge badge-cyan">
                    🎙 Voice
                  </span>
                )}
              </div>
              <p className={styles.qaQuestion}>{qa.question_text}</p>
              <div className={styles.qaDivider} />
              <p className={styles.qaAnswer}>
                {qa.answer_text || <em className={styles.noAnswer}>No answer provided</em>}
              </p>

              {/* Per-question voice metrics */}
              {qa.voice_metrics && (
                <div className={styles.qaVoiceMetrics}>
                  <span className={`badge ${getScoreBadgeClass(qa.voice_metrics.naturalness_score)}`}>
                    Natural: {qa.voice_metrics.naturalness_score}/10
                  </span>
                  <span className={`badge ${getScoreBadgeClass(qa.voice_metrics.confidence_score)}`}>
                    Confidence: {qa.voice_metrics.confidence_score}/10
                  </span>
                  <span className="badge badge-cyan">
                    {qa.voice_metrics.wpm} WPM
                  </span>
                  {qa.voice_metrics.filler_count > 0 && (
                    <span className="badge badge-amber">
                      {qa.voice_metrics.filler_count} fillers
                    </span>
                  )}
                  <span className="badge badge-violet">
                    {qa.voice_metrics.response_latency}s latency
                  </span>
                  <span className={`badge badge-${qa.voice_metrics.fluency_label === 'Optimal' ? 'emerald' : 'amber'}`}>
                    {qa.voice_metrics.fluency_label}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>


      <div className={styles.actions}>
        <button className="btn btn-secondary" onClick={handleDownload} id="download-summary-btn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download Summary
        </button>
        <button className="btn btn-primary" onClick={onRestart} id="restart-btn">
          Start New Interview
        </button>
      </div>
    </div>
  );
}
