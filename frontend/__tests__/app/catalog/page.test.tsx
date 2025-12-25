import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogPage from '../../../app/catalog/page';
import { CatalogSourceId, DEFAULT_CATALOG_SOURCE } from '../../../lib/constants/catalogSources';

// Mock ProtectedRoute to just render children
jest.mock('../../../components/auth/ProtectedRoute', () => ({
    __esModule: true,
    default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock MainLayout to just render children
jest.mock('../../../components/layout', () => ({
    MainLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="main-layout">{children}</div>,
}));

// Mock CatalogList with per-source error simulation
const mockCatalogList = jest.fn();
const mockSourceErrors: Map<CatalogSourceId, Error> = new Map();

// Helper function to set error for specific source
export const setSourceError = (source: CatalogSourceId, error: Error | null) => {
    if (error === null) {
        mockSourceErrors.delete(source);
    } else {
        mockSourceErrors.set(source, error);
    }
};

// Helper function to clear all errors
export const clearAllErrors = () => {
    mockSourceErrors.clear();
};

jest.mock('../../../components/catalog/CatalogList', () => {
    return function MockCatalogList(props: { catalogSource: CatalogSourceId; onInstall: any; onSelect: any }) {
        mockCatalogList(props);

        // Check if this source has an error
        const error = mockSourceErrors.get(props.catalogSource);
        const hasError = error !== undefined;

        return (
            <div
                data-testid="catalog-list"
                data-source={props.catalogSource}
                data-error={hasError ? 'true' : 'false'}
            >
                {hasError ? (
                    <div data-testid="catalog-error">
                        Error: {error?.message}
                    </div>
                ) : (
                    <button onClick={() => props.onInstall({ id: 'test', name: 'Test Server' })}>
                        Install Test
                    </button>
                )}
            </div>
        );
    };
});

// Mock CatalogSourceSelector
const mockOnSourceChange = jest.fn();
jest.mock('../../../components/catalog/CatalogSourceSelector', () => {
    return function MockCatalogSourceSelector(props: {
        selectedSource: CatalogSourceId;
        onSourceChange: (source: CatalogSourceId) => void;
        disabled?: boolean;
    }) {
        // Store the callback for later use
        mockOnSourceChange.mockImplementation((source: CatalogSourceId) => props.onSourceChange(source));
        return (
            <div data-testid="catalog-source-selector" data-selected={props.selectedSource}>
                <select
                    data-testid="source-select"
                    value={props.selectedSource}
                    onChange={(e) => props.onSourceChange(e.target.value as CatalogSourceId)}
                >
                    <option value="docker">Docker MCP Catalog</option>
                    <option value="official">Official MCP Registry</option>
                </select>
            </div>
        );
    };
});

// Mock InstallModal
jest.mock('../../../components/catalog/InstallModal', () => ({
    __esModule: true,
    default: () => <div data-testid="install-modal" />,
}));

// Mock CatalogDetailModal
jest.mock('../../../components/catalog/CatalogDetailModal', () => ({
    __esModule: true,
    default: () => <div data-testid="catalog-detail-modal" />,
}));

// Mock OAuthModal
jest.mock('../../../components/catalog/OAuthModal', () => ({
    __esModule: true,
    default: () => <div data-testid="oauth-modal" />,
}));

// Mock ToastContext
jest.mock('../../../contexts/ToastContext', () => ({
    useToast: () => ({
        showSuccess: jest.fn(),
        showError: jest.fn(),
    }),
}));

// Mock SWR mutate
jest.mock('swr', () => ({
    mutate: jest.fn(),
}));

// Mock remoteServers API
jest.mock('../../../lib/api/remoteServers', () => ({
    createRemoteServer: jest.fn(),
}));

describe('CatalogPage - Source State Management (Task 8)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        clearAllErrors(); // Reset all source errors
    });

    describe('Requirement 1.3: Default Docker source on initial display', () => {
        it('sets Docker source as default on initial render', () => {
            render(<CatalogPage />);

            // Verify CatalogSourceSelector receives docker as default
            const selector = screen.getByTestId('catalog-source-selector');
            expect(selector).toHaveAttribute('data-selected', 'docker');

            // Verify CatalogList receives docker as source
            const catalogList = screen.getByTestId('catalog-list');
            expect(catalogList).toHaveAttribute('data-source', 'docker');
        });

        it('uses DEFAULT_CATALOG_SOURCE constant as initial state', () => {
            render(<CatalogPage />);

            expect(mockCatalogList).toHaveBeenCalledWith(
                expect.objectContaining({
                    catalogSource: DEFAULT_CATALOG_SOURCE,
                })
            );
        });
    });

    describe('Requirement 1.2: Catalog list refresh on source change', () => {
        it('updates catalog list when user changes source to official', async () => {
            render(<CatalogPage />);

            // Initial: docker
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');

            // Change source to official
            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            // Verify catalog list source updated
            await waitFor(() => {
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            });
        });

        it('updates catalog list when user changes source back to docker', async () => {
            render(<CatalogPage />);

            // Change to official
            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            await waitFor(() => {
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            });

            // Change back to docker
            fireEvent.change(select, { target: { value: 'docker' } });

            await waitFor(() => {
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');
            });
        });
    });

    describe('Requirement 6.5: Source switching without page reload', () => {
        it('does not trigger page reload or navigation on source change', async () => {
            const originalLocation = window.location.href;

            render(<CatalogPage />);

            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            await waitFor(() => {
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            });

            // Verify no navigation occurred
            expect(window.location.href).toBe(originalLocation);
        });
    });

    describe('Requirement 6.2: Unchanged source behaves as Docker', () => {
        it('behaves as if Docker is selected when user does not change source', () => {
            render(<CatalogPage />);

            // Should render with docker without any user interaction
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');
        });
    });

    describe('Requirement 4.5: Preserve selected source on error', () => {
        it('preserves selected source when catalog fetch error occurs', async () => {
            // Set up error condition for 'official' source before switching to it
            setSourceError('official', new Error('Failed to fetch catalog'));

            render(<CatalogPage />);

            // Initial state: docker (no error)
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-error', 'false');

            // User changes source to official, which has an error
            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            // Wait for source change and error to appear
            await waitFor(() => {
                expect(screen.getByTestId('catalog-error')).toBeInTheDocument();
            });

            // CRITICAL ASSERTION: Despite the error, source selection remains 'official' (not reset to 'docker')
            const selector = screen.getByTestId('catalog-source-selector');
            expect(selector).toHaveAttribute('data-selected', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-error', 'true');
            expect(screen.getByTestId('catalog-error')).toHaveTextContent('Failed to fetch catalog');
        });

        it('allows retry with same source after error', async () => {
            // Set up error for 'official' source
            setSourceError('official', new Error('Network error'));

            render(<CatalogPage />);

            // Change to official (which has error)
            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            // Wait for error to appear
            await waitFor(() => {
                expect(screen.getByTestId('catalog-error')).toBeInTheDocument();
            });

            // Verify source is 'official' with error
            expect(screen.getByTestId('catalog-source-selector')).toHaveAttribute('data-selected', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-error', 'true');

            // Simulate successful retry by clearing the error for 'official'
            setSourceError('official', null);

            // Trigger re-render by switching away and back (simulating retry)
            fireEvent.change(select, { target: { value: 'docker' } });
            await waitFor(() => {
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');
            });

            fireEvent.change(select, { target: { value: 'official' } });

            // After retry (error cleared), should show success for 'official'
            await waitFor(() => {
                expect(screen.queryByTestId('catalog-error')).not.toBeInTheDocument();
                expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-error', 'false');
            });

            // CRITICAL ASSERTION: Source is still 'official' after successful retry
            expect(screen.getByTestId('catalog-source-selector')).toHaveAttribute('data-selected', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
        });

        it('does not reset source to default on error', async () => {
            // Set up error for 'official' source
            setSourceError('official', new Error('Upstream unavailable'));

            render(<CatalogPage />);

            // Start with docker (default, no error)
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'docker');

            // User changes to official (which has error)
            const select = screen.getByTestId('source-select');
            fireEvent.change(select, { target: { value: 'official' } });

            // Wait for error to appear
            await waitFor(() => {
                expect(screen.getByTestId('catalog-error')).toBeInTheDocument();
            });

            // CRITICAL ASSERTION: Source does NOT reset to default ('docker') on error
            // It stays as 'official' even though there's an error
            const selector = screen.getByTestId('catalog-source-selector');
            expect(selector).toHaveAttribute('data-selected', 'official');
            expect(selector).not.toHaveAttribute('data-selected', 'docker');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-source', 'official');
            expect(screen.getByTestId('catalog-list')).toHaveAttribute('data-error', 'true');
        });
    });

    describe('UI Integration: CatalogSourceSelector is integrated', () => {
        it('renders CatalogSourceSelector component', () => {
            render(<CatalogPage />);

            expect(screen.getByTestId('catalog-source-selector')).toBeInTheDocument();
        });

        it('replaces free-form URL input with preset selector', () => {
            render(<CatalogPage />);

            // Free-form URL input should not exist
            expect(screen.queryByPlaceholderText(/github.com/i)).not.toBeInTheDocument();
            expect(screen.queryByLabelText(/Catalog Source URL/i)).not.toBeInTheDocument();

            // Preset selector should exist
            expect(screen.getByTestId('catalog-source-selector')).toBeInTheDocument();
        });
    });
});
