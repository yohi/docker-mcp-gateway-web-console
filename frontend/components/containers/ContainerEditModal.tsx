'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { ContainerConfig, ContainerInfo } from '@/lib/types/containers';
import { deleteContainer, createContainer, stopContainer, fetchContainerConfig } from '@/lib/api/containers';
import ContainerConfigurator from './ContainerConfigurator';
import { useToast } from '@/contexts/ToastContext';

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
    />
  );
}
