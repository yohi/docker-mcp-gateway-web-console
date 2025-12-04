'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import ProtectedRoute from '../../components/auth/ProtectedRoute';
import LogoutButton from '../../components/auth/LogoutButton';
import ContainerList from '../../components/containers/ContainerList';
import ContainerConfigurator from '../../components/containers/ContainerConfigurator';
import LogViewer from '../../components/containers/LogViewer';
import { useSession } from '../../contexts/SessionContext';
import { fetchContainers } from '../../lib/api/containers';
import Link from 'next/link';

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
      <main className="flex min-h-screen flex-col p-8 bg-gray-50">
        <div className="max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-gray-800">ダッシュボード</h1>
              <p className="text-gray-600 mt-2">
                ログイン中: {session?.user_email}
              </p>
            </div>
            <LogoutButton />
          </div>

          {/* Navigation */}
          <div className="mb-6 flex gap-4">
            <Link
              href="/catalog"
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
            >
              Catalogを見る
            </Link>
            <button
              onClick={() => setShowConfigurator(true)}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium transition-colors"
            >
              新規コンテナを作成
            </button>
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              {isLoading ? '読み込み中...' : '更新'}
            </button>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-50 text-red-700 px-6 py-4 rounded-lg mb-6 border border-red-200">
              <p className="font-semibold">エラー:</p>
              <p className="text-sm">{error.message}</p>
            </div>
          )}

          {/* Container list */}
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-800">
                コンテナ一覧
                {!isLoading && (
                  <span className="ml-3 text-lg font-normal text-gray-600">
                    ({containers.length}個)
                  </span>
                )}
              </h2>
            </div>

            {isLoading ? (
              <div className="bg-white shadow-md rounded-lg p-8 text-center">
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
      </main>
    </ProtectedRoute>
  );
}
