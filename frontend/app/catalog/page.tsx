'use client';

import { useMemo, useState } from 'react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import CatalogList from '@/components/catalog/CatalogList';
import InstallModal from '@/components/catalog/InstallModal';
import CatalogDetailModal from '@/components/catalog/CatalogDetailModal';
import OAuthModal from '@/components/catalog/OAuthModal';
import { CatalogItem } from '@/lib/types/catalog';
import { isRemoteCatalogItem } from '@/lib/utils/catalogUtils';
import { createRemoteServer } from '@/lib/api/remoteServers';
import { useToast } from '@/contexts/ToastContext';

const DEFAULT_CATALOG_URL =
  process.env.NEXT_PUBLIC_CATALOG_URL ||
  'https://api.github.com/repos/docker/mcp-registry/contents/servers';

function RemoteRegisterModal({
  item,
  isOpen,
  isLoading,
  onConfirm,
  onClose,
}: {
  item: CatalogItem | null;
  isOpen: boolean;
  isLoading: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  if (!isOpen || !item) return null;

  const scopes = item.required_scopes ?? [];
  const endpoint = item.remote_endpoint || '未設定';
  const allowlistHint = item.allowlist_hint;
  const requiresOAuth = useMemo(
    () =>
      Boolean(item.oauth_authorize_url || item.oauth_token_url || item.oauth_client_id || item.oauth_config),
    [item],
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-lg bg-white shadow-lg overflow-hidden max-h-[90vh] flex flex-col">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">リモートサーバーを登録</h2>
          <p className="mt-1 text-sm text-gray-600">登録後に必要に応じて OAuth 接続や接続テストを実行してください。</p>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto">
          <div>
            <p className="text-xs font-medium text-gray-500">名称</p>
            <p className="text-sm text-gray-900">{item.name}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500">リモートエンドポイント</p>
            <p className="font-mono text-sm text-gray-900 break-words">{endpoint}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500">要求スコープ</p>
            <p className="text-sm text-gray-900">{scopes.length > 0 ? scopes.join(', ') : 'なし'}</p>
          </div>
          {allowlistHint && (
            <div className="rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-sm text-blue-800">
              <p className="font-semibold">Allowlist ヒント</p>
              <p className="mt-1">{allowlistHint}</p>
            </div>
          )}
          {requiresOAuth && (
            <div className="rounded-md bg-indigo-50 border border-indigo-100 px-3 py-2 text-sm text-indigo-800">
              <p className="font-semibold">認証が必要です</p>
              <p className="mt-1">登録後に「OAuth接続」ボタンから認可フローを実行してください。</p>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 bg-gray-50">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="rounded bg-gray-500 px-4 py-2 text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            キャンセル
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className="flex items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
          >
            {isLoading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-b-transparent"></span>}
            登録する
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const [catalogSource, setCatalogSource] = useState(DEFAULT_CATALOG_URL);
  const [inputSource, setInputSource] = useState(catalogSource);

  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null);
  const [detailItem, setDetailItem] = useState<CatalogItem | null>(null);
  const [oauthItem, setOauthItem] = useState<CatalogItem | null>(null);
  const [remoteConfirmItem, setRemoteConfirmItem] = useState<CatalogItem | null>(null);
  const [isRegisteringRemote, setIsRegisteringRemote] = useState(false);
  const { showSuccess, showError } = useToast();

  const handleInstall = async (item: CatalogItem) => {
    setDetailItem(null);
    if (isRemoteCatalogItem(item)) {
      setRemoteConfirmItem(item);
      return;
    }

    setSelectedItem(item);
  };

  const handleSelect = (item: CatalogItem) => {
    setDetailItem(item);
  };

  const handleOAuth = (item: CatalogItem) => {
    setOauthItem(item);
  };

  const handleConfirmRemote = async () => {
    if (!remoteConfirmItem || isRegisteringRemote) return;
    setIsRegisteringRemote(true);
    try {
      await createRemoteServer(remoteConfirmItem.id);
      showSuccess(`リモートサーバー「${remoteConfirmItem.name}」を登録しました`);
      setRemoteConfirmItem(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'リモートサーバーの登録に失敗しました';
      showError(message);
    } finally {
      setIsRegisteringRemote(false);
    }
  };

  const handleCloseRemoteConfirm = () => {
    if (isRegisteringRemote) return;
    setRemoteConfirmItem(null);
  };

  const handleSourceChange = () => {
    setCatalogSource(inputSource);
  };

  return (
    <ProtectedRoute>
      <MainLayout>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">MCP Server Catalog</h1>
            <p className="mt-2 text-gray-600">
              Catalogから利用可能なMCPサーバーを検索してインストールします
            </p>
          </div>

          {/* Catalog source input */}
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 mb-6">
            <label htmlFor="catalog-source" className="block text-sm font-medium text-gray-700 mb-2">
              Catalog Source URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                id="catalog-source"
                value={inputSource}
                onChange={(e) => setInputSource(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder={DEFAULT_CATALOG_URL}
              />
              <button
                onClick={handleSourceChange}
                disabled={inputSource === catalogSource}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                読み込み
              </button>
            </div>
          </div>

          {/* Catalog list */}
          <CatalogList catalogSource={catalogSource} onInstall={handleInstall} onSelect={handleSelect} />

          {/* Install Modal */}
          <InstallModal
            isOpen={!!selectedItem}
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
          />

          <RemoteRegisterModal
            isOpen={!!remoteConfirmItem}
            item={remoteConfirmItem}
            isLoading={isRegisteringRemote}
            onConfirm={handleConfirmRemote}
            onClose={handleCloseRemoteConfirm}
          />

          <CatalogDetailModal
            isOpen={!!detailItem}
            item={detailItem}
            onClose={() => setDetailItem(null)}
            onInstall={handleInstall}
            onOAuth={handleOAuth}
          />

          <OAuthModal
            isOpen={!!oauthItem}
            item={oauthItem}
            onClose={() => setOauthItem(null)}
          />
        </div>
      </MainLayout>
    </ProtectedRoute>
  );
}
