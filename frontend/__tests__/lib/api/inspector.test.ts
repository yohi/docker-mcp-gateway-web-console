import { fetchTools, fetchResources, fetchPrompts, fetchCapabilities } from '../../../lib/api/inspector';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
const mockGetItem = jest.fn();
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: mockGetItem,
  },
  writable: true,
});

describe('Inspector API', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockGetItem.mockClear();
    mockGetItem.mockReturnValue('test-session-id');
  });

  it('fetchTools calls correct URL and returns data', async () => {
    const mockData = [{ name: 'tool1' }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const result = await fetchTools('container-1');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/inspector/container-1/tools'),
      expect.objectContaining({
        headers: { 'X-Session-ID': 'test-session-id' },
      })
    );
    expect(result).toEqual(mockData);
  });

  it('fetchTools throws error on failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Error message' }),
    });

    await expect(fetchTools('container-1')).rejects.toThrow('Error message');
  });

  it('fetchTools throws default error on failure without detail', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });

    // The default error message for fetchTools is 'Failed to fetch tools'
    await expect(fetchTools('container-1')).rejects.toThrow('Failed to fetch tools');
  });

  it('fetchResources calls correct URL', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    await fetchResources('container-1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/inspector/container-1/resources'),
      expect.any(Object)
    );
  });

  it('fetchPrompts calls correct URL', async () => {
    mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
    });

    await fetchPrompts('container-1');
    expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/inspector/container-1/prompts'),
        expect.any(Object)
    );
  });

  it('fetchCapabilities calls correct URL', async () => {
    mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
    });

    await fetchCapabilities('container-1');
    expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/inspector/container-1/capabilities'),
        expect.any(Object)
    );
  });

  it('throws error if containerId is missing', async () => {
      await expect(fetchTools('')).rejects.toThrow('Invalid containerId');
  });
});
