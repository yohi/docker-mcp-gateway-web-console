// Catalog API client

import { CatalogResponse, CatalogSearchParams } from '../types/catalog';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchCatalog(source: string): Promise<CatalogResponse> {
  const url = new URL(`${API_BASE_URL}/api/catalog`);
  url.searchParams.append('source', source);

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch catalog' }));
    throw new Error(error.detail || 'Failed to fetch catalog');
  }

  return response.json();
}

export async function searchCatalog(params: CatalogSearchParams): Promise<CatalogResponse> {
  const url = new URL(`${API_BASE_URL}/api/catalog/search`);
  url.searchParams.append('source', params.source);
  
  if (params.q) {
    url.searchParams.append('q', params.q);
  }
  
  if (params.category) {
    url.searchParams.append('category', params.category);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to search catalog' }));
    throw new Error(error.detail || 'Failed to search catalog');
  }

  return response.json();
}

export async function clearCatalogCache(source?: string): Promise<void> {
  const url = new URL(`${API_BASE_URL}/api/catalog/cache`);
  
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
