'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CatalogItem } from '@/lib/types/catalog';

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

  if (!selectedItem) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            No Server Selected
          </h2>
          <p className="text-gray-600 mb-6">
            Please select a server from the catalog first.
          </p>
          <button
            onClick={() => router.push('/catalog')}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Go to Catalog
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Configure Container
        </h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            {selectedItem.name}
          </h2>
          
          <p className="text-gray-600 mb-6">{selectedItem.description}</p>

          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Docker Image
              </h3>
              <p className="text-sm font-mono bg-gray-50 p-2 rounded">
                {selectedItem.docker_image}
              </p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Default Environment Variables
              </h3>
              <div className="bg-gray-50 p-4 rounded space-y-2">
                {Object.entries(selectedItem.default_env).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-sm font-mono text-gray-700">{key}:</span>
                    <span className="text-sm font-mono text-gray-600">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {selectedItem.required_secrets.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  Required Secrets
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedItem.required_secrets.map((secret) => (
                    <span
                      key={secret}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
                    >
                      {secret}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <p className="text-sm text-gray-600 mb-4">
              Container configuration form will be implemented in a future task.
            </p>
            <button
              onClick={() => router.push('/catalog')}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
            >
              Back to Catalog
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
