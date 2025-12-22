'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { ContainerConfig } from '../../lib/types/containers';
import { createContainer } from '../../lib/api/containers';

interface ContainerConfiguratorProps {
  onSuccess: () => void;
  onCancel: () => void;
  initialConfig?: Partial<ContainerConfig>;
  onSubmit?: (config: ContainerConfig) => Promise<void>;
  submitLabel?: string;
  isSubmitting?: boolean;
  title?: string;
  description?: string;
  children?: ReactNode;
}

export default function ContainerConfigurator({
  onSuccess,
  onCancel,
  initialConfig,
  onSubmit,
  submitLabel,
  isSubmitting,
  title,
  description,
  children,
}: ContainerConfiguratorProps) {
  const [config, setConfig] = useState<ContainerConfig>({
    name: initialConfig?.name || '',
    image: initialConfig?.image || '',
    env: initialConfig?.env || {},
    ports: initialConfig?.ports || {},
    volumes: initialConfig?.volumes || {},
    labels: initialConfig?.labels || {},
    command: initialConfig?.command,
    network_mode: initialConfig?.network_mode,
  });

  // 初期値が変わった場合にフォームを更新
  useEffect(() => {
    if (initialConfig) {
      setConfig({
        name: initialConfig.name || '',
        image: initialConfig.image || '',
        env: initialConfig.env || {},
        ports: initialConfig.ports || {},
        volumes: initialConfig.volumes || {},
        labels: initialConfig.labels || {},
        command: initialConfig.command,
        network_mode: initialConfig.network_mode,
      });
    }
  }, [initialConfig]);

  const [envKey, setEnvKey] = useState('');
  const [envValue, setEnvValue] = useState('');
  const [portContainer, setPortContainer] = useState('');
  const [portHost, setPortHost] = useState('');
  const [volumeHost, setVolumeHost] = useState('');
  const [volumeContainer, setVolumeContainer] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addEnvVar = () => {
    if (envKey && envValue) {
      setConfig((prev) => ({
        ...prev,
        env: { ...prev.env, [envKey]: envValue },
      }));
      setEnvKey('');
      setEnvValue('');
    }
  };

  const removeEnvVar = (key: string) => {
    setConfig((prev) => {
      const newEnv = { ...prev.env };
      delete newEnv[key];
      return { ...prev, env: newEnv };
    });
  };

  const addPort = () => {
    if (portContainer && portHost) {
      setError(null); // Clear previous errors
      const hostPortNum = parseInt(portHost, 10);

      if (isNaN(hostPortNum) || hostPortNum < 1 || hostPortNum > 65535) {
        setError('ホストポートは1から65535の間の有効な数値である必要があります。');
        return;
      }

      setConfig((prev) => ({
        ...prev,
        ports: { ...prev.ports, [portContainer]: hostPortNum },
      }));
      setPortContainer('');
      setPortHost('');
    }
  };

  const removePort = (containerPort: string) => {
    setConfig((prev) => {
      const newPorts = { ...prev.ports };
      delete newPorts[containerPort];
      return { ...prev, ports: newPorts };
    });
  };

  const addVolume = () => {
    if (volumeHost && volumeContainer) {
      setConfig((prev) => ({
        ...prev,
        volumes: { ...prev.volumes, [volumeHost]: volumeContainer },
      }));
      setVolumeHost('');
      setVolumeContainer('');
    }
  };

  const removeVolume = (hostPath: string) => {
    setConfig((prev) => {
      const newVolumes = { ...prev.volumes };
      delete newVolumes[hostPath];
      return { ...prev, volumes: newVolumes };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!config.name.trim() || !config.image.trim()) {
      setError('必須項目を入力してください');
      return;
    }
    setLoading(true);

    try {
      if (onSubmit) {
        await onSubmit(config);
      } else {
        await createContainer(config);
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'コンテナの作成に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto"
      data-testid="container-configurator"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl my-8">
        <form onSubmit={handleSubmit} noValidate>
          {/* Header */}
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-2xl font-bold text-gray-800">
              {title || 'コンテナ設定'}
            </h2>
            <p className="text-gray-600 text-sm mt-1">
              {description || '新しいコンテナを作成するための設定を入力してください'}
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-6 mt-4 bg-red-50 text-red-700 px-4 py-3 rounded border border-red-200">
              <p className="font-semibold">エラー:</p>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Form content */}
          <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
            {/* Basic settings */}
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="containerName"
                  className="block text-sm font-semibold text-gray-700 mb-2"
                >
                  コンテナ名 *
                </label>
                <input
                  id="containerName"
                  type="text"
                  required
                  value={config.name}
                  onChange={(e) => setConfig({ ...config, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="my-mcp-server"
                />
              </div>

              <div>
                <label
                  htmlFor="containerImage"
                  className="block text-sm font-semibold text-gray-700 mb-2"
                >
                  Dockerイメージ *
                </label>
                <input
                  id="containerImage"
                  type="text"
                  required
                  value={config.image}
                  onChange={(e) => setConfig({ ...config, image: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="example/mcp-server:latest"
                />
              </div>

              <div>
                <label
                  htmlFor="containerNetworkMode"
                  className="block text-sm font-semibold text-gray-700 mb-2"
                >
                  ネットワークモード
                </label>
                <input
                  id="containerNetworkMode"
                  type="text"
                  value={config.network_mode || ''}
                  onChange={(e) =>
                    setConfig({ ...config, network_mode: e.target.value || undefined })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="bridge (デフォルト)"
                />
              </div>
            </div>

            {/* Environment variables */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                環境変数
              </label>
              <p className="text-xs text-gray-500 mb-3">
                Bitwarden参照記法を使用できます: {`{{ bw:item-id:field }}`}
              </p>
              <div className="space-y-2">
                {Object.entries(config.env).map(([key, value]) => (
                  <div key={key} className="flex gap-2 items-center bg-gray-50 p-2 rounded">
                    <code className="flex-1 text-sm font-mono">
                      {key}={value}
                    </code>
                    <button
                      type="button"
                      onClick={() => removeEnvVar(key)}
                      className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-xs"
                    >
                      削除
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input
                  type="text"
                  value={envKey}
                  onChange={(e) => setEnvKey(e.target.value)}
                  placeholder="キー"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <input
                  type="text"
                  value={envValue}
                  onChange={(e) => setEnvValue(e.target.value)}
                  placeholder="値"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <button
                  type="button"
                  onClick={addEnvVar}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                >
                  追加
                </button>
              </div>
            </div>

            {/* Ports */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                ポートマッピング
              </label>
              <div className="space-y-2">
                {Object.entries(config.ports).map(([containerPort, hostPort]) => (
                  <div key={containerPort} className="flex gap-2 items-center bg-gray-50 p-2 rounded">
                    <code className="flex-1 text-sm font-mono">
                      {hostPort} → {containerPort}
                    </code>
                    <button
                      type="button"
                      onClick={() => removePort(containerPort)}
                      className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-xs"
                    >
                      削除
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input
                  type="text"
                  value={portContainer}
                  onChange={(e) => setPortContainer(e.target.value)}
                  placeholder="コンテナポート"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <input
                  type="number"
                  min="1"
                  max="65535"
                  value={portHost}
                  onChange={(e) => setPortHost(e.target.value)}
                  placeholder="ホストポート"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <button
                  type="button"
                  onClick={addPort}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                >
                  追加
                </button>
              </div>
            </div>

            {/* Volumes */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                ボリュームマッピング
              </label>
              <div className="space-y-2">
                {Object.entries(config.volumes).map(([hostPath, containerPath]) => (
                  <div key={hostPath} className="flex gap-2 items-center bg-gray-50 p-2 rounded">
                    <code className="flex-1 text-sm font-mono">
                      {hostPath} → {containerPath}
                    </code>
                    <button
                      type="button"
                      onClick={() => removeVolume(hostPath)}
                      className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-xs"
                    >
                      削除
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input
                  type="text"
                  value={volumeHost}
                  onChange={(e) => setVolumeHost(e.target.value)}
                  placeholder="ホストパス"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <input
                  type="text"
                  value={volumeContainer}
                  onChange={(e) => setVolumeContainer(e.target.value)}
                  placeholder="コンテナパス"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                />
                <button
                  type="button"
                  onClick={addVolume}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                >
                  追加
                </button>
              </div>
            </div>

            {children}
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="px-6 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              キャンセル
            </button>
            <button
              type="submit"
              data-testid="container-submit"
              disabled={loading || isSubmitting}
              className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              {loading || isSubmitting ? '処理中...' : submitLabel || 'コンテナを作成'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
