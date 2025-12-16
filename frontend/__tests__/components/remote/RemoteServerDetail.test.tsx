import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import useSWR from 'swr';
import RemoteServerDetail from '../../../components/remote/RemoteServerDetail';
import { RemoteServer, RemoteServerStatus } from '../../../lib/types/remote';
import {
  startRemoteOAuth,
  testRemoteServer,
  fetchRemoteServerById,
} from '../../../lib/api/remoteServers';
import { createPkcePair } from '../../../lib/utils/pkce';

jest.mock('swr', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('../../../lib/api/remoteServers', () => ({
  __esModule: true,
  fetchRemoteServerById: jest.fn(),
  startRemoteOAuth: jest.fn(),
  testRemoteServer: jest.fn(),
}));

jest.mock('../../../lib/utils/pkce', () => ({
  __esModule: true,
  createPkcePair: jest.fn(),
}));

const mockUseSWR = useSWR as jest.Mock;
const mockStartOAuth = startRemoteOAuth as jest.Mock;
const mockTestRemote = testRemoteServer as jest.Mock;
const mockPkce = createPkcePair as jest.Mock;
const mockFetchById = fetchRemoteServerById as jest.Mock;

const baseServer: RemoteServer = {
  server_id: 'srv-1',
  catalog_item_id: 'cat-1',
  name: 'Alpha Remote',
  endpoint: 'https://alpha.example.com/sse',
  status: RemoteServerStatus.AUTH_REQUIRED,
  created_at: '2024-01-01T00:00:00Z',
};

describe('RemoteServerDetail', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    mockFetchById.mockResolvedValue(baseServer);
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { assign: jest.fn() },
    });
  });

  it('renders loading and error states', () => {
    mockUseSWR.mockReturnValueOnce({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: jest.fn(),
    });

    render(<RemoteServerDetail serverId={baseServer.server_id} />);
    expect(screen.getByText('詳細を取得中...')).toBeInTheDocument();

    mockUseSWR.mockReturnValueOnce({
      data: undefined,
      error: new Error('not found'),
      isLoading: false,
      mutate: jest.fn(),
    });
    render(<RemoteServerDetail serverId={baseServer.server_id} />);
    expect(screen.getByText('リモートサーバーの取得に失敗しました')).toBeInTheDocument();
    expect(screen.getByText('not found')).toBeInTheDocument();
  });

  it('shows server detail when loaded', () => {
    mockUseSWR.mockReturnValue({
      data: baseServer,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<RemoteServerDetail serverId={baseServer.server_id} />);

    expect(screen.getByText('Alpha Remote')).toBeInTheDocument();
    expect(screen.getByText(baseServer.endpoint)).toBeInTheDocument();
    expect(screen.getByText('要認証')).toBeInTheDocument();
  });

  it('starts OAuth flow and stores PKCE', async () => {
    mockUseSWR.mockReturnValue({
      data: baseServer,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });
    mockPkce.mockResolvedValue({
      codeVerifier: 'verifier-1234567890-verifier-1234567890-verifier-12',
      codeChallenge: 'challenge-abc',
    });
    mockStartOAuth.mockResolvedValue({
      auth_url: 'https://auth.example.com',
      state: 'state-123',
      required_scopes: ['scope-a'],
    });

    render(<RemoteServerDetail serverId={baseServer.server_id} />);

    fireEvent.click(screen.getByRole('button', { name: '認証開始' }));

    await waitFor(() => {
      expect(mockStartOAuth).toHaveBeenCalledWith({
        serverId: baseServer.server_id,
        codeChallenge: 'challenge-abc',
      });
    });

    const stored = sessionStorage.getItem('oauth:pkce:state-123');
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored || '{}');
    expect(parsed.codeVerifier).toBe(
      'verifier-1234567890-verifier-1234567890-verifier-12'
    );
    expect(parsed.serverId).toBe(baseServer.server_id);
    expect(parsed.createdAt).toEqual(expect.any(Number));
    expect((window.location as any).assign).toHaveBeenCalledWith('https://auth.example.com');
  });

  it('runs connection test and shows result', async () => {
    mockUseSWR.mockReturnValue({
      data: baseServer,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });
    mockTestRemote.mockResolvedValue({
      server_id: baseServer.server_id,
      reachable: true,
      authenticated: false,
      error: null,
    });

    render(<RemoteServerDetail serverId={baseServer.server_id} />);

    fireEvent.click(screen.getByRole('button', { name: '接続テスト' }));

    await waitFor(() => {
      expect(mockTestRemote).toHaveBeenCalledWith(baseServer.server_id);
    });

    expect(screen.getByText('接続テスト結果')).toBeInTheDocument();
    expect(screen.getByText('到達性: OK')).toBeInTheDocument();
    expect(screen.getByText('認証: 未認証')).toBeInTheDocument();
  });
});
