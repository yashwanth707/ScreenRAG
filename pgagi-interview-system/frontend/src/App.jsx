/**
 * Root component with React Router routes.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSession, STEPS } from './context/SessionContext';
import LandingPage from './pages/LandingPage';
import InterviewPage from './pages/InterviewPage';
import SummaryPage from './pages/SummaryPage';

function App() {
  const { currentStep, sessionId } = useSession();

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/interview"
        element={
          sessionId ? <InterviewPage /> : <Navigate to="/" replace />
        }
      />
      <Route
        path="/summary"
        element={
          sessionId ? <SummaryPage /> : <Navigate to="/" replace />
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
