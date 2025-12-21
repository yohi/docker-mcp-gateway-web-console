// API client for authentication

import { LoginCredentials, Session } from '../types/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

function getUrl(path: string): URL {
  if (API_BASE_URL) {
    return new URL(path, API_BASE_URL);
  }
  if (typeof window !== 'undefined') {
    return new URL(path, window.location.origin);
  }
  return new URL(path, 'http://127.0.0.1:3000');
}

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('session_id') || '';
}

export class AuthAPIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public errorCode?: string
  ) {
    super(message);
    this.name = 'AuthAPIError';
  }
}

export async function loginAPI(credentials: LoginCredentials): Promise<Session> {
  // Convert camelCase to snake_case for backend
  const payload = {
    method: credentials.method,
    email: credentials.email,
    client_id: credentials.clientId,
    client_secret: credentials.clientSecret,
    master_password: credentials.masterPassword,
    two_step_login_method: credentials.twoStepLoginMethod,
    two_step_login_code: credentials.twoStepLoginCode,
  };

  const url = getUrl('/api/auth/login');
  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Login failed' }));
    throw new AuthAPIError(
      error.message || 'Login failed',
      response.status,
      error.error_code
    );
  }

  return response.json();
}

export async function logoutAPI(): Promise<void> {
  const sessionId = getSessionId();
  const url = getUrl('/api/auth/logout');
  const response = await fetch(url.toString(), {
    method: 'POST',
    credentials: 'include',
    headers: sessionId
      ? {
        Authorization: `Bearer ${sessionId}`,
      }
      : {},
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Logout failed' }));
    throw new AuthAPIError(
      error.message || 'Logout failed',
      response.status,
      error.error_code
    );
  }
}

export async function checkSessionAPI(): Promise<{ valid: boolean; session?: Session }> {
  const sessionId = getSessionId();

  if (!sessionId) {
    return { valid: false };
  }

  const url = getUrl('/api/auth/session');
  console.log(`Checking session at ${url.toString()} with token: ${sessionId ? 'PRESENT' : 'NONE'}`);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout

  try {
    const response = await fetch(url.toString(), {
      method: 'GET',
      credentials: 'include',
      headers: {
        Authorization: `Bearer ${sessionId}`,
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      console.error(`Session check failed: ${response.status} ${response.statusText}`);
      return { valid: false };
    }

    try {
      const data = await response.json();
      if (data.valid && data.session_id) {
        return {
          valid: true,
          session: {
            session_id: data.session_id,
            user_email: data.user_email ?? '',
            expires_at: data.expires_at,
            created_at: data.created_at ?? new Date().toISOString(),
          },
        };
      }
      return { valid: false };
    } catch (error) {
      console.error('Failed to parse session response as JSON:', error);
      return { valid: false };
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      console.error('Session check timed out');
    } else {
      console.error('Session check network error:', error);
    }
    return { valid: false };
  }
}


