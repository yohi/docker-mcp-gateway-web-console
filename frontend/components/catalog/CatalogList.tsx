'use client';

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import useSWR from 'swr';
import { CatalogItem } from '@/lib/types/catalog';
import { searchCatalog } from '@/lib/api/catalog';
import { CatalogSourceId } from '@/lib/constants/catalogSources';
import SearchBar from './SearchBar';
import CatalogCard from './CatalogCard'; // Changed import
import CatalogRow from './CatalogRow';
import { useContainers } from '@/hooks/useContainers';
import { fetchRemoteServers } from '@/lib/api/remoteServers';
import { RemoteServer } from '@/lib/types/remote';

const DEFAULT_PAGE_SIZE = 8;
const BACKEND_PAGE_SIZE = 8;

interface CatalogListProps {
  catalogSource: CatalogSourceId;
  onInstall: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem) => void;
  warning?: string;
}

export default function CatalogList({ catalogSource, warning, onInstall, onSelect }: CatalogListProps) {
  const { containers, refresh: refreshContainers, isLoading: isContainersLoading } = useContainers(0); // no polling
  const { data: remoteServers } = useSWR<RemoteServer[]>('remote-servers-catalog', fetchRemoteServers, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [cachedData, setCachedData] = useState<any>(null);
  const [combinedServers, setCombinedServers] = useState<CatalogItem[]>([]);
  const [combinedTotal, setCombinedTotal] = useState(0);

  useEffect(() => {
    setPage(1);
    setCombinedServers([]);
    setCombinedTotal(0);
  }, [catalogSource, searchQuery, categoryFilter]);

  // SWR fetcher function
  const fetcher = useCallback(
    async (key: string) => {
      const [, source, query, category, pageValue, pageSizeValue] = key.split('|');
      const pageNumber = Number(pageValue) || 1;
      const pageSize = Number(pageSizeValue) || BACKEND_PAGE_SIZE;
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
  const cacheKey = `catalog|${catalogSource}|${searchQuery}|${categoryFilter}|${page}|${BACKEND_PAGE_SIZE}`;

  // Fetch catalog data with SWR
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    cacheKey,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60000, // 1 minute
      keepPreviousData: true, // 入力中の再フェッチでコンポーネントがリセットされるのを防ぐ
    }
  );

  useEffect(() => {
    if (data) {
      setCachedData(data);
    }
  }, [data]);

  useEffect(() => {
    const active = data || cachedData;
    if (!active) return;
    if (page === 1) {
      setCombinedServers(active.servers || []);
    } else if (Array.isArray(active.servers)) {
      setCombinedServers((prev) => {
        const existingIds = new Set(prev.map((s) => s.id));
        const merged = [...prev];
        active.servers.forEach((s: CatalogItem) => {
          if (!existingIds.has(s.id)) merged.push(s);
        });
        return merged;
      });
    }
    setCombinedTotal(active.total ?? 0);
  }, [data, cachedData, page]);

  const canLoadMore = combinedServers.length < (combinedTotal || 0);
  const isLoadingMore = isValidating && page > 1;
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const loadingTriggerRef = useRef(false);

  // Handle search
  const handleSearch = useCallback((query: string, category: string) => {
    setSearchQuery(query);
    setCategory(category);
    setPage(1);
  }, []);

  // Intersection-based incremental loading
  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (
            entry.isIntersecting &&
            canLoadMore &&
            !isLoading &&
            !isValidating &&
            !loadingTriggerRef.current
          ) {
            loadingTriggerRef.current = true;
            setPage((prev) => prev + 1);
          }
        });
      },
      { rootMargin: '200px' }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [canLoadMore, isLoading, isValidating]);

  useEffect(() => {
    if (!isValidating) {
      loadingTriggerRef.current = false;
    }
  }, [isValidating]);

  // Extract unique categories from data
  const categories = useMemo(() => {
    if (data?.categories?.length) {
      return data.categories;
    }
    if (!data?.servers) return [];
    const cats = new Set(data.servers.map(item => item.category));
    return Array.from(cats).sort();
  }, [data]);

  // Map remote servers by catalog_item_id
  const remoteStatusByCatalogId = useMemo(() => {
    const map = new Map<string, RemoteServer>();
    (remoteServers || []).forEach((srv: RemoteServer) => {
      if (srv.catalog_item_id) {
        map.set(srv.catalog_item_id, srv);
      }
    });
    return map;
  }, [remoteServers]);

  const activeData = data || cachedData;
  const loadError = error as Error | undefined;
  const usingFallbackCache = !!loadError && !!cachedData && !data;

  // Loading state (initial only)
  if (!activeData && isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading catalog...</p>
        </div>
      </div>
    );
  }

  // Error state without any cached data to show
  if (loadError && !activeData) {
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
              {loadError.message || 'An error occurred while fetching the catalog.'}
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

  const servers = combinedServers;
  const isCached = activeData?.cached || false;
  const warningMessage = usingFallbackCache
    ? `最新のカタログ取得に失敗しましたが、最後に成功したカタログを表示しています。`
    : (warning || activeData?.warning);
  const total = combinedTotal || activeData?.total || 0;
  const pageSize = activeData?.page_size || DEFAULT_PAGE_SIZE;
  const currentPage = page;
  const totalPages = Math.max(1, Math.ceil((total || 1) / pageSize));
  const visibleCount = servers.length;
  const canPrev = currentPage > 1;
  const canNext = combinedServers.length < total;

  return (
    <div className="space-y-6">
      {/* Error fallback notice when using cached data */}
      {usingFallbackCache && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="flex items-start gap-3">
            <svg
              className="h-5 w-5 text-red-400 mt-0.5"
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
            <div className="space-y-1">
              <p className="text-sm font-semibold text-red-800">最新のカタログ取得に失敗しました</p>
              <p className="text-sm text-red-700">{loadError?.message || 'ネットワークエラーが発生しました。'}</p>
              <button
                onClick={() => mutate()}
                className="text-sm font-medium text-red-800 hover:text-red-900 underline"
              >
                再試行
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Warning */}
      {warningMessage && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex gap-3">
          <div className="mt-1 h-2.5 w-2.5 rounded-full bg-yellow-500" />
          <div>
            <p className="text-sm text-yellow-800 font-semibold">警告</p>
            <p className="text-sm text-yellow-800 mt-1">{warningMessage}</p>
          </div>
        </div>
      )}

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

      {/* Loading indicator (non-blocking) */}
      {isValidating && (
        <div className="text-sm text-gray-500">更新中...</div>
      )}

      {/* Results count & pagination */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-gray-700">
          {total === 0
            ? 'No servers found'
            : `読み込み済み ${visibleCount}/${total} 件`}
        </p>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-100 rounded-md px-2 py-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`px-2 py-1 text-sm rounded ${viewMode === 'grid' ? 'bg-white shadow-sm font-semibold' : 'text-gray-600'}`}
            >
              グリッド
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-2 py-1 text-sm rounded ${viewMode === 'list' ? 'bg-white shadow-sm font-semibold' : 'text-gray-600'}`}
            >
              リスト
            </button>
          </div>
          {servers.length > 0 && (
            <button
              onClick={() => mutate()}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          )}
          <div className="text-sm text-gray-600">
            Page <span className="font-medium">{currentPage}</span> / {totalPages}
          </div>
        </div>
      </div>

      {/* Server list / grid */}
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
        viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {servers.map((item) => (
              <CatalogCard
                key={item.id}
                item={item}
                containers={containers}
                isContainersLoading={isContainersLoading}
                onContainersRefresh={refreshContainers}
                remoteServer={remoteStatusByCatalogId.get(item.id)}
                onInstall={onInstall}
                onSelect={onSelect}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {servers.map((item) => (
              <CatalogRow
                key={item.id}
                item={item}
                containers={containers}
                isContainersLoading={isContainersLoading}
                onContainersRefresh={refreshContainers}
                remoteServer={remoteStatusByCatalogId.get(item.id)}
                onInstall={onInstall}
                onSelect={onSelect}
              />
            ))}
          </div>
        )
      )}
      <div
        ref={loadMoreRef}
        className="h-12 flex items-center justify-center text-sm text-gray-500"
      >
        {canNext ? (isLoadingMore ? '読み込み中...' : 'スクロールで追加読み込み') : 'すべて読み込みました'}
      </div>
    </div>
  );
}
