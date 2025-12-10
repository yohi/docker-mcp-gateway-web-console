import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogList from '../../../components/catalog/CatalogList';
import useSWR from 'swr';
import { CatalogItem } from '../../../lib/types/catalog';

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

describe('CatalogList', () => {
  const mockOnInstall = jest.fn();
  const catalogSource = 'http://test.com/catalog.json';
  const mockOnSelect = jest.fn();

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

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Loading catalog...')).toBeInTheDocument();
  });

  it('renders error state', () => {
    mockUseSWR.mockReturnValue({
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
    mockUseSWR.mockReturnValue({
      data: { servers: mockItems, cached: false },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    expect(screen.getByText('Server One')).toBeInTheDocument();
    expect(screen.getByText('Server Two')).toBeInTheDocument();
    // Use regex to match split text
    expect(screen.getByText(/Showing/)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/servers/)).toBeInTheDocument();
  });

  it('renders empty state', () => {
    mockUseSWR.mockReturnValue({
      data: { servers: [], cached: false },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} onSelect={mockOnSelect} />);

    // There are multiple elements with this text (count and empty state message)
    expect(screen.getAllByText('No servers found')).toHaveLength(2);
  });

  it('handles install click', () => {
    mockUseSWR.mockReturnValue({
      data: { servers: mockItems, cached: false },
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
    mockUseSWR.mockReturnValue({
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
    mockUseSWR.mockReturnValue({
      data: { servers: mockItems, cached: false },
      error: undefined,
      isLoading: false,
      mutate: jest.fn(),
    });

    render(<CatalogList catalogSource={catalogSource} onInstall={mockOnInstall} />);

    // Check if categories are passed to the mock search bar (rendered as options)
    // Scope to the select element to avoid matching badges in ServerCard
    const select = screen.getByTestId('category-select');
    expect(select).toBeInTheDocument();
    // We can check if options exist
    expect(screen.getAllByText('utility').find(el => el.tagName === 'OPTION')).toBeInTheDocument();
    expect(screen.getAllByText('ai').find(el => el.tagName === 'OPTION')).toBeInTheDocument();
  });
});
