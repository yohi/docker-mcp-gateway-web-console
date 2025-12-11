'use client';

import type { CatalogItem } from '@/lib/types/catalog';

type Props = {
  item: CatalogItem;
  onInstall: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem) => void;
};

const CatalogRow = ({ item, onInstall, onSelect }: Props) => {
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
          </div>
          <p className="text-sm text-gray-600 line-clamp-2">{item.description}</p>
          <p className="text-xs text-gray-500 mt-1 break-all">イメージ: {item.docker_image}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onInstall(item)}
          className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 transition"
        >
          インストール
        </button>
        <button
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
