'use client';

import { useState, useEffect, useCallback } from 'react';
import { ToolInfo, ResourceInfo, PromptInfo } from '../../lib/types/inspector';
import { fetchCapabilities } from '../../lib/api/inspector';
import ToolsList from './ToolsList';
import ResourcesList from './ResourcesList';
import PromptsList from './PromptsList';
import { startContainer } from '../../lib/api/containers';

type TabType = 'tools' | 'resources' | 'prompts';

interface InspectorPanelProps {
  containerId: string;
  containerName?: string;
  onClose?: () => void;
}

export default function InspectorPanel({ containerId, containerName, onClose }: InspectorPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('tools');
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [resources, setResources] = useState<ResourceInfo[]>([]);
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const loadCapabilities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCapabilities(containerId);
      setTools(data.tools);
      setResources(data.resources);
      setPrompts(data.prompts);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'MCP機能の取得に失敗しました';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [containerId]);

  useEffect(() => {
    loadCapabilities();
  }, [loadCapabilities]);

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      await startContainer(containerId);
      await loadCapabilities();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'コンテナの起動に失敗しました';
      setError(message);
    } finally {
      setStarting(false);
    }
  };

  const notRunning = error?.toLowerCase().includes('not running') ?? false;

  const tabs: { id: TabType; label: string; count: number }[] = [
    { id: 'tools', label: 'Tools', count: tools.length },
    { id: 'resources', label: 'Resources', count: resources.length },
    { id: 'prompts', label: 'Prompts', count: prompts.length },
  ];

  return (
    <div className="bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-800 text-white px-6 py-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">MCP Inspector</h2>
          {containerName && (
            <p className="text-gray-300 text-sm mt-1">{containerName}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadCapabilities}
            disabled={loading}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1 rounded text-sm transition-colors"
          >
            {loading ? '読み込み中...' : '更新'}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              <span
                className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                  activeTab === tab.id
                    ? 'bg-blue-100 text-blue-600'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {loading ? '-' : tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="p-6 max-h-[60vh] overflow-y-auto">
        {notRunning ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4 space-y-3">
            <p className="text-sm text-yellow-800 font-semibold">
              コンテナが停止中のため、MCP情報を取得できません。
            </p>
            {error && <p className="text-sm text-yellow-800">{error}</p>}
            <div className="flex gap-3">
              <button
                onClick={handleStart}
                disabled={starting}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-60 text-sm"
              >
                {starting ? '起動中...' : 'コンテナを起動して再取得'}
              </button>
              {onClose && (
                <button
                  onClick={onClose}
                  className="px-4 py-2 bg-gray-100 text-gray-800 rounded-md border border-gray-200 text-sm hover:bg-gray-200"
                >
                  閉じる
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'tools' && (
              <ToolsList tools={tools} loading={loading} error={error} />
            )}
            {activeTab === 'resources' && (
              <ResourcesList resources={resources} loading={loading} error={error} />
            )}
            {activeTab === 'prompts' && (
              <PromptsList prompts={prompts} loading={loading} error={error} />
            )}
          </>
        )}
      </div>

      {/* Footer with summary */}
      {!loading && !error && !notRunning && (
        <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            合計: {tools.length} Tools, {resources.length} Resources, {prompts.length} Prompts
          </p>
        </div>
      )}
    </div>
  );
}
