'use client';

import { useState, useEffect, useMemo } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import { useToast } from '@/contexts/ToastContext';
import { useInstallation } from '@/hooks/useInstallation';
import { useContainers } from '@/hooks/useContainers';
import { matchCatalogItemContainer } from '@/lib/utils/containerMatch';
import SecretReferenceInput from '../config/SecretReferenceInput';

interface InstallModalProps {
  isOpen: boolean;
  item: CatalogItem | null;
  onClose: () => void;
}

export default function InstallModal({ isOpen, item, onClose }: InstallModalProps) {
  const { showSuccess, showError } = useToast();
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const { install, isLoading } = useInstallation();
  const { containers, isLoading: isContainersLoading, refresh: refreshContainers } = useContainers();

  const installStatus = useMemo<'loading' | 'running' | 'installed' | 'not_installed'>(() => {
    if (isContainersLoading) return 'loading';
    if (!item) return 'not_installed';
    const container = containers.find((c) => matchCatalogItemContainer(item, c));
    if (container) {
      if (container.status === 'running') return 'running';
      return 'installed';
    }
    return 'not_installed';
  }, [containers, isContainersLoading, item]);

  useEffect(() => {
    if (isOpen && item) {
      const initialData: Record<string, string> = { ...item.default_env };
      // Ensure required envs are present in formData
      item.required_envs.forEach(env => {
        if (!initialData.hasOwnProperty(env)) {
          initialData[env] = '';
        }
      });
      setFormData(initialData);
      const initialTouched = Object.keys(initialData).reduce<Record<string, boolean>>((acc, key) => {
        acc[key] = false;
        return acc;
      }, {});
      setTouched(initialTouched);
      setSubmitAttempted(false);
    }
  }, [isOpen, item]);

  if (!isOpen || !item) {
    return null;
  }

  const isSecret = (key: string) => {
    // Check if key is explicitly in required_secrets or matches heuristic
    return item.required_secrets.includes(key) ||
      key.toUpperCase().includes('KEY') ||
      key.toUpperCase().includes('SECRET') ||
      key.toUpperCase().includes('TOKEN') ||
      key.toUpperCase().includes('PASSWORD');
  };

  const handleInstall = async () => {
    setSubmitAttempted(true);
    if (installStatus === 'loading') {
      // 状態取得中はインストール処理を実行しない
      return;
    }
    if (installStatus === 'running' || installStatus === 'installed') {
      const message =
        installStatus === 'running'
          ? 'このサーバーは既に実行中です。コンテナ一覧から操作してください。'
          : 'このサーバーは既にインストール済みです。コンテナ一覧から起動・停止してください。';
      showError(message);
      return;
    }
    // Validation for required envs
    const missing = item.required_envs.filter(key => !formData[key]);
    if (missing.length > 0) {
      showError(`必須項目が未入力です: ${missing.join(', ')}`);
      return;
    }

    const image = (item.docker_image || '').trim();
    if (!image) {
      showError('このカタログ項目にはDockerイメージが定義されていないため、インストールできません。');
      return;
    }

    try {
      const labels: Record<string, string> = {
        'mcp.server_id': item.id,
      };
      if (item.required_scopes && item.required_scopes.length > 0) {
        labels['mcp.required_scopes'] = item.required_scopes.join(', ');
      }
      if (item.oauth_authorize_url) {
        labels['mcp.oauth_authorize_url'] = item.oauth_authorize_url;
      }
      if (item.oauth_token_url) {
        labels['mcp.oauth_token_url'] = item.oauth_token_url;
      }
      if (item.oauth_client_id) {
        labels['mcp.oauth_client_id'] = item.oauth_client_id;
      }
      if (item.oauth_redirect_uri) {
        labels['mcp.oauth_redirect_uri'] = item.oauth_redirect_uri;
      }

      await install({
        name: item.name,
        image,
        env: formData,
        ports: {},
        volumes: {},
        labels,
      });
      try {
        await refreshContainers();
      } catch {
        // noop: インストール自体は成功しているため一覧更新失敗は致命にしない
      }
      showSuccess(`サーバー ${item.name} がインストールされました`);
      onClose();
    } catch (err: any) {
      showError(err.message || 'Installation failed');
    }
  };

  // Sort keys to put required secrets first/top or organize nicely? 
  // For now just existing order.
  const fields = Object.keys(formData);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-lg bg-white shadow-lg overflow-hidden max-h-[90vh] flex flex-col">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">{item.name}をインストール</h2>
          <p className="mt-1 text-sm text-gray-600">
            必要な環境変数を設定してください。Bitwardenの参照も利用可能です。
          </p>
        </div>

        <div className="p-6 overflow-y-auto">
          {(installStatus === 'installed' || installStatus === 'running') && (
            <div
              className={`mb-4 rounded-md border px-3 py-2 text-sm ${
                installStatus === 'running'
                  ? 'border-green-200 bg-green-50 text-green-800'
                  : 'border-gray-200 bg-gray-50 text-gray-800'
              }`}
            >
              {installStatus === 'running'
                ? 'このサーバーは既に実行中です。重複インストールは不要です。'
                : 'このサーバーは既にインストール済みです。コンテナ一覧から起動/停止できます。'}
            </div>
          )}
          <div className="space-y-4">
            {fields.length === 0 ? (
              <p className="text-gray-500 italic">設定可能な環境変数はありません。</p>
            ) : (
              fields.map(key => {
                const fieldId = `env-${key}`;
                return (
                  <div key={key}>
                    {isSecret(key) ? (
                      <SecretReferenceInput
                        label={key}
                        inputId={fieldId}
                        value={formData[key]}
                        onChange={(val) => setFormData(prev => ({ ...prev, [key]: val }))}
                        onBlur={() => setTouched(prev => ({ ...prev, [key]: true }))}
                        required={item.required_envs.includes(key)}
                        disabled={isLoading}
                        placeholder={
                          item.required_envs.includes(key)
                            ? '必須 (値 または {{ bw:... }})'
                            : '任意 ({{ bw:... }} も可)'
                        }
                        error={
                          item.required_envs.includes(key) &&
                          !formData[key] &&
                          (touched[key] || submitAttempted)
                            ? '必須項目です'
                            : undefined
                        }
                      />
                    ) : (
                      <div className="flex flex-col gap-1" data-testid={`env-input-${key}`}>
                        <label className="text-sm font-medium text-gray-700" htmlFor={fieldId}>{key}</label>
                        <input
                          id={fieldId}
                          type="text"
                          value={formData[key]}
                          onChange={(e) => setFormData(prev => ({ ...prev, [key]: e.target.value }))}
                          onBlur={() => setTouched(prev => ({ ...prev, [key]: true }))}
                          disabled={isLoading}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 bg-gray-50">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="rounded bg-gray-500 px-4 py-2 text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            キャンセル
          </button>
          <button
            type="button"
            onClick={handleInstall}
            disabled={isLoading || installStatus !== 'not_installed'}
            className="flex items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
          >
            {isLoading && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-b-transparent"></span>
            )}
            {installStatus === 'running'
              ? '実行中 (インストール済み)'
              : installStatus === 'installed'
                ? 'インストール済み'
                : isLoading
                  ? 'インストール中...'
                  : 'インストール'}
          </button>
        </div>
      </div>
    </div>
  );
}
