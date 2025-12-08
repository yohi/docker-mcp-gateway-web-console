'use client';

import { useState } from 'react';
import { useToast } from '@/contexts/ToastContext';
import { useInstallation } from '@/hooks/useInstallation';
import { ContainerInstallPayload } from '@/lib/types/containers';

interface InstallModalProps {
  isOpen: boolean;
  payload: ContainerInstallPayload;
  onClose: () => void;
}

/**
 * カタログから呼び出されるインストール用モーダル。
 * Installボタンは `install(payload)` を叩き、`isLoading` をスピナー/ボタン制御に利用する。
 */
export default function InstallModal({ isOpen, payload, onClose }: InstallModalProps) {
  const { showSuccess, showError } = useToast();
  const [showDetails, setShowDetails] = useState(false);
  const { install, isLoading, error } = useInstallation({
    onSuccess: (response) => {
      showSuccess(response.message ?? 'インストール要求を送信しました');
    },
    onError: (err) => {
      showError(err.message);
    },
  });

  if (!isOpen) {
    return null;
  }

  const handleInstall = async () => {
    // Installボタン: install(payload) を呼び出し、結果は呼び出し元でトースト表示
    await install(payload);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-lg bg-white shadow-lg">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">サーバーをインストール</h2>
          <p className="mt-1 text-sm text-gray-600">
            インストール時のAPI呼び出しには useInstallation を利用します。`isLoading` をスピナーやボタンの
            disable制御に使用してください。
          </p>
        </div>

        {error && (
          <div className="mx-6 mt-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error.message}
          </div>
        )}

        <div className="px-6 py-4 space-y-4">
          <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
            <div className="flex items-center justify-between">
              <span className="font-semibold">送信ペイロード</span>
              <button
                type="button"
                onClick={() => setShowDetails((prev) => !prev)}
                className="text-xs font-medium text-blue-600 hover:text-blue-800"
              >
                {showDetails ? '閉じる' : '確認'}
              </button>
            </div>
            {showDetails && (
              <pre className="mt-2 overflow-x-auto text-xs text-gray-800">{JSON.stringify(payload, null, 2)}</pre>
            )}
          </div>

          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span className="inline-flex h-2 w-2 rounded-full bg-green-500"></span>
            install(payload) が解決すると onSuccess を、失敗時は onError を経由し UI でトーストやエラー表示を行えます。
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4">
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
