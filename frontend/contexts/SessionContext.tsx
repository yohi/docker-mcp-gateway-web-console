'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Session, SessionContextType, LoginCredentials } from '../lib/types/auth';
import { loginAPI, logoutAPI, checkSessionAPI } from '../lib/api/auth';

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await checkSessionAPI();
      if (result.valid && result.session) {
        setSession(result.session);
      } else {
        setSession(null);
      }
      setError(null);
    } catch (err) {
      setSession(null);
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
      setSession(newSession);
    } catch (err) {
      setSession(null);
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
