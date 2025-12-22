// Catalog API client

import { CatalogResponse, CatalogSearchParams } from '../types/catalog';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

function getUrl(path: string): URL {
  if (API_BASE_URL) {
    return new URL(path, API_BASE_URL);
  }
  if (typeof window !== 'undefined') {
    return new URL(path, window.location.origin);
  }
  return new URL(path, 'http://127.0.0.1:3000');
}

export async function fetchCatalog(source?: string): Promise<CatalogResponse> {
  const url = getUrl('/api/catalog');
  if (source) {
    url.searchParams.append('source', source);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch catalog' }));
    console.error('Fetch catalog failed:', error, url.toString());
    throw new Error(error.detail || 'Failed to fetch catalog');
  }

  return response.json();
}

export async function searchCatalog(params: CatalogSearchParams): Promise<CatalogResponse> {
  const url = getUrl('/api/catalog/search');
  if (params.source) {
    url.searchParams.append('source', params.source);
  }

  if (params.q) {
    url.searchParams.append('q', params.q);
  }

  if (params.category) {
    url.searchParams.append('category', params.category);
  }

  if (typeof params.page === 'number') {
    url.searchParams.append('page', params.page.toString());
  }

  if (typeof params.page_size === 'number') {
    url.searchParams.append('page_size', params.page_size.toString());
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to search catalog' }));
    throw new Error(error.detail || 'Failed to search catalog');
  }

  return response.json();
}

export async function clearCatalogCache(source?: string): Promise<void> {
  const url = getUrl('/api/catalog/cache');

  if (source) {
    url.searchParams.append('source', source);
  }

  const response = await fetch(url.toString(), {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to clear cache' }));
    throw new Error(error.detail || 'Failed to clear cache');
  }
}
