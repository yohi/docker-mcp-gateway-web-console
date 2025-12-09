'use client';

import { CatalogItem } from '@/lib/types/catalog';

interface CatalogDetailModalProps {
  isOpen: boolean;
  item: CatalogItem | null;
  onClose: () => void;
  onInstall: (item: CatalogItem) => void;
}

export default function CatalogDetailModal({
  isOpen,
  item,
  onClose,
  onInstall,
}: CatalogDetailModalProps) {
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
                <div className="mt-1 flex flex-wrap gap-2">
                  <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                    {item.category}
                  </span>
                  {item.required_secrets.length > 0 && (
                    <span className="inline-flex items-center rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-800">
                      シークレットが必要
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

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-xs font-medium text-gray-500">Dockerイメージ</p>
              <p className="mt-1 font-mono text-sm text-gray-900">{item.docker_image}</p>
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
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4">
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
            className="rounded bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-blue-400"
          >
            インストール
          </button>
        </div>
      </div>
    </div>
  );
}
