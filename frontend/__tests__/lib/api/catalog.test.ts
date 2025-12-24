import { fetchCatalog, searchCatalog, clearCatalogCache, CatalogError } from '../../../lib/api/catalog';
import { CatalogResponse, CatalogErrorCode } from '../../../lib/types/catalog';

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

        it('parses structured error response with error_code', async () => {
            const mockResponse = {
                ok: false,
                json: async () => ({
                    detail: 'Invalid source value. Allowed: docker, official',
                    error_code: 'invalid_source',
                }),
            };
            mockFetch.mockResolvedValueOnce(mockResponse);
            mockFetch.mockResolvedValueOnce(mockResponse);

            await expect(fetchCatalog('invalid')).rejects.toBeInstanceOf(CatalogError);
            await expect(fetchCatalog('invalid')).rejects.toMatchObject({
                message: 'Invalid source value. Allowed: docker, official',
                error_code: 'invalid_source',
                retry_after_seconds: undefined,
            });
        });

        it('parses rate_limited error with retry_after_seconds', async () => {
            const mockResponse = {
                ok: false,
                json: async () => ({
                    detail: 'Upstream rate limit exceeded. Please retry later.',
                    error_code: 'rate_limited',
                    retry_after_seconds: 60,
                }),
            };
            mockFetch.mockResolvedValueOnce(mockResponse);
            mockFetch.mockResolvedValueOnce(mockResponse);

            await expect(fetchCatalog('docker')).rejects.toBeInstanceOf(CatalogError);
            await expect(fetchCatalog('docker')).rejects.toMatchObject({
                message: 'Upstream rate limit exceeded. Please retry later.',
                error_code: 'rate_limited',
                retry_after_seconds: 60,
            });
        });

        it('parses upstream_unavailable error', async () => {
            const mockResponse = {
                ok: false,
                json: async () => ({
                    detail: 'Upstream registry is temporarily unavailable.',
                    error_code: 'upstream_unavailable',
                }),
            };
            mockFetch.mockResolvedValueOnce(mockResponse);
            mockFetch.mockResolvedValueOnce(mockResponse);

            await expect(fetchCatalog('official')).rejects.toBeInstanceOf(CatalogError);
            await expect(fetchCatalog('official')).rejects.toMatchObject({
                error_code: 'upstream_unavailable',
            });
        });

        it('handles malformed error response gracefully', async () => {
            const mockResponse = {
                ok: false,
                json: async () => { throw new Error('JSON parse error'); },
            };
            mockFetch.mockResolvedValueOnce(mockResponse);
            mockFetch.mockResolvedValueOnce(mockResponse);

            await expect(fetchCatalog()).rejects.toBeInstanceOf(CatalogError);
            await expect(fetchCatalog()).rejects.toMatchObject({
                message: 'Failed to fetch catalog',
                error_code: undefined,
            });
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
