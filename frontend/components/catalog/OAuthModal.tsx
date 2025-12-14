'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import {
  collectScopes,
  exchangeOAuth,
  initiateOAuth,
  OAuthExchangeResult,
} from '@/lib/api/oauth';

interface OAuthModalProps {
  isOpen: boolean;
  item: CatalogItem | null;
  onClose: () => void;
}

type AuthState = {
  authUrl: string;
  state: string;
  codeVerifier: string;
  scopes: string[];
};

type CodeChallengeResult = {
  challenge: string;
  method: 'S256' | 'plain';
};

function isGitHubServerId(serverId: string): boolean {
  const value = (serverId || '').trim().toLowerCase();
  if (!value) return false;
  if (value.startsWith('https://github.com/')) return true;
  if (value.startsWith('http://github.com/')) return true;
  return value.includes('github.com/');
}

function inferGitHubOAuthEndpoints(
  serverId: string
): { authorizeUrl: string; tokenUrl: string } | null {
  if (!isGitHubServerId(serverId)) return null;
  return {
    authorizeUrl: 'https://github.com/login/oauth/authorize',
    tokenUrl: 'https://github.com/login/oauth/access_token',
  };
}

const base64UrlEncode = (buffer: ArrayBuffer) => {
  const bytes = new Uint8Array(buffer);
  let base64: string;
  if (typeof btoa === 'function') {
    base64 = btoa(String.fromCharCode(...bytes));
  } else {
    const message =
      'base64UrlEncode はブラウザ環境で btoa が必須です。サーバー側でエンコードする場合は Node.js コンテキストで実行してください。';
    throw new Error(message);
  }
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

function createCodeVerifier(): string {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return base64UrlEncode(array.buffer);
  }
  // crypto が利用できない場合は安全な verifier を生成できないためエラーをスローする
  throw new Error('Crypto API is required for secure OAuth flow');
}

async function toCodeChallenge(verifier: string): Promise<CodeChallengeResult> {
  try {
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      const data = new TextEncoder().encode(verifier);
      const digest = await crypto.subtle.digest('SHA-256', data);
      return { challenge: base64UrlEncode(digest), method: 'S256' };
    }
  } catch (err) {
    console.warn('PKCE challenge generation failed, falling back', err);
  }
  // フォールバック: verifier をそのまま返す（テスト環境向け）
  return { challenge: verifier, method: 'plain' };
}

