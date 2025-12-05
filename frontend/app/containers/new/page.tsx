'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CatalogItem } from '@/lib/types/catalog';
import { ContainerConfig } from '@/lib/types/containers';
import ContainerConfigurator from '@/components/containers/ContainerConfigurator';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';

export default function NewContainerPage() {
  const router = useRouter();
  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null);

  useEffect(() => {
    // Retrieve the selected catalog item from sessionStorage
    const stored = sessionStorage.getItem('selectedCatalogItem');
    if (stored) {
      setSelectedItem(JSON.parse(stored));
      // Clear it after retrieval
      sessionStorage.removeItem('selectedCatalogItem');
    }
  }, []);

  const handleSuccess = () => {
    router.push('/dashboard');
  };

  const handleCancel = () => {
    router.push('/catalog');
  };

  if (!selectedItem) {
    return (
      <ProtectedRoute>
        <MainLayout>
          <div className="flex items-center justify-center py-16">
            <div className="text-center max-w-md">
              <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                サーバーが選択されていません
              </h2>
              <p className="text-gray-600 mb-6">
                まずCatalogからサーバーを選択してください。
              </p>
              <button
                onClick={() => router.push('/catalog')}
                className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              >
                Catalogへ
              </button>
            </div>
          </div>
        </MainLayout>
      </ProtectedRoute>
    );
  }

  // Prepare initial config from catalog item (requirement 3.3)
  const initialConfig: Partial<ContainerConfig> = {
    name: selectedItem.id,
    image: selectedItem.docker_image,
    env: selectedItem.default_env,
  };

  return (
    <ProtectedRoute>
      <MainLayout>
        <ContainerConfigurator
          initialConfig={initialConfig}
          onSuccess={handleSuccess}
          onCancel={handleCancel}
        />
      </MainLayout>
    </ProtectedRoute>
  );
}
