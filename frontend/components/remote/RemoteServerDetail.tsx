'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import {
  fetchRemoteServerById,
  startRemoteOAuth,
  testRemoteServer,
} from '@/lib/api/remoteServers';
import { RemoteServer, RemoteServerStatus, RemoteTestResult } from '@/lib/types/remote';
import { createPkcePair } from '@/lib/utils/pkce';

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

type Props = {
  serverId: string;
};

export default function RemoteServerDetail({ serverId }: Props) {
  const { data, error, isLoading, mutate, isValidating } = useSWR<RemoteServer>(
    serverId ? `remote-servers/${serverId}` : null,
    () => fetchRemoteServerById(serverId),
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    }
  );

  const [actionError, setActionError] = useState<string | null>(null);
  const [isStartingAuth, setIsStartingAuth] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<RemoteTestResult | null>(null);

  const badge = useMemo(() => (data ? getBadge(data.status) : null), [data]);

  async function handleStartAuth() {
    if (!data) return;
    setActionError(null);
    setIsStartingAuth(true);
    try {
      const pkce = await createPkcePair();
      const start = await startRemoteOAuth({
        serverId: data.server_id,
        codeChallenge: pkce.codeChallenge,
      });

      const storageKey = `oauth:pkce:${start.state}`;
      const payload = JSON.stringify({
        codeVerifier: pkce.codeVerifier,
        serverId: data.server_id,
        createdAt: Date.now(),
        returnUrl: window.location.href,
      });

      try {
        sessionStorage.setItem(storageKey, payload);
      } catch (err) {
        throw new Error(
          err instanceof Error
            ? `ブラウザストレージへの保存に失敗しました: ${err.message}`
            : 'ブラウザストレージへの保存に失敗しました'
        );
      }

      const testRedirect = (window as any).__oauthRedirect;
      if (typeof testRedirect === 'function') {
        testRedirect(start.auth_url);
      } else {
        window.location.assign(start.auth_url);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '認証開始に失敗しました');
    } finally {
      setIsStartingAuth(false);
    }
  }

  async function handleTestConnection() {
    if (!data) return;
    setActionError(null);
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testRemoteServer(data.server_id);
      setTestResult(result);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '接続テストに失敗しました');
    } finally {
      setIsTesting(false);
    }
  }

  if (!data && isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <p className="text-sm text-gray-600">詳細を取得中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-2">
        <p className="text-sm font-semibold text-red-800">
          リモートサーバーの取得に失敗しました
        </p>
        <p className="text-sm text-red-700">{error.message}</p>
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

  if (!data) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">{data.name}</h2>
            {badge ? (
              <span
                className={`text-xs font-semibold px-2 py-1 rounded-full ${badge.className}`}
              >
                {badge.label}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-gray-600 break-all">{data.endpoint}</p>
          <p className="text-xs text-gray-500">catalog_item_id: {data.catalog_item_id}</p>
          {data.credential_key && (
            <p className="text-xs text-gray-500">
              credential_key: <span className="font-mono">{data.credential_key}</span>
            </p>
          )}
          {data.error_message && (
            <p className="text-xs text-red-600">エラー: {data.error_message}</p>
          )}
        </div>
        <div className="text-xs text-gray-500 text-right space-y-1">
          <p>ID: {data.server_id}</p>
          <p>
            最終接続:{' '}
            {data.last_connected_at ? new Date(data.last_connected_at).toLocaleString() : '未接続'}
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-2 md:flex-row">
          <button
            type="button"
            onClick={handleStartAuth}
            disabled={isStartingAuth || isValidating}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-60"
          >
            {isStartingAuth ? '開始中...' : '認証開始'}
          </button>
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isTesting || isValidating}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-800 shadow-sm hover:bg-gray-50 disabled:opacity-60"
          >
            {isTesting ? 'テスト中...' : '接続テスト'}
          </button>
          <button
            type="button"
            onClick={() => mutate()}
            disabled={isValidating}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-800 shadow-sm hover:bg-gray-50 disabled:opacity-60"
          >
            {isValidating ? '更新中...' : '再読み込み'}
          </button>
        </div>
      </div>

      {actionError && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {actionError}
        </div>
      )}

      {testResult && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm space-y-2">
          <h3 className="text-sm font-semibold text-gray-900">接続テスト結果</h3>
          <p className="text-sm text-gray-700">
            到達性: {testResult.reachable ? 'OK' : 'NG'}
          </p>
          <p className="text-sm text-gray-700">
            認証: {testResult.authenticated ? '認証済み' : '未認証'}
          </p>
          {testResult.error && (
            <p className="text-xs text-red-600">エラー: {testResult.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