export default function OAuthModal({ isOpen, item, onClose }: OAuthModalProps) {
  const [authState, setAuthState] = useState<AuthState | null>(null);
  const [codeInput, setCodeInput] = useState('');
  const [stateInput, setStateInput] = useState('');
  const [result, setResult] = useState<OAuthExchangeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const popupRef = useRef<Window | null>(null);

  const scopes = useMemo(() => (item ? collectScopes(item) : []), [item]);

  const previousItemIdRef = useRef<string | null>(null);

  useEffect(() => {
    const currentItemId = item?.id ?? null;
    const previousItemId = previousItemIdRef.current;

    // モーダルを閉じた場合はすべての状態をリセット
    if (!isOpen) {
      setAuthState(null);
      setResult(null);
      setCodeInput('');
      setStateInput('');
      setError(null);
      previousItemIdRef.current = null;
      return;
    }

    // 開いたまま対象アイテムが変わった場合も状態をリセット
    if (isOpen && currentItemId && previousItemId && currentItemId !== previousItemId) {
      setAuthState(null);
      setResult(null);
      setCodeInput('');
      setStateInput('');
      setError(null);
    }

    if (currentItemId) {
      previousItemIdRef.current = currentItemId;
    }
  }, [isOpen, item?.id]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (typeof window === 'undefined') return;
      if (!isOpen) return;
      if (event.origin !== window.location.origin) return;
      const data = event.data as any;
      if (!data || data.type !== 'oauth:complete') return;
      if (!authState || data.state !== authState.state) return;
      setResult(data.result as OAuthExchangeResult);
      setError(null);
      try {
        popupRef.current?.close();
      } catch {
        // noop
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [authState, isOpen]);

  if (!isOpen || !item) return null;

  const storePkce = (state: string, codeVerifier: string) => {
    try {
      // popup/window 間で共有するため localStorage を使用する
      localStorage.setItem(
        `oauth:pkce:${state}`,
        JSON.stringify({ codeVerifier, serverId: item.id, createdAt: Date.now() })
      );
    } catch {
      // noop
    }
  };

  const openAuthWindow = (url: string) => {
    // ポップアップがブロックされた場合は同一タブで遷移する
    const popup = window.open(url, 'oauth', 'width=520,height=720');
    popupRef.current = popup;
    if (!popup) {
      window.location.assign(url);
    }
  };

  const startAuth = async () => {
    try {
      setLoading(true);
      setError(null);
      const codeVerifier = createCodeVerifier();
      const { challenge, method } = await toCodeChallenge(codeVerifier);

      const redirectUri =
        item.oauth_redirect_uri ||
        (typeof window !== 'undefined' ? `${window.location.origin}/oauth/callback` : undefined);

      const inferred = inferGitHubOAuthEndpoints(item.id);
      const authorizeUrl = item.oauth_authorize_url ?? inferred?.authorizeUrl;
      const tokenUrl = item.oauth_token_url ?? inferred?.tokenUrl;

      const response = await initiateOAuth({
        serverId: item.id,
        scopes,
        authorizeUrl,
        tokenUrl,
        clientId: item.oauth_client_id,
        redirectUri,
        codeChallenge: challenge,
        codeChallengeMethod: method,
      });

      const nextAuth: AuthState = {
        authUrl: response.auth_url,
        state: response.state,
        codeVerifier,
        scopes: response.required_scopes || scopes,
      };
      setAuthState(nextAuth);
      setStateInput(response.state);
      setResult(null);
      storePkce(response.state, codeVerifier);
      openAuthWindow(response.auth_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : '認可の開始に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const exchangeCode = async () => {
    if (!authState) {
      setError('先に認可を開始してください');
      return;
    }
    if (!codeInput) {
      setError('認可コードを入力してください');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const response = await exchangeOAuth({
        code: codeInput,
        state: stateInput || authState.state,
        serverId: item.id,
        codeVerifier: authState.codeVerifier,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'トークン交換に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-3xl rounded-lg bg-white shadow-xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-gray-500">{item.name}</p>
              <h2 className="text-xl font-semibold text-gray-900">OAuth 認可</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              閉じる
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 p-6">
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-gray-200 p-4 space-y-2">
            <p className="text-sm font-semibold text-gray-900">要求スコープ</p>
            <p className="text-sm text-gray-700">
              {scopes.length > 0 ? scopes.join(', ') : 'なし'}
            </p>
          </div>

          <div className="flex gap-3 flex-wrap">
            <button
              type="button"
              onClick={startAuth}
              disabled={loading}
              className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
            >
              認可を開始
            </button>
          </div>

          {authState && (
            <div className="space-y-2 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
              <div className="font-semibold">認可 URL</div>
              <div className="break-all">{authState.authUrl}</div>
              <div>state: {authState.state}</div>
              <div className="text-xs text-blue-800">
                code_verifier はクライアントで保持されています。
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-800" htmlFor="code-input">
                認可コード
              </label>
              <input
                id="code-input"
                value={codeInput}
                onChange={(e) => setCodeInput(e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="provider から返却された code"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-800" htmlFor="state-input">
                state
              </label>
              <input
                id="state-input"
                value={stateInput}
                onChange={(e) => setStateInput(e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="認可開始時に保存した state"
              />
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={exchangeCode}
              disabled={loading}
              className="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-400"
            >
              コードを交換
            </button>
          </div>

          {result && (
            <div className="rounded border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-800 space-y-1">
              <div className="font-semibold">交換結果</div>
              <div>status: {result.status}</div>
              {result.credential_key && <div>credential_key: {result.credential_key}</div>}
              {result.expires_at && <div>expires_at: {result.expires_at}</div>}
              {result.scope?.length ? <div>scope: {result.scope.join(', ')}</div> : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
