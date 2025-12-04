'use client';

import { useState } from 'react';
import { ContainerInfo } from '../../lib/types/containers';
import {
  startContainer,
  stopContainer,
  restartContainer,
  deleteContainer,
} from '../../lib/api/containers';

interface ContainerActionsProps {
  container: ContainerInfo;
  onRefresh: () => void;
  onViewLogs: (containerId: string) => void;
}

export default function ContainerActions({
  container,
  onRefresh,
  onViewLogs,
}: ContainerActionsProps) {
  const [loading, setLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAction = async (
    action: () => Promise<any>,
    successMessage: string
  ) => {
    setLoading(true);
    setError(null);
    try {
      await action();
      // Show success message briefly
      setTimeout(() => {
        onRefresh();
      }, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'アクションに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handleStart = () => {
    handleAction(() => startContainer(container.id), 'コンテナを起動しました');
  };

  const handleStop = () => {
    handleAction(() => stopContainer(container.id), 'コンテナを停止しました');
  };

  const handleRestart = () => {
    handleAction(() => restartContainer(container.id), 'コンテナを再起動しました');
  };

  const handleDelete = () => {
    handleAction(
      () => deleteContainer(container.id, container.status === 'running'),
      'コンテナを削除しました'
    );
    setShowDeleteConfirm(false);
  };

  return (
    <div className="flex flex-col gap-2">
      {error && (
        <div className="bg-red-50 text-red-700 px-3 py-2 rounded text-xs mb-2">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        {container.status === 'stopped' && (
          <button
            onClick={handleStart}
            disabled={loading}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
          >
            {loading ? '処理中...' : '起動'}
          </button>
        )}

        {container.status === 'running' && (
          <>
            <button
              onClick={handleStop}
              disabled={loading}
              className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {loading ? '処理中...' : '停止'}
            </button>
            <button
              onClick={handleRestart}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {loading ? '処理中...' : '再起動'}
            </button>
          </>
        )}

        <button
          onClick={() => onViewLogs(container.id)}
          disabled={loading}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
        >
          ログ
        </button>

        {!showDeleteConfirm ? (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            disabled={loading}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm font-medium transition-colors"
          >
            削除
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={loading}
              className="px-3 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm font-medium"
            >
              確認
            </button>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              disabled={loading}
              className="px-3 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 text-sm font-medium"
            >
              キャンセル
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
