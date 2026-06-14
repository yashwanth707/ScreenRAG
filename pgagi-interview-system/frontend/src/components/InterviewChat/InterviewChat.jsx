/**
 * InterviewChat Component — Voice-First Interview Interface
 *
 * Chat-style interface with voice recording as the primary input:
 * - Questions appear as AI bubbles on the left
 * - Auto-starts microphone recording when a question appears
 * - Shows real-time waveform visualization while recording
 * - "Stop & Submit" to send audio, "Type instead" to fall back to text
 * - "I don't know, Next Question" skip button
 * - Displays transcript + voice metric badges on answer bubbles
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import QuestionCard from '../QuestionCard/QuestionCard';
import styles from './InterviewChat.module.css';

// Recording states
const VOICE_STATE = {
  IDLE: 'idle',
  REQUESTING: 'requesting',   // Requesting mic permission
  RECORDING: 'recording',
  PROCESSING: 'processing',   // Sent to backend, waiting for response
  TEXT_MODE: 'text_mode',      // User chose to type instead
};

export default function InterviewChat({
  messages,
  currentQuestion,
  isLoading,
  onSubmitAnswer,
  onSubmitVoiceAnswer,
  onSkipQuestion,
  questionNumber,
  totalQuestions,
}) {
  const [answer, setAnswer] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [voiceState, setVoiceState] = useState(VOICE_STATE.IDLE);
  const [recordingTime, setRecordingTime] = useState(0);
  const [voiceError, setVoiceError] = useState(null);
  const [lastVoiceResult, setLastVoiceResult] = useState(null);

  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const analyserRef = useRef(null);
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);
  const streamRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const silenceStartRef = useRef(null);
  const readingTimerRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentQuestion, isLoading, voiceState]);

  // Auto-resize textarea (text mode)
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [answer]);

  // Auto-start recording when a new question appears
  useEffect(() => {
    if (currentQuestion && !isLoading) {
      // Reset states for new question
      setVoiceState(VOICE_STATE.IDLE);
      setRecordingTime(0);
      setVoiceError(null);
      setLastVoiceResult(null);
      setAnswer('');

      // Calculate reading delay: ~3 words per second, min 2 seconds
      const wordCount = currentQuestion.question_text.split(/\s+/).length;
      const readingDelayMs = Math.max(2000, Math.floor((wordCount / 3) * 1000));

      readingTimerRef.current = setTimeout(() => {
        startRecording();
      }, readingDelayMs);

      return () => clearTimeout(readingTimerRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentQuestion?.question_id]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecordingCleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Recording Logic ───────────────────────────────────────
  const startRecording = useCallback(async () => {
    setVoiceError(null);
    setVoiceState(VOICE_STATE.REQUESTING);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;

      // Set up audio analyser for waveform + silence detection
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Start MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(250); // Collect chunks every 250ms
      setVoiceState(VOICE_STATE.RECORDING);
      setRecordingTime(0);

      // Start recording timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      // Start waveform visualization
      drawWaveform();

      // Start silence detection
      startSilenceDetection(analyser);

    } catch (err) {
      console.error('Microphone access failed:', err);
      setVoiceError(
        err.name === 'NotAllowedError'
          ? 'Microphone access denied. Please allow microphone access or type your answer.'
          : 'Could not access microphone. Please check your device settings.'
      );
      setVoiceState(VOICE_STATE.TEXT_MODE);
    }
  }, []);

  const stopRecordingCleanup = useCallback(() => {
    // Stop timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    // Stop animation
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    // Stop silence detection
    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const stopAndSubmitRecording = useCallback(async () => {
    if (!mediaRecorderRef.current || voiceState !== VOICE_STATE.RECORDING) return;

    setVoiceState(VOICE_STATE.PROCESSING);
    stopRecordingCleanup();

    // Stop the recorder and wait for final data
    const recorder = mediaRecorderRef.current;

    return new Promise((resolve) => {
      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });

        if (audioBlob.size < 1000) {
          setVoiceError('Recording too short. Please try again or type your answer.');
          setVoiceState(VOICE_STATE.TEXT_MODE);
          resolve();
          return;
        }

        try {
          setIsSubmitting(true);
          const result = await onSubmitVoiceAnswer(audioBlob);
          setLastVoiceResult(result);
        } catch (err) {
          console.error('Voice submission failed:', err);
          setVoiceError(
            err.response?.data?.detail || 'Failed to process audio. Please type your answer instead.'
          );
          setVoiceState(VOICE_STATE.TEXT_MODE);
        } finally {
          setIsSubmitting(false);
          resolve();
        }
      };

      recorder.stop();
    });
  }, [voiceState, onSubmitVoiceAnswer, stopRecordingCleanup]);

  // ─── Silence Detection ─────────────────────────────────────
  const startSilenceDetection = useCallback((analyser) => {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    silenceStartRef.current = null;

    silenceTimerRef.current = setInterval(() => {
      analyser.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((sum, v) => sum + v, 0) / bufferLength;

      if (avg < 8) {
        // Silence detected
        if (!silenceStartRef.current) {
          silenceStartRef.current = Date.now();
        } else if (Date.now() - silenceStartRef.current > 5000) {
          // 5 seconds of silence — auto-stop
          stopAndSubmitRecording();
        }
      } else {
        silenceStartRef.current = null;
      }
    }, 200);
  }, [stopAndSubmitRecording]);

  // ─── Waveform Visualization ────────────────────────────────
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const barCount = 48;
      const barWidth = width / barCount - 2;
      const step = Math.floor(bufferLength / barCount);

      for (let i = 0; i < barCount; i++) {
        const value = dataArray[i * step] / 255;
        const barHeight = Math.max(3, value * height * 0.85);

        // Gradient from violet to cyan based on position
        const t = i / barCount;
        const r = Math.round(139 * (1 - t) + 6 * t);
        const g = Math.round(92 * (1 - t) + 182 * t);
        const b = Math.round(246 * (1 - t) + 212 * t);

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.5 + value * 0.5})`;
        ctx.beginPath();
        ctx.roundRect(
          i * (barWidth + 2),
          (height - barHeight) / 2,
          barWidth,
          barHeight,
          2
        );
        ctx.fill();
      }
    };

    draw();
  }, []);

  // ─── Text Mode Handlers ────────────────────────────────────
  const switchToTextMode = useCallback(() => {
    stopRecordingCleanup();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setVoiceState(VOICE_STATE.TEXT_MODE);
  }, [stopRecordingCleanup]);

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    if (!answer.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onSubmitAnswer(answer.trim());
      setAnswer('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTextSubmit(e);
    }
  };

  const handleSkip = async () => {
    if (isSubmitting) return;

    // Stop recording if active
    stopRecordingCleanup();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    setIsSubmitting(true);
    try {
      await onSkipQuestion();
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Format recording time ─────────────────────────────────
  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // ─── Render Helper: Voice Metric Badges ────────────────────
  const renderVoiceMetrics = (metrics) => {
    if (!metrics) return null;

    const getScoreColor = (score) => {
      if (score >= 7) return 'emerald';
      if (score >= 5) return 'amber';
      return 'rose';
    };

    return (
      <div className={styles.voiceMetrics}>
        <span className={`badge badge-${getScoreColor(metrics.naturalness_score)}`}>
          Natural: {metrics.naturalness_score}/10
        </span>
        <span className={`badge badge-${getScoreColor(metrics.confidence_score)}`}>
          Confidence: {metrics.confidence_score}/10
        </span>
        <span className="badge badge-cyan">
          {metrics.wpm} WPM
        </span>
        {metrics.filler_count > 0 && (
          <span className="badge badge-amber">
            {metrics.filler_count} fillers
          </span>
        )}
        {metrics.response_latency > 0 && (
          <span className="badge badge-violet">
            {metrics.response_latency}s latency
          </span>
        )}
      </div>
    );
  };

  return (
    <div className={styles.chatContainer}>
      {/* Messages area */}
      <div className={styles.messagesArea}>
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`${styles.message} ${
              msg.type === 'question' ? styles.aiMessage : styles.userMessage
            }`}
          >
            {msg.type === 'question' ? (
              <QuestionCard
                questionText={msg.text}
                questionNumber={msg.number}
                topic={msg.topic}
                difficulty={msg.difficulty}
              />
            ) : (
              <div className={styles.answerBubble}>
                <div className={styles.answerHeader}>
                  <div className={styles.answerLabel}>Your Answer</div>
                  {msg.answerMode === 'voice' && (
                    <span className={`badge badge-violet ${styles.modeBadge}`}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                      </svg>
                      Voice
                    </span>
                  )}
                </div>
                <p className={styles.answerText}>{msg.text}</p>
                {msg.voiceMetrics && renderVoiceMetrics(msg.voiceMetrics)}
              </div>
            )}
          </div>
        ))}

        {/* Current unanswered question */}
        {currentQuestion && !isLoading && (
          <div className={`${styles.message} ${styles.aiMessage} animate-slide-left`}>
            <QuestionCard
              questionText={currentQuestion.question_text}
              questionNumber={currentQuestion.question_number}
              topic={currentQuestion.topic}
              difficulty={currentQuestion.difficulty}
            />
          </div>
        )}

        {/* Typing indicator */}
        {isLoading && (
          <div className={`${styles.message} ${styles.aiMessage}`}>
            <div className={styles.typingBubble}>
              <div className="typing-indicator">
                <span className="dot"></span>
                <span className="dot"></span>
                <span className="dot"></span>
              </div>
              <span className={styles.typingText}>Generating question...</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input area — Voice or Text mode */}
      {currentQuestion && !isLoading && (
        <div className={styles.inputArea}>
          {/* Voice Error */}
          {voiceError && (
            <div className={styles.voiceError}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {voiceError}
            </div>
          )}

          {/* Recording Mode */}
          {(voiceState === VOICE_STATE.RECORDING || voiceState === VOICE_STATE.REQUESTING) && (
            <div className={styles.recordingPanel}>
              <div className={styles.recordingHeader}>
                <div className={styles.recordingIndicator}>
                  <span className={styles.recordingDot} />
                  <span className={styles.recordingLabel}>
                    {voiceState === VOICE_STATE.REQUESTING ? 'Requesting mic...' : 'Recording'}
                  </span>
                </div>
                <span className={styles.recordingTimer}>{formatTime(recordingTime)}</span>
              </div>

              {/* Waveform */}
              <canvas
                ref={canvasRef}
                width={600}
                height={64}
                className={styles.waveformCanvas}
              />

              <div className={styles.recordingControls}>
                <button
                  className={`btn btn-primary ${styles.stopBtn}`}
                  onClick={stopAndSubmitRecording}
                  disabled={voiceState === VOICE_STATE.REQUESTING}
                  id="stop-submit-btn"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                  Stop & Submit
                </button>
                <button
                  className={`btn btn-ghost ${styles.textFallbackBtn}`}
                  onClick={switchToTextMode}
                  id="type-instead-btn"
                >
                  ⌨ Type instead
                </button>
                <button
                  className={`btn btn-ghost ${styles.skipBtn}`}
                  onClick={handleSkip}
                  id="skip-question-btn"
                >
                  I don't know →
                </button>
              </div>
            </div>
          )}

          {/* Processing Mode */}
          {voiceState === VOICE_STATE.PROCESSING && (
            <div className={styles.processingPanel}>
              <div className="spinner spinner-sm" />
              <span className={styles.processingText}>
                Transcribing & analyzing your answer...
              </span>
            </div>
          )}

          {/* Text Input Mode */}
          {voiceState === VOICE_STATE.TEXT_MODE && (
            <form onSubmit={handleTextSubmit}>
              <div className={styles.inputWrapper}>
                <textarea
                  ref={textareaRef}
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your answer here... (Enter to submit, Shift+Enter for new line)"
                  className={styles.textarea}
                  rows={3}
                  disabled={isSubmitting}
                  id="answer-textarea"
                />
                <div className={styles.textControls}>
                  <button
                    type="submit"
                    className={`btn btn-primary ${styles.submitBtn}`}
                    disabled={!answer.trim() || isSubmitting}
                    id="submit-answer-btn"
                  >
                    {isSubmitting ? (
                      <span className="spinner spinner-sm" />
                    ) : (
                      <>
                        Submit
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="22" y1="2" x2="11" y2="13" />
                          <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    className={`btn btn-ghost ${styles.skipBtn}`}
                    onClick={handleSkip}
                    disabled={isSubmitting}
                  >
                    Skip →
                  </button>
                </div>
              </div>
              <div className={styles.inputHint}>
                <button
                  type="button"
                  className={styles.switchToVoiceLink}
                  onClick={startRecording}
                >
                  🎙 Switch to voice
                </button>
                <span>Question {questionNumber} of {totalQuestions}</span>
              </div>
            </form>
          )}

          {/* Idle state (Reading time before auto-start) */}
          {voiceState === VOICE_STATE.IDLE && (
            <div className={styles.idlePanel}>
              <div className={styles.idlePulse}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M2 12h4l3-9 5 18 3-9h5" />
                </svg>
              </div>
              <span className={styles.idleText}>Reading time... (Mic will auto-start)</span>
              <button 
                className={`btn btn-primary ${styles.startNowBtn}`}
                onClick={() => {
                  if (readingTimerRef.current) clearTimeout(readingTimerRef.current);
                  startRecording();
                }}
                style={{ marginTop: '16px' }}
              >
                🎙 Start Answering Now
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
