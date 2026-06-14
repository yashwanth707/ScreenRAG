/**
 * Step 2: Live Interview
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession, STEPS } from '../context/SessionContext';
import { getNextQuestion, submitAnswer, submitVoiceAnswer, submitSkipAnswer } from '../api/client';
import InterviewChat from '../components/InterviewChat/InterviewChat';
import styles from './InterviewPage.module.css';

const ROLE_DISPLAY = {
  ai_ml: 'AI/ML Engineer',
  backend: 'Backend Engineer',
  data_science: 'Data Scientist',
};

export default function InterviewPage() {
  const navigate = useNavigate();
  const { sessionId, role, candidateName, setStep } = useSession();

  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [questionNumber, setQuestionNumber] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(7);
  const [error, setError] = useState(null);


  const questionAskedAtRef = useRef(null);
  const isFetchingRef = useRef(false);


  const fetchNextQuestion = useCallback(async () => {
    if (!sessionId || isFetchingRef.current) return;

    isFetchingRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const data = await getNextQuestion(sessionId);

      if (data.done) {

        setStep(STEPS.SUMMARY);
        navigate('/summary');
        return;
      }

      setCurrentQuestion(data);
      setQuestionNumber(data.question_number);
      setTotalQuestions(data.total_questions);


      questionAskedAtRef.current = new Date().toISOString();

    } catch (err) {
      console.error('Failed to fetch question:', err);
      setError(
        err.response?.data?.detail || 'Failed to generate question. Please try again.'
      );
    } finally {
      setIsLoading(false);
      isFetchingRef.current = false;
    }
  }, [sessionId, navigate, setStep]);


  useEffect(() => {
    fetchNextQuestion();
  }, [fetchNextQuestion]);


  const handleSubmitAnswer = async (answerText) => {
    if (!currentQuestion || !sessionId) return;

    try {
      await submitAnswer(sessionId, currentQuestion.question_id, answerText);


      setMessages((prev) => [
        ...prev,
        {
          type: 'question',
          text: currentQuestion.question_text,
          number: currentQuestion.question_number,
          topic: currentQuestion.topic,
          difficulty: currentQuestion.difficulty,
        },
        {
          type: 'answer',
          text: answerText,
          answerMode: 'text',
        },
      ]);

      setCurrentQuestion(null);
      await fetchNextQuestion();
    } catch (err) {
      console.error('Failed to submit answer:', err);
      setError(
        err.response?.data?.detail || 'Failed to save answer. Please try again.'
      );
    }
  };


  const handleSubmitVoiceAnswer = async (audioBlob) => {
    if (!currentQuestion || !sessionId) return;

    const result = await submitVoiceAnswer(
      sessionId,
      currentQuestion.question_id,
      audioBlob,
      questionAskedAtRef.current || '',
    );


    setMessages((prev) => [
      ...prev,
      {
        type: 'question',
        text: currentQuestion.question_text,
        number: currentQuestion.question_number,
        topic: currentQuestion.topic,
        difficulty: currentQuestion.difficulty,
      },
      {
        type: 'answer',
        text: result.transcript || '(No speech detected)',
        answerMode: 'voice',
        voiceMetrics: result.voice_metrics || null,
      },
    ]);

    setCurrentQuestion(null);
    await fetchNextQuestion();

    return result;
  };


  const handleSkipQuestion = async () => {
    if (!currentQuestion || !sessionId) return;

    try {
      await submitSkipAnswer(sessionId, currentQuestion.question_id);

      setMessages((prev) => [
        ...prev,
        {
          type: 'question',
          text: currentQuestion.question_text,
          number: currentQuestion.question_number,
          topic: currentQuestion.topic,
          difficulty: currentQuestion.difficulty,
        },
        {
          type: 'answer',
          text: "(Skipped — I don't know)",
          answerMode: 'text',
        },
      ]);

      setCurrentQuestion(null);
      await fetchNextQuestion();
    } catch (err) {
      console.error('Failed to skip question:', err);
      setError(
        err.response?.data?.detail || 'Failed to skip question. Please try again.'
      );
    }
  };

  const progress = totalQuestions > 0 ? (questionNumber / totalQuestions) * 100 : 0;

  return (
    <div className={styles.page}>

      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.logoIcon}>◆</span>
          <div className={styles.headerInfo}>
            <span className={styles.candidateName}>{candidateName}</span>
            <span className={styles.roleBadge}>
              {ROLE_DISPLAY[role] || role}
            </span>
          </div>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.progressLabel}>
            Question {questionNumber} of {totalQuestions}
          </span>
        </div>
      </header>


      <div className={styles.progressBar}>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>


      <main className={styles.main}>
        <div className={styles.container}>
          {error && (
            <div className={styles.error}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
              <button className="btn btn-ghost" onClick={fetchNextQuestion}>
                Retry
              </button>
            </div>
          )}

          <InterviewChat
            messages={messages}
            currentQuestion={currentQuestion}
            isLoading={isLoading}
            onSubmitAnswer={handleSubmitAnswer}
            onSubmitVoiceAnswer={handleSubmitVoiceAnswer}
            onSkipQuestion={handleSkipQuestion}
            questionNumber={questionNumber}
            totalQuestions={totalQuestions}
          />
        </div>
      </main>
    </div>
  );
}
