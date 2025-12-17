import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OAuthCallbackPage from '../../app/oauth/callback/page';
import { completeOAuthCallback } from '../../lib/api/oauth';
import { useRouter, useSearchParams } from 'next/navigation';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(),
}));

jest.mock('../../lib/api/oauth', () => ({
  __esModule: true,
  completeOAuthCallback: jest.fn(),
}));

const mockUseRouter = useRouter as jest.Mock;
const mockUseSearchParams = useSearchParams as jest.Mock;
const mockCompleteCallback = completeOAuthCallback as jest.Mock;

function setSearchParams(params: Record<string, string | undefined>) {
  mockUseSearchParams.mockReturnValue({
    get: (key: string) => params[key] ?? null,
    toString: () => new URLSearchParams(params as Record<string, string>).toString(),
  });
}

describe('OAuthCallbackPage', () => {
  const replace = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    mockUseRouter.mockReturnValue({ replace });
    Object.defineProperty(window, 'opener', { value: null, writable: true });
  });

  it('exchanges code using stored verifier and redirects to returnUrl', async () => {
    setSearchParams({ code: 'auth-code', state: 'state-123' });
    sessionStorage.setItem(
      'oauth:pkce:state-123',
      JSON.stringify({
        codeVerifier: 'verifier-xyz',
        serverId: 'remote-1',
        returnUrl: '/catalog?server=remote-1',
      })
    );
    mockCompleteCallback.mockResolvedValue({
      success: true,
      status: 'authenticated',
      scope: ['scope-a'],
      server_id: 'remote-1',
    });

    render(<OAuthCallbackPage />);

    await waitFor(() =>
      expect(mockCompleteCallback).toHaveBeenCalledWith({
        code: 'auth-code',
        state: 'state-123',
        serverId: 'remote-1',
        codeVerifier: 'verifier-xyz',
      })
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/catalog?server=remote-1'));
    expect(sessionStorage.getItem('oauth:pkce:state-123')).toBeNull();
  });

  it('posts message to opener when popup flow and does not redirect', async () => {
    const openerPostMessage = jest.fn();
    Object.defineProperty(window, 'opener', { value: { postMessage: openerPostMessage }, writable: true });
    const closeSpy = jest.spyOn(window, 'close').mockImplementation(() => {});

    setSearchParams({ code: 'abc', state: 'state-popup' });
    localStorage.setItem(
      'oauth:pkce:state-popup',
      JSON.stringify({
        codeVerifier: 'verifier-popup',
        serverId: 'remote-popup',
      })
    );
    mockCompleteCallback.mockResolvedValue({
      success: true,
      status: 'authenticated',
      scope: [],
      server_id: 'remote-popup',
    });

    render(<OAuthCallbackPage />);

    await waitFor(() =>
      expect(mockCompleteCallback).toHaveBeenCalledWith({
        code: 'abc',
        state: 'state-popup',
        serverId: 'remote-popup',
        codeVerifier: 'verifier-popup',
      })
    );

    await waitFor(() =>
      expect(openerPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'oauth:complete',
          state: 'state-popup',
          result: expect.objectContaining({ success: true }),
        }),
        window.location.origin
      )
    );
    expect(replace).not.toHaveBeenCalled();
    expect(localStorage.getItem('oauth:pkce:state-popup')).toBeNull();
    closeSpy.mockRestore();
  });

  it('shows an error when code or state is missing', async () => {
    setSearchParams({ code: undefined, state: 'state-missing' });

    render(<OAuthCallbackPage />);

    expect(await screen.findByText(/認証コードまたは state が見つかりません/)).toBeInTheDocument();
    expect(mockCompleteCallback).not.toHaveBeenCalled();
  });
});
