/**
 * Example usage of common UI components
 * This file demonstrates how to use Toast, LoadingIndicator, and ConfirmDialog
 */

'use client';

import React, { useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { LoadingIndicator, ConfirmDialog } from './index';

export default function UsageExample() {
  const { showSuccess, showError, showWarning, showInfo } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // Example: API call with loading and toast notifications
  const handleApiCall = async () => {
    setIsLoading(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 2000));
      showSuccess('操作が成功しました');
    } catch (error) {
      showError('エラーが発生しました: ' + (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  // Example: Delete action with confirmation dialog
  const handleDelete = () => {
    setShowConfirm(true);
  };

  const confirmDelete = async () => {
    setShowConfirm(false);
    setIsLoading(true);
    try {
      // Simulate delete API call
      await new Promise((resolve) => setTimeout(resolve, 1000));
      showSuccess('削除が完了しました');
    } catch (error) {
      showError('削除に失敗しました');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-4">
      <h1 className="text-2xl font-bold mb-6">Common UI Components Example</h1>

      {/* Toast Examples */}
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Toast Notifications</h2>
        <div className="flex gap-2">
          <button
            onClick={() => showSuccess('成功メッセージ')}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          >
            Success Toast
          </button>
          <button
            onClick={() => showError('エラーメッセージ')}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Error Toast
          </button>
          <button
            onClick={() => showWarning('警告メッセージ')}
            className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
          >
            Warning Toast
          </button>
          <button
            onClick={() => showInfo('情報メッセージ')}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Info Toast
          </button>
        </div>
      </section>

      {/* Loading Indicator Examples */}
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Loading Indicators</h2>
        <div className="flex gap-4 items-center">
          <LoadingIndicator size="small" />
          <LoadingIndicator size="medium" message="読み込み中..." />
          <LoadingIndicator size="large" />
        </div>
        <button
          onClick={handleApiCall}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Simulate API Call (with loading)
        </button>
      </section>

      {/* Confirm Dialog Example */}
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Confirmation Dialog</h2>
        <button
          onClick={handleDelete}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
        >
          Delete (with confirmation)
        </button>
      </section>

      {/* Full-screen loading overlay */}
      {isLoading && (
        <LoadingIndicator
          size="large"
          message="処理中..."
          fullScreen
        />
      )}

      {/* Confirmation dialog */}
      {showConfirm && (
        <ConfirmDialog
          title="削除の確認"
          message="本当に削除しますか？この操作は取り消せません。"
          confirmText="削除"
          cancelText="キャンセル"
          type="danger"
          onConfirm={confirmDelete}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
