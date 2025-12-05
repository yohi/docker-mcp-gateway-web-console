'use client';

import { ResourceInfo } from '../../lib/types/inspector';

interface ResourcesListProps {
  resources: ResourceInfo[];
  loading?: boolean;
  error?: string | null;
}

export default function ResourcesList({ resources, loading, error }: ResourcesListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
        <span className="ml-3 text-gray-600">Resources を読み込み中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-700">{error}</p>
      </div>
    );
  }

  if (resources.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>利用可能な Resources がありません</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {resources.map((resource, index) => (
        <div
          key={`${resource.uri}-${index}`}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
        >
          <div className="flex items-start justify-between mb-2">
            <h4 className="text-lg font-semibold text-gray-800">{resource.name}</h4>
            <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">Resource</span>
          </div>
          <p className="text-gray-600 text-sm mb-3">{resource.description || '説明なし'}</p>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-gray-500">URI:</span>
              <code className="bg-gray-100 px-2 py-1 rounded text-xs text-gray-700">
                {resource.uri}
              </code>
            </div>
            {resource.mime_type && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500">MIME Type:</span>
                <code className="bg-gray-100 px-2 py-1 rounded text-xs text-gray-700">
                  {resource.mime_type}
                </code>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
