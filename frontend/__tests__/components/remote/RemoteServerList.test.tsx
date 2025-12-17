import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import useSWR from 'swr';
import RemoteServerList from '../../../components/remote/RemoteServerList';
import { RemoteServer, RemoteServerStatus } from '../../../lib/types/remote';

jest.mock('swr', () => ({
  __esModule: true,
  default: jest.fn(),
}));

const mockUseSWR = useSWR as jest.Mock;

const mockServers: RemoteServer[] = [
  {
    server_id: 'srv-1',
    catalog_item_id: 'cat-1',
    name: 'Alpha Server',
    endpoint: 'https://alpha.example.com',
    status: RemoteServerStatus.AUTH_REQUIRED,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    server_id: 'srv-2',
    catalog_item_id: 'cat-2',
    name: 'Beta Server',
    endpoint: 'https://beta.example.com',
    status: RemoteServerStatus.AUTHENTICATED,
    created_at: '2024-01-02T00:00:00Z',
  },
  {
    server_id: 'srv-3',
    catalog_item_id: 'cat-3',
    name: 'Gamma Server',
    endpoint: 'https://gamma.example.com',
    status: RemoteServerStatus.ERROR,
    error_message: 'unreachable',
    created_at: '2024-01-03T00:00:00Z',
  },
];

describe('RemoteServerList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: jest.fn(),
    });

    render(<RemoteServerList />);

    expect(screen.getByText('リモートサーバーを読み込み中...')).toBeInTheDocument();
  });

  it('renders error state', () => {
    mockUseSWR.mockReturnValue({
      data: undefined,
      error: new Error('network failed'),
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<RemoteServerList />);

    expect(screen.getByText('リモートサーバー一覧の取得に失敗しました')).toBeInTheDocument();
    expect(screen.getByText('network failed')).toBeInTheDocument();
  });

  it('renders servers with status badges', () => {
    mockUseSWR.mockReturnValue({
      data: mockServers,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<RemoteServerList />);

    expect(mockUseSWR).toHaveBeenCalledWith(
      'remote-servers',
      expect.any(Function),
      expect.any(Object)
    );

    expect(screen.getAllByTestId('remote-server-row')).toHaveLength(3);
    expect(screen.getByText('Alpha Server')).toBeInTheDocument();
    expect(screen.getByText('Beta Server')).toBeInTheDocument();
    expect(screen.getAllByTestId('status-badge').some(el => el.textContent?.includes('要認証'))).toBe(
      true
    );
    expect(screen.getAllByTestId('status-badge').some(el => el.textContent?.includes('認証済み'))).toBe(
      true
    );
  });

  it('filters servers by search term', () => {
    mockUseSWR.mockReturnValue({
      data: mockServers,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<RemoteServerList />);

    const searchInput = screen.getByTestId('remote-search');
    fireEvent.change(searchInput, { target: { value: 'gamma' } });

    expect(screen.getByText('Gamma Server')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Server')).not.toBeInTheDocument();
    expect(screen.queryByText('Beta Server')).not.toBeInTheDocument();
  });

  it('filters servers by status', () => {
    mockUseSWR.mockReturnValue({
      data: mockServers,
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<RemoteServerList />);

    const statusSelect = screen.getByTestId('status-filter');
    fireEvent.change(statusSelect, { target: { value: RemoteServerStatus.AUTHENTICATED } });

    expect(screen.getByText('Beta Server')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Server')).not.toBeInTheDocument();
    expect(screen.queryByText('Gamma Server')).not.toBeInTheDocument();
  });
});
