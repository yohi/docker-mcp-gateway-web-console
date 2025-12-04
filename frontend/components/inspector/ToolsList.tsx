'use client';

import { ToolInfo } from '../../lib/types/inspector';

interface ToolsListProps {
  tools: ToolInfo[];
  loading?: boolean;
  error?: string | null;
}

export default function ToolsList({ tools, loading, error }: ToolsListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Tools を読み込み中...</span>
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

  if (tools.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>利用可能な Tools がありません</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {tools.map((tool, index) => (
        <div
          key={`${tool.name}-${index}`}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
        >
          <div className="flex items-start justify-between mb-2">
            <h4 className="text-lg font-semibold text-gray-800">{tool.name}</h4>
            <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">Tool</span>
          </div>
          <p className="text-gray-600 text-sm mb-3">{tool.description || '説明なし'}</p>
          {Object.keys(tool.input_schema).length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 mb-2">入力スキーマ:</p>
              <pre className="bg-gray-50 p-3 rounded text-xs overflow-x-auto">
                {JSON.stringify(tool.input_schema, null, 2)}
              </pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
