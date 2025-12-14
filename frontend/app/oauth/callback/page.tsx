'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { exchangeOAuth } from '@/lib/api/oauth';
import type { OAuthExchangeResult } from '@/lib/api/oauth';

type Status = 'processing' | 'success' | 'error';

type StoredPKCE = {
  codeVerifier: string;
  serverId: string;
  createdAt: number;
};

const STORAGE_PREFIX = 'oauth:pkce:';
const STORAGE_TTL_MS = 15 * 60 * 1000;

function safeParseStored(value: string | null): StoredPKCE | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as Partial<StoredPKCE>;
    if (!parsed.codeVerifier || !parsed.serverId || !parsed.createdAt) return null;
    return parsed as StoredPKCE;
  } catch {
    return null;
  }
}

function OAuthCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<Status>('processing');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OAuthExchangeResult | null>(null);

  const code = params.get('code') || '';
  const state = params.get('state') || '';
  const providerError = params.get('error');
  const providerErrorDescription = params.get('error_description');

  const storageKey = useMemo(() => (state ? `${STORAGE_PREFIX}${state}` : ''), [state]);

  useEffect(() => {
    if (providerError) {
      setStatus('error');
      setError(providerErrorDescription || providerError);
      return;
    }

    if (!code || !state) {
      setStatus('error');
      setError('認可結果のパラメータ(code/state)が不足しています。');
      return;
    }

    const run = async () => {
      const stored = safeParseStored(localStorage.getItem(storageKey));
      if (!stored) {
        setStatus('error');
        setError('認可状態が見つかりません（stateが失効/不一致の可能性があります）。最初からやり直してください。');
        return;
      }

      if (Date.now() - stored.createdAt > STORAGE_TTL_MS) {
        localStorage.removeItem(storageKey);
        setStatus('error');
        setError('認可状態が期限切れです。最初からやり直してください。');
        return;
      }

      try {
        const exchange = await exchangeOAuth({
          code,
          state,
          serverId: stored.serverId,
          codeVerifier: stored.codeVerifier,
        });
        localStorage.removeItem(storageKey);
        setResult(exchange);
        setStatus('success');

        if (window.opener && !window.opener.closed) {
          window.opener.postMessage(
            { type: 'oauth:complete', state, result: exchange },
            window.location.origin
          );
          window.close();
          return;
        }

        // ポップアップが使えない場合は、少し待ってから戻す
        setTimeout(() => router.replace('/catalog'), 1200);
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'トークン交換に失敗しました。');
      }
    };

    void run();
  }, [code, providerError, providerErrorDescription, router, state, storageKey]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-lg border border-gray-200 bg-white shadow-sm p-6 space-y-3">
        <h1 className="text-lg font-semibold text-gray-900">OAuth 認証</h1>

        {status === 'processing' && (
          <div className="text-sm text-gray-700">
            認証を完了しています… この画面は自動で閉じます。
          </div>
        )}

        {status === 'success' && (
          <div className="text-sm text-green-700">
            認証が完了しました。アプリに戻ります…
            {result?.credential_key ? (
              <div className="mt-2 text-xs text-gray-600">
                credential_key: <span className="font-mono">{result.credential_key}</span>
              </div>
            ) : null}
          </div>
        )}

        {status === 'error' && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error || '認証に失敗しました。'}
          </div>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center p-6">
          <div className="w-full max-w-xl rounded-lg border border-gray-200 bg-white shadow-sm p-6 space-y-3">
            <h1 className="text-lg font-semibold text-gray-900">OAuth 認証</h1>
            <div className="text-sm text-gray-700">読み込み中...</div>
          </div>
        </div>
      }
    >
      <OAuthCallbackContent />
    </Suspense>
  );
}
