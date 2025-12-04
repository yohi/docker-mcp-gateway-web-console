'use client';

import { CatalogItem } from '@/lib/types/catalog';

interface ServerCardProps {
  item: CatalogItem;
  onInstall: (item: CatalogItem) => void;
}

export default function ServerCard({ item, onInstall }: ServerCardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white">
      <div className="flex flex-col h-full">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {item.name}
          </h3>
          
          <p className="text-sm text-gray-600 mb-3 line-clamp-3">
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
        
        <button
          onClick={() => onInstall(item)}
          className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
        >
          Install
        </button>
      </div>
    </div>
  );
}
