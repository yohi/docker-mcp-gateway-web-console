'use client';

import { useMemo, useState } from 'react';
import type { CatalogItem } from '@/lib/types/catalog';
import type { ContainerInfo } from '@/lib/types/containers';
import { matchCatalogItemContainer } from '@/lib/utils/containerMatch';
import { deleteContainer } from '@/lib/api/containers';
import { useToast } from '@/contexts/ToastContext';

type Props = {
  item: CatalogItem;
  containers: ContainerInfo[];
  isContainersLoading: boolean;
  onContainersRefresh: () => void;
  onInstall: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem) => void;
};

const CatalogRow = ({ item, containers, isContainersLoading, onContainersRefresh, onInstall, onSelect }: Props) => {
  const { showSuccess, showError } = useToast();
  const [isDeleting, setIsDeleting] = useState(false);
  const isRemote = item.is_remote || item.server_type === 'remote' || (!!item.remote_endpoint && !item.docker_image);
  const remoteEndpoint = item.remote_endpoint || '';

  const matchedContainer = useMemo(() => {
    if (isRemote) return null;
    if (isContainersLoading) return 'loading';
    const container = containers.find((c) => matchCatalogItemContainer(item, c));
    return container || null;
  }, [containers, isContainersLoading, isRemote, item.docker_image, item.name]);

  const status =
    isRemote
      ? 'remote'
      : matchedContainer === 'loading'
        ? 'loading'
        : matchedContainer
          ? matchedContainer.status === 'running'
            ? 'running'
            : 'installed'
          : 'not_installed';

  const handleUninstall = async () => {
    if (!matchedContainer || matchedContainer === 'loading') return;
    setIsDeleting(true);
    try {
      await deleteContainer(matchedContainer.id, matchedContainer.status === 'running');
      onContainersRefresh();
      showSuccess('コンテナを削除しました');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'コンテナの削除に失敗しました。もう一度お試しください。';
      showError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm flex flex-col gap-3">
      <div className="flex items-start gap-3">
        {item.icon_url ? (
          <img
            src={item.icon_url}
            alt={item.name}
            className="h-12 w-12 rounded-md border border-gray-200 object-cover"
            onError={(event) => {
              event.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          <div className="h-12 w-12 rounded-md bg-gray-100 flex items-center justify-center text-gray-500 font-semibold">
            {item.name.slice(0, 2).toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-gray-900 truncate">{item.name}</h3>
            <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
              {item.category}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                isRemote ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'
              }`}
            >
              {isRemote ? 'リモート' : 'Docker'}
            </span>
            {item.vendor ? (
              <span className="text-xs text-gray-500">by {item.vendor}</span>
            ) : null}
            {status === 'running' && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                実行中
              </span>
            )}
            {status === 'installed' && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                インストール済み
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600 line-clamp-2">{item.description}</p>
          {isRemote ? (
            <p className="text-xs text-gray-500 mt-1 break-all">リモートエンドポイント: {remoteEndpoint || '未設定'}</p>
          ) : (
            <p className="text-xs text-gray-500 mt-1 break-all">イメージ: {item.docker_image || '未設定'}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {isRemote ? (
          <button
            type="button"
            onClick={() => onSelect(item)}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 transition"
          >
            詳細を見る
          </button>
        ) : status === 'running' || status === 'installed' ? (
          <button
            type="button"
            onClick={handleUninstall}
            disabled={isDeleting || status === 'loading'}
            className="px-3 py-1.5 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 transition disabled:opacity-60"
          >
            {isDeleting ? '削除中...' : 'アンインストール'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onInstall(item)}
            disabled={status === 'loading'}
            className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 transition disabled:opacity-60"
          >
            インストール
          </button>
        )}
        <button
          type="button"
          onClick={() => onSelect(item)}
          className="px-3 py-1.5 bg-gray-100 text-gray-800 text-sm rounded-md hover:bg-gray-200 transition"
        >
          詳細
        </button>
      </div>
    </div>
  );
};

export default CatalogRow;
