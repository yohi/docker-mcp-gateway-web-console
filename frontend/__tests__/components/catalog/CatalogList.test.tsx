import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogList from '../../../components/catalog/CatalogList';
import useSWR from 'swr';
import { CatalogItem } from '../../../lib/types/catalog';
import { RemoteServer, RemoteServerStatus } from '../../../lib/types/remote';

// Mock SWR
jest.mock('swr', () => ({
  __esModule: true,
  default: jest.fn(),
}));

// Mock useContainers
jest.mock('../../../hooks/useContainers', () => ({
  useContainers: () => ({
    containers: [],
    isLoading: false,
    isError: false,
    refresh: jest.fn(),
  }),
}));

// Mock ToastContext
jest.mock('../../../contexts/ToastContext', () => ({
  useToast: () => ({
    showSuccess: jest.fn(),
    showError: jest.fn(),
  }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock SearchBar to avoid timer issues and simplify testing
jest.mock('../../../components/catalog/SearchBar', () => {
  return function MockSearchBar({ onSearch, categories, initialQuery, initialCategory }: any) {
    return (
      <div data-testid="search-bar">
        <input
          data-testid="search-input"
          value={initialQuery}
          onChange={(e) => onSearch(e.target.value, initialCategory)}
        />
        <select
          data-testid="category-select"
          value={initialCategory}
          onChange={(e) => onSearch(initialQuery, e.target.value)}
        >
          <option value="">All</option>
          {categories.map((c: string) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    );
  };
});

const mockUseSWR = useSWR as jest.Mock;

const mockItems: CatalogItem[] = [
  {
    id: 'server-1',
    name: 'Server One',
    description: 'Description One',
    category: 'utility',
    docker_image: 'image-1',
    default_env: {},
    required_envs: [],
    required_secrets: [],
    vendor: 'v1',
    icon_url: '',
    required_scopes: ['repo:read'],
    verify_signatures: true,
  },
  {
    id: 'server-2',
    name: 'Server Two',
    description: 'Description Two',
    category: 'ai',
    docker_image: 'image-2',
    default_env: {},
    required_envs: [],
    required_secrets: ['API_KEY'],
    vendor: 'v2',
    icon_url: '',
    required_scopes: [],
    verify_signatures: false,
  },
];

const remoteItem: CatalogItem = {
  id: 'remote-1',
  name: 'Remote Server',
  description: 'Remote endpoint catalog entry',
  category: 'remote',
  docker_image: '',
  remote_endpoint: 'https://api.example.com/sse',
  is_remote: true,
  server_type: 'remote',
  default_env: {},
  required_envs: [],
  required_secrets: [],
  vendor: 'remote-vendor',
  icon_url: '',
  required_scopes: [],
  verify_signatures: true,
};

const remoteServerRecord: RemoteServer = {
  server_id: 'remote-1-id',
  catalog_item_id: 'remote-1',
  name: 'Remote Server',
  endpoint: 'https://api.example.com/sse',
  status: RemoteServerStatus.REGISTERED,
  credential_key: null,
  last_connected_at: null,
  error_message: null,
  created_at: new Date().toISOString(),
};

// Mock IntersectionObserver for jsdom environment
const mockIntersectionObserver = jest.fn(() => ({
  observe: jest.fn(),
  disconnect: jest.fn(),
  unobserve: jest.fn(),
}));

describe('CatalogList', () => {
  const mockOnInstall = jest.fn();
  const catalogSource = 'docker' as const;
  const mockOnSelect = jest.fn();
  const emptyRemoteResponse = {
    data: [],
    error: undefined,
    isLoading: false,
    mutate: jest.fn(),
    isValidating: false,
  };

  const setMockSWRResponses = (catalogResponse: any, remoteResponse: any = emptyRemoteResponse) => {
    mockUseSWR.mockImplementation((key: string) => {
      if (typeof key === 'string' && key.startsWith('catalog|')) {
        return catalogResponse;
      }
      if (key === 'remote-servers-catalog') {
        return remoteResponse;
      }
      return {
        data: undefined,
        error: undefined,
        isLoading: false,
        mutate: jest.fn(),
      };
    });
  };

  beforeAll(() => {
    (global as any).IntersectionObserver = mockIntersectionObserver;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state', () => {
    setMockSWRResponses({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Loading catalog...')).toBeInTheDocument();
  });

  it('renders error state', () => {
    setMockSWRResponses({
      data: undefined,
      error: new Error('Failed to fetch'),
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Failed to load catalog')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument();
  });

  it('renders list of servers', () => {
    setMockSWRResponses({
      data: { servers: mockItems, cached: false, total: mockItems.length, page_size: mockItems.length },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Server One')).toBeInTheDocument();
    expect(screen.getByText('Server Two')).toBeInTheDocument();
    expect(screen.getByText(/読み込み済み/)).toBeInTheDocument();
  });

  it('renders empty state', () => {
    setMockSWRResponses({
      data: { servers: [], cached: false, total: 0, page_size: 10 },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    // There are multiple elements with this text (count and empty state message)
    expect(screen.getAllByText('No servers found')).toHaveLength(2);
  });

  it('handles install click', () => {
    setMockSWRResponses({
      data: { servers: mockItems, cached: false, total: mockItems.length, page_size: mockItems.length },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    const installButtons = screen.getAllByText('インストール');
    fireEvent.click(installButtons[0]);

    expect(mockOnInstall).toHaveBeenCalledWith(mockItems[0]);
  });

  it('updates SWR key on search', async () => {
    setMockSWRResponses({
      data: { servers: mockItems, cached: false },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    // Initial call check
    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(`catalog|${catalogSource}||`), // Empty query and category
      expect.any(Function),
      expect.any(Object)
    );

    // Simulate search
    const searchInput = screen.getByTestId('search-input');
    fireEvent.change(searchInput, { target: { value: 'test' } });

    // SWR should be called with new key on next render
    await waitFor(() => {
      expect(mockUseSWR).toHaveBeenCalledWith(
        expect.stringContaining(`catalog|${catalogSource}|test|`),
        expect.any(Function),
        expect.any(Object)
      );
    });
  });

  it('extracts and passes categories to SearchBar', () => {
    setMockSWRResponses({
      data: { servers: mockItems, cached: false, total: mockItems.length, page_size: mockItems.length },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    // Check if categories are passed to the mock search bar (rendered as options)
    // Scope to the select element to avoid matching badges in ServerCard
    const select = screen.getByTestId('category-select');
    expect(select).toBeInTheDocument();
    // We can check if options exist
    expect(screen.getAllByText('utility').find(el => el.tagName === 'OPTION')).toBeInTheDocument();
    expect(screen.getAllByText('ai').find(el => el.tagName === 'OPTION')).toBeInTheDocument();
  });

  it('renders remote catalog items with badge and endpoint', () => {
    setMockSWRResponses(
      {
        data: { servers: [remoteItem], cached: false, total: 1, page_size: 1 },
        error: undefined,
        isLoading: false,
        mutate: jest.fn(),
      },
      {
        data: [remoteServerRecord],
        error: undefined,
        isLoading: false,
        mutate: jest.fn(),
        isValidating: false,
      }
    );

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Remote Server')).toBeInTheDocument();
    expect(screen.getAllByText('remote').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/リモートエンドポイント/)).toBeInTheDocument();
    expect(screen.getByText(/https:\/\/api\.example\.com\/sse/)).toBeInTheDocument();
    // ステータスバッジ
    expect(screen.getByText('登録済み')).toBeInTheDocument();
    expect(screen.queryByText('インストール')).not.toBeInTheDocument();
  });

  it('falls back to cached data when fetching fails after a success', async () => {
    let catalogCallCount = 0;
    mockUseSWR.mockImplementation((key: string) => {
      if (key === 'remote-servers-catalog') {
        return emptyRemoteResponse;
      }

      if (key.startsWith('catalog|')) {
        catalogCallCount += 1;
        if (catalogCallCount === 1) {
          return {
            data: { servers: mockItems, cached: false, total: mockItems.length, page_size: mockItems.length },
            error: undefined,
            isLoading: false,
            isValidating: false,
            mutate: jest.fn(),
          };
        }
        return {
          data: undefined,
          error: new Error('Network error'),
          isLoading: false,
          isValidating: false,
          mutate: jest.fn(),
        };
      }

      return {
        data: undefined,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: jest.fn(),
      };
    });

    const { rerender } = render(
      <CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />
    );

    // First render shows fetched data
    expect(screen.getByText('Server One')).toBeInTheDocument();

    // Second render simulates fetch failure, should show cached data + warning
    rerender(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    await waitFor(() => {
      expect(screen.getByText('Server One')).toBeInTheDocument();
      expect(screen.getByText(/最後に成功したカタログ/)).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  // Task 9 Tests: Structured error code handling (Requirements: 1.4, 1.5, 4.3, 4.4)
  describe('structured error handling', () => {
    // Helper to create a CatalogError with error_code
    const createCatalogError = (code: string, detail: string, retryAfter?: number) => {
      const error = new Error(detail) as any;
      error.error_code = code;
      error.retry_after_seconds = retryAfter;
      return error;
    };

    it('displays rate limit error with countdown when error_code is rate_limited', async () => {
      const rateLimitError = createCatalogError('rate_limited', '上流サービスのレート制限に達しました', 60);

      setMockSWRResponses({
        data: undefined,
        error: rateLimitError,
        isLoading: false,
        mutate: jest.fn(),
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      // Should display rate limit specific title
      expect(screen.getByRole('heading', { name: /レート制限に達しました/ })).toBeInTheDocument();
      // Should display countdown timer
      expect(screen.getByText(/60/)).toBeInTheDocument();
      // Should have retry timer indicator
      expect(screen.getByTestId('rate-limit-countdown')).toBeInTheDocument();
    });

    it('displays upstream unavailable error with retry button when error_code is upstream_unavailable', async () => {
      const upstreamError = createCatalogError('upstream_unavailable', 'カタログサービスに一時的にアクセスできません');

      setMockSWRResponses({
        data: undefined,
        error: upstreamError,
        isLoading: false,
        mutate: jest.fn(),
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      // Should display upstream unavailable specific title
      expect(screen.getByRole('heading', { name: /上流サービスが利用できません/ })).toBeInTheDocument();
      // Should have retry button
      const retryButton = screen.getByRole('button', { name: /再試行/ });
      expect(retryButton).toBeInTheDocument();
      expect(retryButton).not.toBeDisabled();
    });

    it('displays invalid source error appropriately when error_code is invalid_source', async () => {
      const invalidSourceError = createCatalogError('invalid_source', '指定されたカタログソースは無効です');

      setMockSWRResponses({
        data: undefined,
        error: invalidSourceError,
        isLoading: false,
        mutate: jest.fn(),
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      // Should display invalid source error title
      expect(screen.getByRole('heading', { name: /無効なソースです/ })).toBeInTheDocument();
    });

    it('displays generic error for internal_error code', async () => {
      const internalError = createCatalogError('internal_error', 'サーバーで問題が発生しました');

      setMockSWRResponses({
        data: undefined,
        error: internalError,
        isLoading: false,
        mutate: jest.fn(),
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      // Should display internal error title
      expect(screen.getByRole('heading', { name: /内部エラーが発生しました/ })).toBeInTheDocument();
      // Should have retry button for recovery
      expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
    });

    it('countdown timer decrements and enables retry when reaching zero', async () => {
      jest.useFakeTimers();

      const rateLimitError = createCatalogError('rate_limited', 'レート制限に達しました', 3);
      const mockMutate = jest.fn();

      setMockSWRResponses({
        data: undefined,
        error: rateLimitError,
        isLoading: false,
        mutate: mockMutate,
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      // Initial countdown
      expect(screen.getByText(/3/)).toBeInTheDocument();

      // Advance timer by 1 second
      jest.advanceTimersByTime(1000);
      await waitFor(() => {
        expect(screen.getByText(/2/)).toBeInTheDocument();
      });

      // Advance to zero
      jest.advanceTimersByTime(2000);
      await waitFor(() => {
        // When countdown reaches zero, retry button should be enabled
        const retryButton = screen.getByRole('button', { name: /再試行/ });
        expect(retryButton).not.toBeDisabled();
      });

      jest.useRealTimers();
    });

    it('retry button triggers mutate for upstream unavailable error', async () => {
      const upstreamError = createCatalogError('upstream_unavailable', 'カタログサービスに一時的にアクセスできません');
      const mockMutate = jest.fn();

      setMockSWRResponses({
        data: undefined,
        error: upstreamError,
        isLoading: false,
        mutate: mockMutate,
      });

      render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

      const retryButton = screen.getByRole('button', { name: /再試行/ });
      fireEvent.click(retryButton);

      expect(mockMutate).toHaveBeenCalled();
    });
  });
});

