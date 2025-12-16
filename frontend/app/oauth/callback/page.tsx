'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { completeOAuthCallback, OAuthCallbackResult } from '@/lib/api/oauth';

type Status = 'processing' | 'success' | 'error';

type StoredPkce = {
  codeVerifier?: string;
  serverId?: string;
  returnUrl?: string;
};

function readStoredPkce(state: string): StoredPkce | null {
  const key = `oauth:pkce:${state}`;
  const storages: Storage[] = [];
  if (typeof window !== 'undefined') {
    storages.push(sessionStorage, localStorage);
  }
  for (const storage of storages) {
    try {
      const raw = storage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as StoredPkce;
      return parsed;
    } catch {
      // noop
    }
  }
  return null;
}

function clearStoredPkce(state: string) {
  if (typeof window === 'undefined') return;
  const key = `oauth:pkce:${state}`;
  try {
    sessionStorage.removeItem(key);
  } catch {
    // noop
  }
  try {
    localStorage.removeItem(key);
  } catch {
    // noop
  }
}

export default function OAuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<Status>('processing');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<OAuthCallbackResult | null>(null);

  useEffect(() => {
    if (!searchParams) return;
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const errorParam = searchParams.get('error');
    const serverIdParam = searchParams.get('server_id');

    if (errorParam) {
      setStatus('error');
      setErrorMessage(`認証が拒否されました: ${errorParam}`);
      return;
    }

    if (!code || !state) {
      setStatus('error');
      setErrorMessage('認証コードまたは state が見つかりません。もう一度認証を開始してください。');
      return;
    }

    const storedPkce = readStoredPkce(state);
    const codeVerifier = storedPkce?.codeVerifier;
    const serverId = serverIdParam ?? storedPkce?.serverId ?? undefined;
    const returnUrl = storedPkce?.returnUrl;

    const run = async () => {
      try {
        const response = await completeOAuthCallback({
          code,
          state,
          serverId,
          codeVerifier,
        });
        setResult(response);
        setStatus('success');
        clearStoredPkce(state);

        if (typeof window !== 'undefined' && window.opener && window.opener !== window) {
          try {
            window.opener.postMessage(
              { type: 'oauth:complete', state, result: response },
              window.location.origin
            );
          } catch {
            // noop
          }
          try {
            window.close();
          } catch {
            // noop
          }
          return;
        }

        const fallback = serverId ? `/catalog?server=${serverId}` : '/catalog';
        router.replace(returnUrl || fallback);
      } catch (err) {
        setStatus('error');
        setErrorMessage(
          err instanceof Error ? err.message : '認証処理に失敗しました。再度お試しください。'
        );
      }
    };

    run();
  }, [router, searchParams]);

  const statusMessage = useMemo(() => {
    if (status === 'processing') return '認証処理を完了しています...';
    if (status === 'success') return '認証が完了しました。まもなくリダイレクトします。';
    return errorMessage ?? '認証処理に失敗しました。';
  }, [errorMessage, status]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-lg rounded-lg bg-white shadow-md p-6 space-y-4 border border-gray-200">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">OAuth コールバック</h1>
          <p className="mt-1 text-sm text-gray-600">リモート MCP サーバーの認証結果を処理しています。</p>
        </div>

        <div className="rounded-md border border-gray-200 bg-gray-50 p-4 space-y-2">
          <p className="text-sm text-gray-800">{statusMessage}</p>
          {status === 'processing' && (
            <p className="text-xs text-gray-500">このタブを閉じずにお待ちください...</p>
          )}
          {status === 'success' && result?.server_id && (
            <p className="text-xs text-gray-600">対象サーバー: {result.server_id}</p>
          )}
          {status === 'error' && (
            <div className="space-y-2">
              <p className="text-sm text-red-700">問題が発生しました。再度認証を開始してください。</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => router.replace('/catalog')}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
                >
                  カタログへ戻る
                </button>
                <button
                  type="button"
                  onClick={() => router.replace('/dashboard')}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-800 shadow-sm hover:bg-gray-50"
                >
                  ダッシュボードへ戻る
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
