'use client';

import { PromptInfo } from '../../lib/types/inspector';

interface PromptsListProps {
  prompts: PromptInfo[];
  loading?: boolean;
  error?: string | null;
}

export default function PromptsList({ prompts, loading, error }: PromptsListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
        <span className="ml-3 text-gray-600">Prompts を読み込み中...</span>
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

  if (prompts.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>利用可能な Prompts がありません</p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="prompts-list">
      {prompts.map((prompt, index) => (
        <div
          key={`${prompt.name}-${index}`}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
        >
          <div className="flex items-start justify-between mb-2">
            <h4 className="text-lg font-semibold text-gray-800">{prompt.name}</h4>
            <span className="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded">Prompt</span>
          </div>
          <p className="text-gray-600 text-sm mb-3">{prompt.description || '説明なし'}</p>
          {prompt.arguments.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 mb-2">引数:</p>
              <div className="space-y-2">
                {prompt.arguments.map((arg, argIndex) => (
                  <div
                    key={`${arg.name}-${argIndex}`}
                    className="bg-gray-50 p-2 rounded flex items-start gap-2"
                  >
                    <code className="text-xs font-semibold text-purple-700">{arg.name}</code>
                    {arg.required && (
                      <span className="text-red-500 text-xs">*必須</span>
                    )}
                    {arg.description && (
                      <span className="text-xs text-gray-600">- {arg.description}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
