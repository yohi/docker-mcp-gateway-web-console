'use client';

import { useMemo } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import { useContainers } from '@/hooks/useContainers';

interface CatalogCardProps {
    item: CatalogItem;
    onInstall: (item: CatalogItem) => void;
}

export default function CatalogCard({ item, onInstall }: CatalogCardProps) {
    const { containers, isLoading } = useContainers();

    const status = useMemo(() => {
        if (isLoading) return 'loading';
        const normalizedName = item.name.toLowerCase();
        const container = containers.find(c =>
            c.image === item.docker_image ||
            c.name.toLowerCase() === normalizedName
        );
        if (container) {
            if (container.status === 'running') return 'running';
            return 'installed';
        }
        return 'not_installed';
    }, [containers, isLoading, item.docker_image]);

    return (
        <div
            className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white flex flex-col h-full"
            data-testid="catalog-card"
        >
            <div className="flex-1">
                <h3
                    className="text-lg font-semibold text-gray-900 mb-2"
                    data-testid="server-name"
                >
                    {item.name}
                </h3>
                <p className="text-xs text-gray-500 mb-2" data-testid="server-vendor">
                    {item.vendor || '提供元未指定'}
                </p>

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
                    <div className="w-full px-4 py-2 bg-gray-100 text-gray-800 rounded-md text-center font-medium">
                        インストール済み
                    </div>
                ) : (
                    <button
                        onClick={() => onInstall(item)}
                        className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                    >
                        インストール
                    </button>
                )}
            </div>
        </div>
    );
}
