import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SessionProvider, useSession } from '../../contexts/SessionContext';
import * as authAPI from '../../lib/api/auth';

// Mock the auth API
jest.mock('../../lib/api/auth');

const mockLoginAPI = authAPI.loginAPI as jest.MockedFunction<typeof authAPI.loginAPI>;
const mockLogoutAPI = authAPI.logoutAPI as jest.MockedFunction<typeof authAPI.logoutAPI>;
const mockCheckSessionAPI = authAPI.checkSessionAPI as jest.MockedFunction<typeof authAPI.checkSessionAPI>;

// Test component that uses the session context
function TestComponent() {
  const { session, isLoading, error, login, logout } = useSession();

  return (
    <div>
      <div data-testid="loading">{isLoading ? 'loading' : 'not-loading'}</div>
      <div data-testid="session">{session ? session.user_email : 'no-session'}</div>
      <div data-testid="error">{error || 'no-error'}</div>
      <button onClick={async () => await login({ method: 'api_key', email: 'test@example.com', apiKey: 'key' })}>
        Login
      </button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

describe('SessionProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('checks session on mount', async () => {
    mockCheckSessionAPI.mockResolvedValue({
      valid: true,
      session: {
        session_id: 'test-session',
        user_email: 'test@example.com',
        expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
        created_at: new Date().toISOString(),
      },
    });

    await act(async () => {
      render(
        <SessionProvider>
          <TestComponent />
        </SessionProvider>
      );
    });

    // Initially loading
    expect(screen.getByTestId('loading')).toHaveTextContent('loading');

    // After check, should have session
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading');
      expect(screen.getByTestId('session')).toHaveTextContent('test@example.com');
    });

    expect(mockCheckSessionAPI).toHaveBeenCalledTimes(1);
  });

  it('handles no existing session', async () => {
    mockCheckSessionAPI.mockResolvedValue({ valid: false });

    await act(async () => {
      render(
        <SessionProvider>
          <TestComponent />
        </SessionProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading');
      expect(screen.getByTestId('session')).toHaveTextContent('no-session');
    });
  });

  it('handles login successfully', async () => {
    mockCheckSessionAPI.mockResolvedValue({ valid: false });
    mockLoginAPI.mockResolvedValue({
      session_id: 'new-session',
      user_email: 'test@example.com',
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: new Date().toISOString(),
    });

    await act(async () => {
      render(
        <SessionProvider>
          <TestComponent />
        </SessionProvider>
      );
    });

    // Wait for initial check
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading');
    });

            // Click login
            const loginButton = screen.getByText('Login');
            await act(async () => {
              try {
                loginButton.click();
              } catch (e) {
                // Expected to throw, catch it to allow act block to complete
              }
            });
    await waitFor(() => {
      expect(screen.getByTestId('session')).toHaveTextContent('test@example.com');
    });

    expect(mockLoginAPI).toHaveBeenCalledWith({
      method: 'api_key',
      email: 'test@example.com',
      apiKey: 'key',
    });
  });

  it('handles login failure', async () => {
    mockCheckSessionAPI.mockResolvedValue({ valid: false });
    const loginError = new Error('Login failed');
    await act(async () => {
      render(
        <SessionProvider>
          <TestComponent />
        </SessionProvider>
      );
    });

    // Wait for initial check
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('not-loading');
    });

                    // Click login

                    const loginButton = screen.getByText('Login');

                    await act(async () => {

                      loginButton.click();

                    });

            

                    await waitFor(() => {

                      expect(screen.getByTestId('error')).toHaveTextContent('Login failed');

                      expect(screen.getByTestId('session')).toHaveTextContent('no-session');

                    });  });

  it('handles logout successfully', async () => {
    mockCheckSessionAPI.mockResolvedValue({
      valid: true,
      session: {
        session_id: 'test-session',
        user_email: 'test@example.com',
        expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
        created_at: new Date().toISOString(),
      },
    });
    mockLogoutAPI.mockResolvedValue();

    await act(async () => {
      render(
        <SessionProvider>
          <TestComponent />
        </SessionProvider>
      );
    });

    // Wait for session to be established
    await waitFor(() => {
      expect(screen.getByTestId('session')).toHaveTextContent('test@example.com');
    });

    // Click logout
    const logoutButton = screen.getByText('Logout');
    await act(async () => {
      logoutButton.click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('session')).toHaveTextContent('no-session');
    });

    expect(mockLogoutAPI).toHaveBeenCalledTimes(1);
  });

  it('throws error when useSession is used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useSession must be used within a SessionProvider');

    consoleSpy.mockRestore();
  });
});
