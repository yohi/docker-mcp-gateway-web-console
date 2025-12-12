'use client';

import { ContainerInfo } from '../../lib/types/containers';
import ContainerActions from './ContainerActions';

interface ContainerListProps {
  containers: ContainerInfo[];
  onRefresh: () => void;
  onViewLogs: (containerId: string) => void;
  warning?: string;
}

export default function ContainerList({ containers, warning, onRefresh, onViewLogs }: ContainerListProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-green-100 text-green-800';
      case 'stopped':
        return 'bg-gray-100 text-gray-800';
      case 'error':
        return 'bg-red-100 text-red-800 font-bold';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('ja-JP');
  };

  if (warning) {
    return (
      <div className="bg-white shadow-md rounded-lg p-6 border border-yellow-300">
        <div className="flex items-start gap-3">
          <div className="mt-1 h-3 w-3 rounded-full bg-yellow-500 animate-pulse" />
          <div>
            <p className="text-gray-800 font-semibold">Docker に接続できませんでした</p>
            <p className="text-gray-600 text-sm mt-1">{warning}</p>
            <ul className="text-gray-600 text-sm mt-3 list-disc list-inside space-y-1">
              <li>ホストで Docker デーモンが起動しているか確認</li>
              <li>ソケット権限: `sudo usermod -aG docker $USER` 実行後に再ログイン</li>
              <li>rootless Docker の場合: `DOCKER_HOST=unix:///run/user/$UID/docker.sock` を設定</li>
            </ul>
            <button
              type="button"
              onClick={onRefresh}
              className="mt-4 inline-flex items-center px-3 py-1.5 rounded bg-yellow-500 text-white text-sm font-semibold hover:bg-yellow-600 transition"
            >
              再読み込み
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (containers.length === 0) {
    return (
      <div className="bg-white shadow-md rounded-lg p-8 text-center">
        <p className="text-gray-600 text-lg">コンテナがありません</p>
        <p className="text-gray-500 text-sm mt-2">
          新しいコンテナを作成するか、既存のコンテナを起動してください。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {containers.map((container) => (
        <div
          key={container.id}
          className={`bg-white shadow-md rounded-lg p-6 border-l-4 ${
            container.status === 'error' ? 'border-red-500' : 'border-blue-500'
          }`}
        >
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h3 className="text-xl font-bold text-gray-800">{container.name}</h3>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(
                    container.status
                  )}`}
                >
                  {container.status}
                </span>
              </div>
              <p className="text-gray-600 text-sm mb-1">
                <span className="font-semibold">イメージ:</span> {container.image}
              </p>
              <p className="text-gray-600 text-sm mb-1">
                <span className="font-semibold">ID:</span>{' '}
                <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                  {container.id.substring(0, 12)}
                </code>
              </p>
              <p className="text-gray-600 text-sm">
                <span className="font-semibold">作成日時:</span> {formatDate(container.created_at)}
              </p>
            </div>
            <ContainerActions
              container={container}
              onRefresh={onRefresh}
              onViewLogs={onViewLogs}
            />
          </div>

          {Object.keys(container.ports).length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-sm font-semibold text-gray-700 mb-2">ポートマッピング:</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(container.ports).map(([containerPort, hostPort]) => (
                  <span
                    key={containerPort}
                    className="bg-blue-50 text-blue-700 px-3 py-1 rounded text-xs font-mono"
                  >
                    {hostPort} → {containerPort}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
