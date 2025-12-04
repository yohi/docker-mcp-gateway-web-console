import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Bitwardenでログイン')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('メールアドレス')).toBeInTheDocument();
    expect(screen.getByLabelText('APIキー')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
  });

  it('switches between API key and master password methods', async () => {
    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('APIキー')).toBeInTheDocument();
    });

    // Initially shows API key field
    expect(screen.getByLabelText('APIキー')).toBeInTheDocument();
    expect(screen.queryByLabelText('マスターパスワード')).not.toBeInTheDocument();

    // Switch to master password
    const masterPasswordRadio = screen.getByLabelText('マスターパスワード');
    fireEvent.click(masterPasswordRadio);

    // Now shows master password field
    expect(screen.queryByLabelText('APIキー')).not.toBeInTheDocument();
    expect(screen.getByLabelText('マスターパスワード')).toBeInTheDocument();
  });

  it('validates required fields before submission', async () => {
    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
    });

    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('メールアドレスを入力してください')).toBeInTheDocument();
    });

    expect(mockLoginAPI).not.toHaveBeenCalled();
  });

  it('submits login with API key credentials', async () => {
    mockLoginAPI.mockResolvedValue({
      session_id: 'test-session-id',
      user_email: 'test@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
    });

    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('メールアドレス')).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByLabelText('メールアドレス'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText('APIキー'), {
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

    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('マスターパスワード')).toBeInTheDocument();
    });

    // Switch to master password
    const masterPasswordRadio = screen.getByLabelText('マスターパスワード');
    fireEvent.click(masterPasswordRadio);

    // Fill in the form
    fireEvent.change(screen.getByLabelText('メールアドレス'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText('マスターパスワード'), {
      target: { value: 'test-password' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLoginAPI).toHaveBeenCalledWith({
        method: 'master_password',
        email: 'test@example.com',
        masterPassword: 'test-password',
      });
    });
  });

  it('displays error message on login failure', async () => {
    const loginError = new Error('Invalid credentials');
    mockLoginAPI.mockRejectedValue(loginError);

    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    // Wait for initial session check
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByLabelText('メールアドレス'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText('APIキー'), {
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
    mockLoginAPI.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));

    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('メールアドレス')).toBeInTheDocument();
    });

    // Fill in the form
    fireEvent.change(screen.getByLabelText('メールアドレス'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText('APIキー'), {
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
