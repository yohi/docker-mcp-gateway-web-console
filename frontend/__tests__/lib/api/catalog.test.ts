import { fetchCatalog, searchCatalog, clearCatalogCache } from '../../../lib/api/catalog';
import { CatalogResponse } from '../../../lib/types/catalog';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('Catalog API', () => {
    beforeEach(() => {
        mockFetch.mockClear();
    });

    const mockCatalogResponse: CatalogResponse = {
        servers: [
            {
                id: 'test-id',
                name: 'Test Server',
                description: 'Test Description',
                category: 'utilities',
                docker_image: 'test/image:latest',
                default_env: {},
                required_secrets: [],
            },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        cached: true,
        categories: ['utilities'],
    };

    describe('fetchCatalog', () => {
        it('calls correct URL with source', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockCatalogResponse,
            });

            const source = 'http://example.com/catalog.json';
            const result = await fetchCatalog(source);

            // Check that the URL contains the encoded source parameter
            const expectedUrlPart = encodeURIComponent(source);
            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining(`source=${expectedUrlPart}`)
            );
            expect(result).toEqual(mockCatalogResponse);
        });

        it('calls correct URL without source', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockCatalogResponse,
            });

            // Assert that we can call it without arguments
            const result = await fetchCatalog();

            // Should not contain source parameter
            const callUrl = mockFetch.mock.calls[0][0];
            expect(callUrl).not.toContain('source=');
            expect(result).toEqual(mockCatalogResponse);
        });

        it('throws error on failure', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ detail: 'Fetch error' }),
            });

            await expect(fetchCatalog()).rejects.toThrow('Fetch error');
        });
    });

    describe('searchCatalog', () => {
        it('calls correct URL with query and category', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockCatalogResponse,
            });

            const params = {
                source: 'http://example.com',
                q: 'test',
                category: 'utilities',
                page: 2,
                page_size: 20,
            };
            await searchCatalog(params);

            const callUrl = mockFetch.mock.calls[0][0];
            expect(callUrl).toContain('q=test');
            expect(callUrl).toContain('category=utilities');
            expect(callUrl).toContain('page=2');
            expect(callUrl).toContain('page_size=20');
        });

        it('calls correct URL with optional source', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockCatalogResponse,
            });

            // @ts-ignore - testing optional source if we update types
            await searchCatalog({ q: 'test' });

            const callUrl = mockFetch.mock.calls[0][0];
            expect(callUrl).not.toContain('source=');
            expect(callUrl).toContain('q=test');
        });
    });

    describe('clearCatalogCache', () => {
        it('calls correct URL with DELETE method', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true }),
            });

            await clearCatalogCache();

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/catalog/cache'),
                expect.objectContaining({ method: 'DELETE' })
            );
        });

        it('includes source param if provided', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true }),
            });

            const source = 'http://example.com';
            await clearCatalogCache(source);

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining(`source=${encodeURIComponent(source)}`),
                expect.objectContaining({ method: 'DELETE' })
            );
        });
    });
});
