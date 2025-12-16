'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { fetchRemoteServers } from '@/lib/api/remoteServers';
import { RemoteServer, RemoteServerStatus } from '@/lib/types/remote';

const STATUS_LABELS: Record<RemoteServerStatus, string> = {
  [RemoteServerStatus.UNREGISTERED]: '未登録',
  [RemoteServerStatus.REGISTERED]: '登録済み',
  [RemoteServerStatus.AUTH_REQUIRED]: '要認証',
  [RemoteServerStatus.AUTHENTICATED]: '認証済み',
  [RemoteServerStatus.DISABLED]: '無効',
  [RemoteServerStatus.ERROR]: 'エラー',
};

const STATUS_CLASSES: Record<RemoteServerStatus, string> = {
  [RemoteServerStatus.UNREGISTERED]: 'bg-gray-100 text-gray-700 border border-gray-200',
  [RemoteServerStatus.REGISTERED]: 'bg-blue-50 text-blue-700 border border-blue-200',
  [RemoteServerStatus.AUTH_REQUIRED]: 'bg-amber-50 text-amber-800 border border-amber-200',
  [RemoteServerStatus.AUTHENTICATED]: 'bg-green-50 text-green-700 border border-green-200',
  [RemoteServerStatus.DISABLED]: 'bg-slate-100 text-slate-700 border border-slate-200',
  [RemoteServerStatus.ERROR]: 'bg-red-50 text-red-700 border border-red-200',
};

function getBadge(status: RemoteServerStatus) {
  return {
    label: STATUS_LABELS[status] ?? status,
    className: STATUS_CLASSES[status] ?? 'bg-gray-100 text-gray-700 border border-gray-200',
  };
}

export default function RemoteServerList() {
  const { data, error, isLoading, mutate, isValidating } = useSWR<RemoteServer[]>(
    'remote-servers',
    fetchRemoteServers,
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    }
  );
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | RemoteServerStatus>('all');

  const filteredServers = useMemo(() => {
    const lower = searchTerm.trim().toLowerCase();
    return (data || []).filter((server) => {
      const matchesSearch =
        !lower ||
        server.name.toLowerCase().includes(lower) ||
        server.endpoint.toLowerCase().includes(lower);
      const matchesStatus = statusFilter === 'all' || server.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data, searchTerm, statusFilter]);

  if (!data && isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-gray-600">リモートサーバーを読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-2">
        <p className="text-sm font-semibold text-red-800">
          リモートサーバー一覧の取得に失敗しました
        </p>
        <p className="text-sm text-red-700" data-testid="error-message">
          {error.message}
        </p>
        <button
          type="button"
          onClick={() => mutate()}
          className="text-sm text-red-800 underline font-medium"
        >
          再試行
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="w-full md:w-1/2">
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="remote-search">
            サーバー検索
          </label>
          <input
            id="remote-search"
            data-testid="remote-search"
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="名前やエンドポイントで絞り込み"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          />
        </div>
        <div className="flex items-end gap-3">
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1" htmlFor="status-filter">
              ステータス
            </label>
            <select
              id="status-filter"
              data-testid="status-filter"
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter((e.target.value as RemoteServerStatus | 'all') || 'all')
              }
              className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            >
              <option value="all">すべて</option>
              {Object.values(RemoteServerStatus).map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => mutate()}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60"
            disabled={isValidating}
          >
            {isValidating ? '更新中...' : '再読み込み'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>表示件数: {filteredServers.length}</span>
        {isValidating && <span className="text-blue-600">同期中...</span>}
      </div>

      {filteredServers.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center">
          <p className="text-sm font-medium text-gray-800">該当するサーバーがありません</p>
          <p className="text-xs text-gray-600 mt-1">検索条件を変更してください。</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {filteredServers.map((server) => {
            const badge = getBadge(server.status);
            return (
              <li
                key={server.server_id}
                data-testid="remote-server-row"
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-900">{server.name}</p>
                      <span
                        data-testid="status-badge"
                        className={`text-xs font-semibold px-2 py-1 rounded-full ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 break-all">{server.endpoint}</p>
                    {server.error_message && (
                      <p className="text-xs text-red-600">エラー: {server.error_message}</p>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 text-right">
                    <p>ID: {server.server_id}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
