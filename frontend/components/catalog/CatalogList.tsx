'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import useSWR from 'swr';
import { CatalogItem } from '@/lib/types/catalog';
import { searchCatalog } from '@/lib/api/catalog';
import SearchBar from './SearchBar';
import CatalogCard from './CatalogCard'; // Changed import

const DEFAULT_PAGE_SIZE = 12;

interface CatalogListProps {
  catalogSource: string;
  onInstall: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem) => void;
}

export default function CatalogList({ catalogSource, onInstall, onSelect }: CatalogListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategory] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [catalogSource]);

  // SWR fetcher function
  const fetcher = useCallback(
    async (key: string) => {
      const [, source, query, category, pageValue, pageSizeValue] = key.split('|');
      const pageNumber = Number(pageValue) || 1;
      const pageSize = Number(pageSizeValue) || DEFAULT_PAGE_SIZE;
      return searchCatalog({
        source,
        q: query || undefined,
        category: category || undefined,
        page: pageNumber,
        page_size: pageSize,
      });
    },
    []
  );

  // Create cache key that includes search params
  const cacheKey = `catalog|${catalogSource}|${searchQuery}|${categoryFilter}|${page}|${DEFAULT_PAGE_SIZE}`;

  // Fetch catalog data with SWR
  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60000, // 1 minute
    }
  );

  useEffect(() => {
    if (data?.page && data.page !== page) {
      setPage(data.page);
    }
  }, [data?.page, page]);

  // Handle search
  const handleSearch = useCallback((query: string, category: string) => {
    setSearchQuery(query);
    setCategory(category);
    setPage(1);
  }, []);

  // Extract unique categories from data
  const categories = useMemo(() => {
    if (data?.categories?.length) {
      return data.categories;
    }
    if (!data?.servers) return [];
    const cats = new Set(data.servers.map(item => item.category));
    return Array.from(cats).sort();
  }, [data]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading catalog...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg
              className="h-5 w-5 text-red-400"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Failed to load catalog
            </h3>
            <p className="mt-1 text-sm text-red-700">
              {error.message || 'An error occurred while fetching the catalog.'}
            </p>
            <button
              onClick={() => mutate()}
              className="mt-2 text-sm font-medium text-red-800 hover:text-red-900 underline"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const servers = data?.servers || [];
  const isCached = data?.cached || false;
  const total = data?.total ?? 0;
  const pageSize = data?.page_size || DEFAULT_PAGE_SIZE;
  const currentPage = data?.page || page;
  const totalPages = Math.max(1, Math.ceil((total || 1) / pageSize));
  const visibleCount = servers.length;
  const start = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = total === 0 || visibleCount === 0 ? 0 : Math.min(total, start + visibleCount - 1);
  const canPrev = currentPage > 1;
  const canNext = currentPage < totalPages;

  return (
    <div className="space-y-6">
      {/* Cache indicator */}
      {isCached && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-sm text-blue-800">
            Showing cached data. Fresh data is being fetched in the background.
          </p>
        </div>
      )}

      {/* Search bar */}
      <SearchBar
        onSearch={handleSearch}
        categories={categories}
        initialQuery={searchQuery}
        initialCategory={categoryFilter}
      />

      {/* Results count & pagination */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-gray-700">
          {total === 0 ? (
            'No servers found'
          ) : (
            <>
              Showing <span className="font-medium">{start}</span>-
              <span className="font-medium">{end}</span> of{' '}
              <span className="font-medium">{total}</span> servers
            </>
          )}
        </p>

        <div className="flex items-center gap-3">
          {servers.length > 0 && (
            <button
              onClick={() => mutate()}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              disabled={!canPrev}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page <span className="font-medium">{currentPage}</span> / {totalPages}
            </span>
            <button
              onClick={() => setPage((prev) => prev + 1)}
              disabled={!canNext}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Server grid */}
      {servers.length === 0 ? (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            No servers found
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || categoryFilter
              ? 'Try adjusting your search or filters.'
              : 'The catalog appears to be empty.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {servers.map((item) => (
            <CatalogCard key={item.id} item={item} onInstall={onInstall} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}
