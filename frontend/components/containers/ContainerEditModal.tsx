'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { ContainerConfig, ContainerInfo } from '@/lib/types/containers';
import { deleteContainer, createContainer, stopContainer, fetchContainerConfig } from '@/lib/api/containers';
import ContainerConfigurator from './ContainerConfigurator';
import { useToast } from '@/contexts/ToastContext';
import SessionExecutionPanel from '@/components/catalog/SessionExecutionPanel';
import OAuthModal from '@/components/catalog/OAuthModal';
import type { CatalogItem } from '@/lib/types/catalog';

interface ContainerEditModalProps {
  container: ContainerInfo;
  onClose: () => void;
  onUpdated: () => void;
}

export default function ContainerEditModal({ container, onClose, onUpdated }: ContainerEditModalProps) {
  const { showError, showSuccess } = useToast();
  const [saving, setSaving] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [initialConfig, setInitialConfig] = useState<ContainerConfig | null>(null);
  const [isOAuthOpen, setIsOAuthOpen] = useState(false);
  const [oauthServerId, setOauthServerId] = useState('');
  const [oauthScopesInput, setOauthScopesInput] = useState('');
  const [oauthAuthorizeUrl, setOauthAuthorizeUrl] = useState('');
  const [oauthTokenUrl, setOauthTokenUrl] = useState('');
  const [oauthClientId, setOauthClientId] = useState('');
  const [oauthRedirectUri, setOauthRedirectUri] = useState('');

  const fallbackConfig: ContainerConfig = useMemo(
    () => ({
      name: container.name,
      image: container.image,
      env: {},
      ports: container.ports || {},
      volumes: {},
      labels: container.labels || {},
      command: undefined,
      network_mode: undefined,
    }),
    [container]
  );

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoadingConfig(true);
      try {
        const cfg = await fetchContainerConfig(container.id);
        if (!cancelled) {
          setInitialConfig(cfg);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'コンテナ設定の取得に失敗しました';
        showError(message);
        if (!cancelled) {
          setInitialConfig(fallbackConfig);
        }
      } finally {
        if (!cancelled) setLoadingConfig(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [container.id, fallbackConfig, showError]);

  const panelConfig = initialConfig || fallbackConfig;

  useEffect(() => {
    const nextServerId =
      panelConfig.labels?.['mcp.server_id']?.trim() ||
      container.labels?.['mcp.server_id']?.trim() ||
      panelConfig.name ||
      container.name;
    setOauthServerId(nextServerId);

    const rawScopes =
      panelConfig.labels?.['mcp.required_scopes']?.trim() ||
      container.labels?.['mcp.required_scopes']?.trim() ||
      '';
    setOauthScopesInput(rawScopes);

    const authorizeUrl =
      panelConfig.labels?.['mcp.oauth_authorize_url']?.trim() ||
      container.labels?.['mcp.oauth_authorize_url']?.trim() ||
      '';
    const tokenUrl =
      panelConfig.labels?.['mcp.oauth_token_url']?.trim() ||
      container.labels?.['mcp.oauth_token_url']?.trim() ||
      '';
    const clientId =
      panelConfig.labels?.['mcp.oauth_client_id']?.trim() ||
      container.labels?.['mcp.oauth_client_id']?.trim() ||
      '';
    const redirectUri =
      panelConfig.labels?.['mcp.oauth_redirect_uri']?.trim() ||
      container.labels?.['mcp.oauth_redirect_uri']?.trim() ||
      '';

    setOauthAuthorizeUrl(authorizeUrl);
    setOauthTokenUrl(tokenUrl);
    setOauthClientId(clientId);
    setOauthRedirectUri(redirectUri);
  }, [container.labels, container.name, panelConfig.labels, panelConfig.name]);

  const oauthItem: CatalogItem = useMemo(() => {
    const scopes = oauthScopesInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    return {
      id: oauthServerId || panelConfig.name || container.name,
      name: oauthServerId || panelConfig.name || container.name,
      description: '',
      vendor: '',
      category: 'general',
      docker_image: panelConfig.image,
      icon_url: '',
      default_env: panelConfig.env ?? {},
      required_envs: [],
      required_secrets: [],
      required_scopes: scopes.length ? scopes : undefined,
      oauth_authorize_url: oauthAuthorizeUrl || undefined,
      oauth_token_url: oauthTokenUrl || undefined,
      oauth_client_id: oauthClientId || undefined,
      oauth_redirect_uri: oauthRedirectUri || undefined,
    };
  }, [
    container.name,
    oauthAuthorizeUrl,
    oauthClientId,
    oauthRedirectUri,
    oauthScopesInput,
    oauthServerId,
    oauthTokenUrl,
    panelConfig.env,
    panelConfig.image,
    panelConfig.name,
  ]);

  const handleSubmit = useCallback(
    async (config: ContainerConfig) => {
      setSaving(true);
      try {
        // 実行中なら停止 → 削除 → 再作成
        if (container.status === 'running') {
          await stopContainer(container.id);
        }
        await deleteContainer(container.id, true);
        await createContainer(config);
        showSuccess('コンテナを再作成しました');
        onUpdated();
        onClose();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'コンテナの再作成に失敗しました';
        showError(message);
      } finally {
        setSaving(false);
      }
    },
    [container.id, container.status, onClose, onUpdated, showError, showSuccess]
  );

  return (
    <>
      <ContainerConfigurator
        initialConfig={initialConfig || fallbackConfig}
        onSubmit={handleSubmit}
        onSuccess={onClose}
        onCancel={onClose}
        submitLabel={saving ? '保存中...' : '設定を保存'}
        isSubmitting={saving}
        title="コンテナ設定を編集"
        description={
          loadingConfig
            ? '設定を読み込み中です…'
            : '設定を更新するとコンテナを再作成します。停止中に再作成するか、実行中の場合は一度停止してから再作成します。'
        }
      >
        <div className="rounded-lg border border-gray-200 p-4 space-y-2">
          <p className="text-sm font-semibold text-gray-900">Session/Execution パネル</p>
          <p className="text-xs text-gray-600">
            ゲートウェイ状態を確認し、mcp-exec を同期/非同期で実行できます。
          </p>
          <SessionExecutionPanel
            serverId={oauthServerId || panelConfig.name}
            image={panelConfig.image}
            defaultEnv={panelConfig.env}
          />
        </div>

        <div className="rounded-lg border border-gray-200 p-4 space-y-3">
          <p className="text-sm font-semibold text-gray-900">OAuth接続</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-800" htmlFor="oauth-server-id">
                server_id
              </label>
              <input
                id="oauth-server-id"
                value={oauthServerId}
                onChange={(e) => setOauthServerId(e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="例: github.com/docker/mcp-server"
              />
              <p className="text-xs text-gray-500">
                未設定の場合はコンテナ名を使用します（推奨: カタログの server_id）。
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-800" htmlFor="oauth-scopes">
                scopes (カンマ区切り)
              </label>
              <input
                id="oauth-scopes"
                value={oauthScopesInput}
                onChange={(e) => setOauthScopesInput(e.target.value)}
                className="rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="例: repo, read:user"
              />
            </div>
          </div>

          <details className="rounded border border-gray-200 bg-gray-50 px-3 py-2">
            <summary className="cursor-pointer text-sm font-medium text-gray-800">
              詳細設定 (OAuth URL/Client)
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-800" htmlFor="oauth-authorize-url">
                  authorize_url (任意)
                </label>
                <input
                  id="oauth-authorize-url"
                  value={oauthAuthorizeUrl}
                  onChange={(e) => setOauthAuthorizeUrl(e.target.value)}
                  className="rounded border border-gray-300 px-3 py-2 text-sm"
                  placeholder="https://provider.example.com/authorize"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-800" htmlFor="oauth-token-url">
                  token_url (任意)
                </label>
                <input
                  id="oauth-token-url"
                  value={oauthTokenUrl}
                  onChange={(e) => setOauthTokenUrl(e.target.value)}
                  className="rounded border border-gray-300 px-3 py-2 text-sm"
                  placeholder="https://provider.example.com/token"
                />
              </div>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-800" htmlFor="oauth-client-id">
                  client_id (任意)
                </label>
                <input
                  id="oauth-client-id"
                  value={oauthClientId}
                  onChange={(e) => setOauthClientId(e.target.value)}
                  className="rounded border border-gray-300 px-3 py-2 text-sm"
                  placeholder="mcp-console"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-800" htmlFor="oauth-redirect-uri">
                  redirect_uri (任意)
                </label>
                <input
                  id="oauth-redirect-uri"
                  value={oauthRedirectUri}
                  onChange={(e) => setOauthRedirectUri(e.target.value)}
                  className="rounded border border-gray-300 px-3 py-2 text-sm"
                  placeholder="http://localhost:3000/oauth/callback"
                />
              </div>
            </div>
          </details>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setIsOAuthOpen(true)}
              className="rounded bg-indigo-600 px-4 py-2 text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:bg-indigo-400"
              disabled={!panelConfig.image}
            >
              OAuth接続を開く
            </button>
          </div>
        </div>
      </ContainerConfigurator>

      <OAuthModal
        isOpen={isOAuthOpen}
        item={oauthItem}
        onClose={() => setIsOAuthOpen(false)}
      />
    </>
  );
}
