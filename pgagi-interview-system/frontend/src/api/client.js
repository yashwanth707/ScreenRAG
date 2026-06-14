/**
 * ScreenRAG — API Client
 *
 * Single Axios instance with all API calls.
 * Base URL configured via VITE_API_URL env var.
 */

import axios from 'axios';

// Create axios instance with base URL
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 120000, // 2 minutes — LLM calls can be slow
  headers: {
    'Accept': 'application/json',
  },
});

/**
 * Upload a resume PDF and create an interview session.
 *
 * @param {FormData} formData - Must contain 'file' (PDF) and 'role' (string)
 * @returns {Promise<{session_id, candidate_name, skills, experience_level, role}>}
 */
export async function uploadResume(formData) {
  const response = await api.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000, // 3 minutes for resume parsing
  });
  return response.data;
}

/**
 * Get the next interview question for a session.
 *
 * @param {string} sessionId - Session UUID
 * @returns {Promise<{question_id, question_text, question_number, total_questions, done}>}
 */
export async function getNextQuestion(sessionId) {
  const response = await api.post('/interview/next-question', {
    session_id: sessionId,
  });
  return response.data;
}

/**
 * Submit an answer to an interview question.
 *
 * @param {string} sessionId - Session UUID
 * @param {string} questionId - Question UUID
 * @param {string} answerText - The candidate's answer
 * @returns {Promise<{saved, question_number}>}
 */
export async function submitAnswer(sessionId, questionId, answerText) {
  const response = await api.post('/interview/answer', {
    session_id: sessionId,
    question_id: questionId,
    answer_text: answerText,
  });
  return response.data;
}

/**
 * Submit a voice answer (audio recording) to an interview question.
 *
 * @param {string} sessionId - Session UUID
 * @param {string} questionId - Question UUID
 * @param {Blob} audioBlob - Recorded audio blob (webm format)
 * @param {string} questionAskedAt - ISO timestamp of when the question was shown
 * @returns {Promise<{saved, question_number, transcript, voice_metrics}>}
 */
export async function submitVoiceAnswer(sessionId, questionId, audioBlob, questionAskedAt) {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('question_id', questionId);
  formData.append('audio', audioBlob, 'answer.webm');
  formData.append('question_asked_at', questionAskedAt || '');

  const response = await api.post('/interview/answer-voice', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // Whisper transcription can take a moment
  });
  return response.data;
}

/**
 * Submit a "skip" answer (I don't know / next question).
 *
 * @param {string} sessionId - Session UUID
 * @param {string} questionId - Question UUID
 * @returns {Promise<{saved, question_number}>}
 */
export async function submitSkipAnswer(sessionId, questionId) {
  return submitAnswer(sessionId, questionId, "(Skipped — I don't know)");
}

/**
 * Get the interview summary for a completed session.
 *
 * @param {string} sessionId - Session UUID
 * @returns {Promise<{session_id, candidate_name, role, questions_asked, answers_given, qa_pairs, analysis}>}
 */
export async function getSummary(sessionId) {
  const response = await api.get(`/summary/${sessionId}`);
  return response.data;
}

/**
 * Check backend health status.
 *
 * @returns {Promise<{status, ollama, chroma, db}>}
 */
export async function checkHealth() {
  const response = await api.get('/health');
  return response.data;
}

export default api;
