'use client';

import { KeyboardEvent, useMemo, useState, type MouseEvent } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import { useContainers } from '@/hooks/useContainers';
import { matchCatalogItemContainer } from '@/lib/utils/containerMatch';
import { deleteContainer } from '@/lib/api/containers';

interface CatalogCardProps {
    item: CatalogItem;
    onInstall: (item: CatalogItem) => void;
    onSelect?: (item: CatalogItem) => void;
}

export default function CatalogCard({ item, onInstall, onSelect }: CatalogCardProps) {
    const { containers, isLoading, refresh } = useContainers();
    const [isDeleting, setIsDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const scopes = item.required_scopes || [];
    const allowStatus = item.allowlist_status;

    const matchedContainer = useMemo(() => {
        if (isLoading) return 'loading';
        const container = containers.find((c) => matchCatalogItemContainer(item, c));
        return container || null;
    }, [containers, isLoading, item.docker_image, item.name]);

    const status =
        matchedContainer === 'loading'
            ? 'loading'
            : matchedContainer
              ? matchedContainer.status === 'running'
                  ? 'running'
                  : 'installed'
              : 'not_installed';

    const handleSelect = () => {
        if (onSelect) {
            onSelect(item);
        }
    };

    const handleUninstall = async (event: MouseEvent<HTMLButtonElement>) => {
        event.stopPropagation();
        if (!matchedContainer || matchedContainer === 'loading') return;
        setIsDeleting(true);
        setDeleteError(null);
        try {
            await deleteContainer(
                matchedContainer.id,
                matchedContainer.status === 'running'
            );
            await refresh();
        } catch (err) {
            const message =
                err instanceof Error
                    ? err.message
                    : 'コンテナの削除に失敗しました。もう一度お試しください。';
            setDeleteError(message);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
        if (!onSelect) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSelect(item);
        }
    };

    return (
        <div
            className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white flex flex-col h-full cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="catalog-card"
            onClick={handleSelect}
            onKeyDown={handleKeyDown}
            role={onSelect ? 'button' : undefined}
            tabIndex={onSelect ? 0 : -1}
            aria-label={`${item.name}の詳細を表示`}
        >
            <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                    {item.icon_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={item.icon_url}
                            alt={`${item.name} icon`}
                            className="w-10 h-10 rounded-md border border-gray-200 object-cover bg-white"
                        />
                    ) : (
                        <div className="w-10 h-10 rounded-md bg-gray-100 border border-gray-200 flex items-center justify-center text-gray-500 text-sm font-semibold">
                            {item.name.slice(0, 2).toUpperCase()}
                        </div>
                    )}
                    <div>
                        <h3
                            className="text-lg font-semibold text-gray-900"
                            data-testid="server-name"
                        >
                            {item.name}
                        </h3>
                        <p className="text-xs text-gray-500" data-testid="server-vendor">
                            {item.vendor || '提供元未指定'}
                        </p>
                    </div>
                </div>

                <p
                    className="text-sm text-gray-600 mb-3 line-clamp-3"
                    data-testid="server-description"
                >
                    {item.description}
                </p>

                <div className="flex flex-wrap gap-2 mb-3">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {item.category}
                    </span>

                    {item.required_secrets.length > 0 && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            Requires Secrets
                        </span>
                    )}
                    {item.verify_signatures === false && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                            署名検証無効
                        </span>
                    )}
                    {allowStatus && (
                        <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                allowStatus === 'allowed'
                                    ? 'bg-green-100 text-green-800'
                                    : allowStatus === 'pending'
                                        ? 'bg-yellow-100 text-yellow-800'
                                        : 'bg-red-100 text-red-800'
                            }`}
                        >
                            allowlist: {allowStatus}
                        </span>
                    )}
                </div>

                <div className="space-y-1 mb-3">
                    <div className="text-xs text-gray-700">
                        <span className="font-semibold">要求スコープ: </span>
                        {scopes.length > 0 ? scopes.join(', ') : 'なし'}
                    </div>
                    <div className="text-xs text-gray-700">
                        署名検証: {item.verify_signatures === false ? '無効' : '有効'}
                    </div>
                </div>

                <div className="text-xs text-gray-500 mb-2">
                    <span className="font-mono">{item.docker_image}</span>
                </div>
            </div>

            <div className="mt-4">
                {status === 'loading' ? (
                    <button
                        disabled
                        className="w-full px-4 py-2 bg-gray-100 text-gray-400 rounded-md cursor-not-allowed"
                    >
                        読み込み中...
                    </button>
                ) : status === 'running' ? (
                    <div className="w-full px-4 py-2 bg-green-100 text-green-800 rounded-md text-center font-medium">
                        実行中
                    </div>
                ) : status === 'installed' ? (
                    <button
                        onClick={handleUninstall}
                        disabled={isDeleting}
                        className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
                    >
                        {isDeleting ? '削除中...' : 'アンインストール'}
                    </button>
                    {deleteError && (
                        <p className="mt-2 text-sm text-red-600">{deleteError}</p>
                    )}
                ) : (
                    <button
                        onClick={(event) => {
                            event.stopPropagation();
                            onInstall(item);
                        }}
                        className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                    >
                        インストール
                    </button>
                )}
            </div>
        </div>
    );
}
