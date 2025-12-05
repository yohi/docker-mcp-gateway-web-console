'use client';

import { useState } from 'react';
import useSWR from 'swr';
import ProtectedRoute from '../../components/auth/ProtectedRoute';
import { MainLayout } from '../../components/layout';
import ContainerList from '../../components/containers/ContainerList';
import ContainerConfigurator from '../../components/containers/ContainerConfigurator';
import LogViewer from '../../components/containers/LogViewer';
import { useSession } from '../../contexts/SessionContext';
import { fetchContainers } from '../../lib/api/containers';

export default function DashboardPage() {
  const { session } = useSession();
  const [showConfigurator, setShowConfigurator] = useState(false);
  const [viewingLogsFor, setViewingLogsFor] = useState<string | null>(null);

  // Fetch containers with SWR for automatic revalidation
  const { data, error, mutate } = useSWR(
    session ? 'containers' : null,
    () => fetchContainers(true),
    {
      refreshInterval: 5000, // Auto-refresh every 5 seconds (requirement 9.2)
      revalidateOnFocus: true,
    }
  );

  const containers = data?.containers || [];
  const isLoading = !data && !error;

  const handleRefresh = () => {
    mutate();
  };

  const handleCreateSuccess = () => {
    setShowConfigurator(false);
    mutate();
  };

  return (
    <ProtectedRoute>
      <MainLayout>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">ダッシュボード</h1>
            <p className="text-gray-600 mt-2">
              MCPサーバーコンテナを管理します
            </p>
          </div>

          {/* Action buttons */}
          <div className="mb-6 flex flex-wrap gap-3">
            <button
              onClick={() => setShowConfigurator(true)}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              新規コンテナを作成
            </button>
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {isLoading ? '読み込み中...' : '更新'}
            </button>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-50 text-red-700 px-4 py-3 rounded-md mb-6 border border-red-200">
              <p className="font-semibold">エラー:</p>
              <p className="text-sm">{error.message}</p>
            </div>
          )}

          {/* Container list */}
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                コンテナ一覧
                {!isLoading && (
                  <span className="ml-3 text-base font-normal text-gray-600">
                    ({containers.length}個)
                  </span>
                )}
              </h2>
            </div>

            {isLoading ? (
              <div className="bg-white shadow-sm rounded-lg p-8 text-center border border-gray-200">
                <div className="animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-1/4 mx-auto mb-4"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2 mx-auto"></div>
                </div>
              </div>
            ) : (
              <ContainerList
                containers={containers}
                onRefresh={handleRefresh}
                onViewLogs={setViewingLogsFor}
              />
            )}
          </div>
        </div>

        {/* Modals */}
        {showConfigurator && (
          <ContainerConfigurator
            onSuccess={handleCreateSuccess}
            onCancel={() => setShowConfigurator(false)}
          />
        )}

        {viewingLogsFor && (
          <LogViewer
            containerId={viewingLogsFor}
            onClose={() => setViewingLogsFor(null)}
          />
        )}
      </MainLayout>
    </ProtectedRoute>
  );
}
