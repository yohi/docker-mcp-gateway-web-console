'use client';

import { useMemo } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import { useContainers } from '@/hooks/useContainers';
import { matchCatalogItemContainer } from '@/lib/utils/containerMatch';
import { isRemoteCatalogItem, getRemoteEndpoint } from '@/lib/utils/catalogUtils';
import SessionExecutionPanel from './SessionExecutionPanel';

interface CatalogDetailModalProps {
  isOpen: boolean;
  item: CatalogItem | null;
  onClose: () => void;
  onInstall: (item: CatalogItem) => void;
  onOAuth?: (item: CatalogItem) => void;
}

export default function CatalogDetailModal({
  isOpen,
  item,
  onClose,
  onInstall,
  onOAuth,
}: CatalogDetailModalProps) {
  const isRemote = item ? isRemoteCatalogItem(item) : false;
  const { containers, isLoading } = useContainers();

  const status = useMemo<'loading' | 'running' | 'installed' | 'not_installed'>(() => {
    if (isLoading) return 'loading';
    if (!item) return 'not_installed';
    const container = containers.find((c) => matchCatalogItemContainer(item, c));
    if (container) {
      if (container.status === 'running') return 'running';
      return 'installed';
    }
    return 'not_installed';
  }, [containers, isLoading, item]);

  if (!isOpen || !item) {
    return null;
  }

  const envEntries = Object.entries(item.default_env || {});

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              {item.icon_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={item.icon_url}
                  alt={`${item.name} icon`}
                  className="h-12 w-12 rounded-md border border-gray-200 bg-white object-cover"
                />
              ) : (
                <div className="flex h-12 w-12 items-center justify-center rounded-md border border-gray-200 bg-gray-100 text-base font-semibold text-gray-600">
                  {item.name.slice(0, 2).toUpperCase()}
                </div>
              )}
              <div>
                <p className="text-sm text-gray-500">{item.vendor || '提供元未指定'}</p>
                <h2 className="text-xl font-semibold text-gray-900">{item.name}</h2>
                <div className="mt-2">
                  {status === 'loading' ? (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">
                      インストール状態を取得中...
                    </span>
                  ) : status === 'running' ? (
                    <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-800">
                      実行中 (インストール済み)
                    </span>
                  ) : status === 'installed' ? (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-800">
                      インストール済み (停止中)
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                      未インストール
                    </span>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap gap-2">
                  <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                    {item.category}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      isRemote ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {isRemote ? 'リモート' : 'Docker'}
                  </span>
                  {item.required_secrets.length > 0 && (
                    <span className="inline-flex items-center rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-800">
                      シークレットが必要
                    </span>
                  )}
                  {item.verify_signatures === false ? (
                    <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">
                      署名検証無効
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                      署名検証有効
                    </span>
                  )}
                  {item.allowlist_status && (
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        item.allowlist_status === 'allowed'
                          ? 'bg-green-100 text-green-800'
                          : item.allowlist_status === 'pending'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-red-100 text-red-800'
                      }`}
                    >
                      allowlist: {item.allowlist_status}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="詳細を閉じる"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <div>
            <h3 className="text-sm font-medium text-gray-900">説明</h3>
            <p className="mt-2 whitespace-pre-line text-sm text-gray-700">{item.description}</p>
          </div>

          {item.verify_signatures === false && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              <p className="font-semibold">リスク警告</p>
              <p className="mt-1">
                署名検証が無効化されています。署名未検証のイメージが許可される可能性があります。
              </p>
            </div>
          )}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-xs font-medium text-gray-500">
                {isRemote ? 'リモートエンドポイント' : 'Dockerイメージ'}
              </p>
              <p className="mt-1 font-mono text-sm text-gray-900 break-words">
                {isRemote ? getRemoteEndpoint(item) || '未設定' : item.docker_image || '未設定'}
              </p>
            </div>

            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-xs font-medium text-gray-500">提供元</p>
              <p className="mt-1 text-sm text-gray-900">{item.vendor || '提供元未指定'}</p>
              <p className="mt-3 text-xs font-medium text-gray-500">カテゴリー</p>
              <p className="mt-1 text-sm text-gray-900">{item.category}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">必須環境変数</p>
              {item.required_envs.length === 0 ? (
                <p className="mt-1 text-sm text-gray-600">必須の環境変数はありません。</p>
              ) : (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-gray-700">
                  {item.required_envs.map((key) => (
                    <li key={key}>{key}</li>
                  ))}
                </ul>
              )}

              {item.required_secrets.length > 0 && (
                <div className="mt-3 rounded-md bg-yellow-50 p-3 text-sm text-yellow-800">
                  <p className="font-medium">シークレットが必要</p>
                  <p className="mt-1">
                    {item.required_secrets.join(', ')}
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">デフォルト環境変数</p>
              {envEntries.length === 0 ? (
                <p className="mt-1 text-sm text-gray-600">デフォルトの環境変数はありません。</p>
              ) : (
                <div className="mt-2 space-y-2">
                  {envEntries.map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm"
                    >
                      <p className="font-medium text-gray-900">{key}</p>
                      <p className="mt-1 break-words font-mono text-xs text-gray-700">{value}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4 space-y-2">
              <p className="text-sm font-semibold text-gray-900">要求スコープ</p>
              <p className="text-sm text-gray-700">
                {item.required_scopes?.length ? item.required_scopes.join(', ') : 'なし'}
              </p>
              {item.allowlist_hint && (
                <div className="rounded bg-blue-50 px-3 py-2 text-sm text-blue-800">
                  <p className="font-semibold">Allowlist ヒント</p>
                  <p className="mt-1">{item.allowlist_hint}</p>
                </div>
              )}
            </div>
            <div className="rounded-lg border border-gray-200 p-4 space-y-2">
              <p className="text-sm font-semibold text-gray-900">署名検証</p>
              <p className="text-sm text-gray-700">
                {item.verify_signatures === false ? '無効' : '有効'}
              </p>
              {item.jwks_url && (
                <p className="text-xs text-gray-600 break-all">
                  JWKS: <span className="font-mono">{item.jwks_url}</span>
                </p>
              )}
              {item.permit_unsigned && item.permit_unsigned.length > 0 && (
                <div className="rounded bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
                  <p className="font-semibold">未署名許可条件</p>
                  <p className="mt-1 break-words">{item.permit_unsigned.join(', ')}</p>
                </div>
              )}
            </div>
          </div>

          {!isRemote && (
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">Session/Execution パネル</p>
              <p className="text-xs text-gray-600 mb-3">
                ゲートウェイ状態を確認し、mcp-exec を同期/非同期で実行できます。
              </p>
              <SessionExecutionPanel
                serverId={item.id}
                image={item.docker_image}
                defaultEnv={item.default_env}
              />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4">
          {onOAuth && (
            <button
              type="button"
              onClick={() => onOAuth(item)}
              className="rounded bg-indigo-600 px-4 py-2 text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:bg-indigo-400"
            >
              OAuth接続
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-500 px-4 py-2 text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            閉じる
          </button>
          <button
            type="button"
            onClick={() => onInstall(item)}
            disabled={status !== 'not_installed' || isRemote}
            className="rounded bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-blue-400"
          >
            {isRemote
              ? 'リモートサーバー（インストール対象外）'
              : status === 'running'
                ? '実行中 (インストール済み)'
                : status === 'installed'
                  ? 'インストール済み'
                  : status === 'loading'
                    ? '判定中...'
                    : 'インストール'}
          </button>
        </div>
      </div>
    </div>
  );
}
