'use client';

import { useMemo, useState } from 'react';
import type { CatalogItem } from '@/lib/types/catalog';
import { useContainers } from '@/hooks/useContainers';
import { matchCatalogItemContainer } from '@/lib/utils/containerMatch';
import { deleteContainer } from '@/lib/api/containers';
import { useToast } from '@/contexts/ToastContext';

type Props = {
  item: CatalogItem;
  onInstall: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem) => void;
};

const CatalogRow = ({ item, onInstall, onSelect }: Props) => {
  const { containers, refresh, isLoading: isContainersLoading } = useContainers(0);
  const { showSuccess, showError } = useToast();
  const [isDeleting, setIsDeleting] = useState(false);

  const matchedContainer = useMemo(() => {
    if (isContainersLoading) return 'loading';
    const container = containers.find((c) => matchCatalogItemContainer(item, c));
    return container || null;
  }, [containers, isContainersLoading, item.docker_image, item.name]);

  const status =
    matchedContainer === 'loading'
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
      await refresh();
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
          <p className="text-xs text-gray-500 mt-1 break-all">イメージ: {item.docker_image}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {status === 'running' || status === 'installed' ? (
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
