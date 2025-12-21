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

    expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Client Secret')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('マスターパスワード')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ログイン' })).toBeInTheDocument();
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
      expect(
        screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')
      ).toBeInTheDocument();
    });

    // Initially shows API key credential fields
    expect(
      screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Client Secret')).toBeInTheDocument();

    // Switch to master password
    const masterPasswordRadio = screen.getByRole('radio', { name: 'マスターパスワード' });
    fireEvent.click(masterPasswordRadio);

    // Now hides API key fields and keeps master password field
    expect(
      screen.queryByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')
    ).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Client Secret')).not.toBeInTheDocument();
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
    fireEvent.change(
      screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'),
      {
        target: { value: 'user.1234-5678' },
      }
    );
    fireEvent.change(screen.getByPlaceholderText('Client Secret'), {
      target: { value: 'test-secret' },
    });
    fireEvent.change(screen.getByPlaceholderText('マスターパスワード'), {
      target: { value: 'vault-pass' },
    });

    // Submit
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockLoginAPI).toHaveBeenCalledWith({
        method: 'api_key',
        email: 'test@example.com',
        client_id: 'user.1234-5678',
        client_secret: 'test-secret',
        master_password: 'vault-pass',
      });
    });
  });

  it('submits login with master password credentials', async () => {
    // Use a delayed mock to ensure loading state is visible
    mockLoginAPI.mockImplementation(() =>
      new Promise((resolve) =>
        setTimeout(() => resolve({
          session_id: 'test-session-id',
          user_email: 'test@example.com',
          expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
          created_at: new Date().toISOString(),
        }), 100)
      )
    );

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
    const submitButton = screen.getByRole('button', { name: 'ログイン' });
    await act(async () => {
      fireEvent.click(submitButton);
    });

    // Expect loading state after click
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'ログイン中...' })).toBeInTheDocument();
    });

    // Wait for login to complete
    await waitFor(() => {
      expect(mockLoginAPI).toHaveBeenCalledWith({
        method: 'master_password',
        email: 'test@example.com',
        master_password: 'test-password',
      });
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
    fireEvent.change(
      screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'),
      {
        target: { value: 'user.1234-5678' },
      }
    );
    fireEvent.change(screen.getByPlaceholderText('Client Secret'), {
      target: { value: 'wrong-key' },
    });
    fireEvent.change(screen.getByPlaceholderText('マスターパスワード'), {
      target: { value: 'vault-pass' },
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
    fireEvent.change(
      screen.getByPlaceholderText('user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'),
      {
        target: { value: 'user.1234-5678' },
      }
    );
    fireEvent.change(screen.getByPlaceholderText('Client Secret'), {
      target: { value: 'test-secret' },
    });
    fireEvent.change(screen.getByPlaceholderText('マスターパスワード'), {
      target: { value: 'vault-pass' },
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
