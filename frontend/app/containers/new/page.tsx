'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CatalogItem } from '@/lib/types/catalog';
import { ContainerConfig } from '@/lib/types/containers';
import ContainerConfigurator from '@/components/containers/ContainerConfigurator';
import ProtectedRoute from '@/components/auth/ProtectedRoute';

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
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              サーバーが選択されていません
            </h2>
            <p className="text-gray-600 mb-6">
              まずCatalogからサーバーを選択してください。
            </p>
            <button
              onClick={() => router.push('/catalog')}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Catalogへ
            </button>
          </div>
        </div>
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
      <div className="min-h-screen bg-gray-50">
        <ContainerConfigurator
          initialConfig={initialConfig}
          onSuccess={handleSuccess}
          onCancel={handleCancel}
        />
      </div>
    </ProtectedRoute>
  );
}
