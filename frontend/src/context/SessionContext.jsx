/**
 * Global state management using React Context.
 */

import React, { createContext, useContext, useReducer, useEffect } from 'react';


export const STEPS = {
  UPLOAD: 'UPLOAD',
  INTERVIEW: 'INTERVIEW',
  SUMMARY: 'SUMMARY',
};


const initialState = {
  sessionId: null,
  role: null,
  candidateName: null,
  skills: [],
  experienceLevel: null,
  currentStep: STEPS.UPLOAD,
};


const ACTIONS = {
  SET_SESSION: 'SET_SESSION',
  SET_STEP: 'SET_STEP',
  RESET: 'RESET',
  RESTORE: 'RESTORE',
};


function sessionReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSION:
      return {
        ...state,
        sessionId: action.payload.sessionId,
        role: action.payload.role,
        candidateName: action.payload.candidateName,
        skills: action.payload.skills || [],
        experienceLevel: action.payload.experienceLevel,
        currentStep: STEPS.INTERVIEW,
      };

    case ACTIONS.SET_STEP:
      return {
        ...state,
        currentStep: action.payload,
      };

    case ACTIONS.RESET:
      return { ...initialState };

    case ACTIONS.RESTORE:
      return { ...action.payload };

    default:
      return state;
  }
}


const SessionContext = createContext(null);


const STORAGE_KEY = 'screenrag_session';

/**
 * Session Provider Component
 */
export function SessionProvider({ children }) {
  const [state, dispatch] = useReducer(sessionReducer, initialState);


  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.sessionId) {
          dispatch({ type: ACTIONS.RESTORE, payload: parsed });
        }
      }
    } catch {
      // Ignore parse errors
    }
  }, []);


  useEffect(() => {
    if (state.sessionId) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  }, [state]);


  const setSession = (data) => {
    dispatch({
      type: ACTIONS.SET_SESSION,
      payload: data,
    });
  };

  const setStep = (step) => {
    dispatch({ type: ACTIONS.SET_STEP, payload: step });
  };

  const resetSession = () => {
    localStorage.removeItem(STORAGE_KEY);
    dispatch({ type: ACTIONS.RESET });
  };

  const value = {
    ...state,
    setSession,
    setStep,
    resetSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

/**
 * Hook to access session state and actions.
 */
export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}
