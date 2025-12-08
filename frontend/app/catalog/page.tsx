'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import CatalogList from '@/components/catalog/CatalogList';
import InstallModal from '@/components/catalog/InstallModal';
import { CatalogItem } from '@/lib/types/catalog';

export default function CatalogPage() {
  const [catalogSource, setCatalogSource] = useState(
    process.env.NEXT_PUBLIC_CATALOG_URL || 'https://example.com/catalog.json'
  );
  const [inputSource, setInputSource] = useState(catalogSource);

  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null);

  const handleInstall = (item: CatalogItem) => {
    setSelectedItem(item);
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
                placeholder="https://example.com/catalog.json"
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
          <CatalogList catalogSource={catalogSource} onInstall={handleInstall} />

          {/* Install Modal */}
          <InstallModal
            isOpen={!!selectedItem}
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
          />
        </div>
      </MainLayout>
    </ProtectedRoute>
  );
}
