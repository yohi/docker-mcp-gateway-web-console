import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import LoginForm from '../../../components/auth/LoginForm';
import { SessionProvider } from '../../../contexts/SessionContext';
import * as authAPI from '../../../lib/api/auth';

// Mock the auth API
jest.mock('../../../lib/api/auth');

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

const mockLoginAPI = authAPI.loginAPI as jest.MockedFunction<typeof authAPI.loginAPI>;
const mockCheckSessionAPI = authAPI.checkSessionAPI as jest.MockedFunction<typeof authAPI.checkSessionAPI>;

describe('LoginForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCheckSessionAPI.mockResolvedValue({ valid: false });
  });

  it('renders login form with all fields', async () => {
    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByText('Bitwardenでログイン')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Bitwarden APIキー')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
    });
  });

  it('switches between API key and master password methods', async () => {
    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Bitwarden APIキー')).toBeInTheDocument();
    });

    // Initially shows API key field
    expect(screen.getByPlaceholderText('Bitwarden APIキー')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('マスターパスワード')).not.toBeInTheDocument();

    // Switch to master password
    const masterPasswordRadio = screen.getByRole('radio', { name: 'マスターパスワード' });
    fireEvent.click(masterPasswordRadio);

    // Now shows master password field
    expect(screen.queryByPlaceholderText('Bitwarden APIキー')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('マスターパスワード')).toBeInTheDocument();
  });

  it('validates required fields before submission', async () => {
    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    const form = screen.getByRole('form', { name: /.*/i }); // Try with regex for name
    await act(async () => {
      fireEvent.submit(form);
    });

    await waitFor(() => {
      expect(screen.getByText('メールアドレスを入力してください')).toBeInTheDocument();
    });

    expect(mockLoginAPI).not.toHaveBeenCalled();
  });

  it('submits login with API key credentials', async () => {
    mockLoginAPI.mockResolvedValue({
      session_id: 'new-session',
      user_email: 'test@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
    });

    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByPlaceholderText('your@email.com'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Bitwarden APIキー'), {
      target: { value: 'test-api-key' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLoginAPI).toHaveBeenCalledWith({
        method: 'api_key',
        email: 'test@example.com',
        apiKey: 'test-api-key',
      });
    });
  });

  it('submits login with master password credentials', async () => {
    mockLoginAPI.mockResolvedValue({
      session_id: 'test-session-id',
      user_email: 'test@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
    });

    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    // Switch to master password
    const masterPasswordRadio = screen.getByRole('radio', { name: 'マスターパスワード' });
    fireEvent.click(masterPasswordRadio);

    // Fill in the form
    fireEvent.change(screen.getByPlaceholderText('your@email.com'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('マスターパスワード'), {
      target: { value: 'test-password' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' }); // Query the initial non-loading button
    await act(async () => {
      fireEvent.click(submitButton);
    });

    // Expect loading state after click
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン中...' })).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(mockLoginAPI).toHaveBeenCalledWith({
        method: 'master_password',
        email: 'test@example.com',
        masterPassword: 'test-password',
      });
      expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument(); // Assert button is back to 'ログイン'
    });
  });

  it('displays error message on login failure', async () => {
    const loginError = new Error('Invalid credentials');
    mockLoginAPI.mockRejectedValue(loginError);

    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    // Wait for initial session check
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByPlaceholderText('your@email.com'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Bitwarden APIキー'), {
      target: { value: 'wrong-key' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('disables form during submission', async () => {
    const mockSession = {
      session_id: 'test-session-id',
      user_email: 'test@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
    };
    mockLoginAPI.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve(mockSession), 100)));

    await act(async () => {
      render(
        <SessionProvider>
          <LoginForm />
        </SessionProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByPlaceholderText('your@email.com'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Bitwarden APIキー'), {
      target: { value: 'test-api-key' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    // Button should be disabled and show loading text
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン中...' })).toBeDisabled();
    });
  });
});
