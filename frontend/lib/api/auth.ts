// API client for authentication

import { LoginCredentials, Session } from '../types/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

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

  const response = await fetch(`${API_URL}/api/auth/login`, {
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
  const response = await fetch(`${API_URL}/api/auth/logout`, {
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

  const response = await fetch(`${API_URL}/api/auth/session`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${sessionId}`,
    },
  });

  if (!response.ok) {
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
    // Log parse error for debugging
    console.error('Failed to parse session response as JSON:', error);
    return { valid: false };
  }
}
