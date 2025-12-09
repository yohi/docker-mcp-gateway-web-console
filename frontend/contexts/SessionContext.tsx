'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Session, SessionContextType, LoginCredentials } from '../lib/types/auth';
import { loginAPI, logoutAPI, checkSessionAPI } from '../lib/api/auth';

const SessionContext = createContext<SessionContextType | undefined>(undefined);
const SESSION_STORAGE_KEY = 'session';
const SESSION_ID_STORAGE_KEY = 'session_id';

const readStoredSession = (): Session | null => {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
};

const persistSession = (value: Session | null) => {
  if (typeof window === 'undefined') return;
  if (value) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(value));
    window.localStorage.setItem(SESSION_ID_STORAGE_KEY, value.session_id);
  } else {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    window.localStorage.removeItem(SESSION_ID_STORAGE_KEY);
  }
};

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(readStoredSession());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const stored = readStoredSession();
      const result = await checkSessionAPI();

      if (result.valid && (result.session || stored)) {
        const nextSession = result.session ?? stored;
        if (nextSession) {
          setSession(nextSession);
          persistSession(nextSession);
          setError(null);
          return;
        }
      }

      setSession(null);
      persistSession(null);
      setError(null);
    } catch (err) {
      setSession(null);
      persistSession(null);
      setError(err instanceof Error ? err.message : 'Failed to check session');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    try {
      setIsLoading(true);
      setError(null);
      const newSession = await loginAPI(credentials);
      const normalizedSession: Session = {
        ...newSession,
        user_email: credentials.email,
        created_at: newSession.created_at ?? new Date().toISOString(),
      };
      setSession(normalizedSession);
      persistSession(normalizedSession);
    } catch (err) {
      setSession(null);
      persistSession(null);
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      await logoutAPI();
      setSession(null);
      persistSession(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Logout failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Check session on mount
  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const value: SessionContextType = {
    session,
    isLoading,
    error,
    login,
    logout,
    checkSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}
