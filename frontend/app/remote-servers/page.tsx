'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import RemoteServerList from '@/components/remote/RemoteServerList';
import RemoteServerDetail from '@/components/remote/RemoteServerDetail';

export default function RemoteServersPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <ProtectedRoute>
      <MainLayout>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">リモートサーバー</h1>
              <p className="text-gray-600 mt-2">登録済みリモート MCP サーバーの一覧と詳細</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="lg:border-r lg:pr-6">
              <RemoteServerList onSelect={(server) => setSelectedId(server.server_id)} />
            </div>
            <div className="lg:pl-6">
              {selectedId ? (
                <RemoteServerDetail serverId={selectedId} />
              ) : (
                <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center">
                  <p className="text-sm font-medium text-gray-800">サーバーを選択してください</p>
                  <p className="text-xs text-gray-600 mt-1">一覧からサーバーをクリックすると詳細が表示されます。</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </MainLayout>
    </ProtectedRoute>
  );
}
