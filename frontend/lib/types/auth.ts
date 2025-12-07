// Authentication types

export interface LoginCredentials {
  method: 'api_key' | 'master_password';
  email: string;
  clientId?: string;
  clientSecret?: string;
  masterPassword?: string;
  twoStepLoginMethod?: number;
  twoStepLoginCode?: string;
}

export interface Session {
  session_id: string;
  user_email: string;
  expires_at: string;
  created_at: string;
}

export interface SessionContextType {
  session: Session | null;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
}
