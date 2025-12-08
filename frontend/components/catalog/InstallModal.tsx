'use client';

import { useState, useEffect } from 'react';
import { CatalogItem } from '@/lib/types/catalog';
import { useToast } from '@/contexts/ToastContext';
import { useInstallation } from '@/hooks/useInstallation';
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
  const { install, isLoading } = useInstallation({
    onError: (err) => showError(err.message || 'Installation failed'),
  });

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
    // Validation for required envs
    const missing = item.required_envs.filter(key => !formData[key]);
    if (missing.length > 0) {
      showError(`必須項目が未入力です: ${missing.join(', ')}`);
      return;
    }

    try {
      await install({
        name: item.name,
        image: item.docker_image,
        env: formData,
        ports: {},
        volumes: {},
        labels: {},
      });
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
                        placeholder={item.required_secrets.includes(key) ? '必須 (または {{ bw:... }})' : '{{ bw:... }}'}
                        error={
                          item.required_secrets.includes(key) &&
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
            disabled={isLoading}
            className="flex items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
          >
            {isLoading && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-b-transparent"></span>
            )}
            {isLoading ? 'インストール中...' : 'インストール'}
          </button>
        </div>
      </div>
    </div>
  );
}
