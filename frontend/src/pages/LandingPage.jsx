/**
 * Step 1: Resume Upload + Role Selection
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { uploadResume } from '../api/client';
import ResumeUpload from '../components/ResumeUpload/ResumeUpload';
import RoleSelector from '../components/RoleSelector/RoleSelector';
import styles from './LandingPage.module.css';

export default function LandingPage() {
  const navigate = useNavigate();
  const { setSession } = useSession();

  const [file, setFile] = useState(null);
  const [role, setRole] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const canSubmit = file && role && !isLoading;

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('role', role);

      const data = await uploadResume(formData);


      setSession({
        sessionId: data.session_id,
        role: data.role,
        candidateName: data.candidate_name,
        skills: data.skills,
        experienceLevel: data.experience_level,
      });


      navigate('/interview');
    } catch (err) {
      console.error('Upload failed:', err);
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to upload resume. Please try again.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.page}>

      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>◆</span>
          <span className={styles.logoText}>ScreenRAG</span>
        </div>
      </header>


      <div className={styles.hero}>
        <h1 className={styles.title}>
          Your Personal <span className="text-gradient">Technical Interview</span>
        </h1>
        <p className={styles.subtitle}>
          Let's get started. Share your resume and pick a role to experience a dynamic, friendly interview tailored just for you.
        </p>
      </div>


      <div className={styles.formContainer}>
        <div className={`glass-card ${styles.formCard} animate-fade-in-up`}>

          <div className={styles.step}>
            <div className={styles.stepBadge}>
              <span className={styles.stepNumber}>1</span>
              Resume
            </div>
            <ResumeUpload file={file} onFileSelect={setFile} />
          </div>


          <div className={`${styles.step} ${!file ? styles.stepDisabled : ''}`}>
            <div className={styles.stepBadge}>
              <span className={styles.stepNumber}>2</span>
              Role
            </div>
            <RoleSelector
              selectedRole={role}
              onRoleSelect={setRole}
            />
          </div>


          {error && (
            <div className={styles.error}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
            </div>
          )}


          <button
            className={`btn btn-primary ${styles.submitBtn}`}
            onClick={handleSubmit}
            disabled={!canSubmit}
            id="start-interview-btn"
          >
            {isLoading ? (
              <>
                <span className="spinner spinner-sm" />
                Preparing your interview...
              </>
            ) : (
              <>
                Let's Begin
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>


      <footer className={styles.footer}>
        <p>Powered by Ollama + ChromaDB + Sentence Transformers</p>
      </footer>
    </div>
  );
}
