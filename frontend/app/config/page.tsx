'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import { MainLayout } from '@/components/layout';
import { fetchGatewayConfig, saveGatewayConfig } from '@/lib/api/config';
import { GatewayConfig } from '@/lib/types/config';
import ConfigForm from '@/components/config/ConfigForm';
import { useToast } from '@/contexts/ToastContext';

export default function ConfigPage() {
  const router = useRouter();
  const { showSuccess, showError } = useToast();
  const [config, setConfig] = useState<GatewayConfig | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGatewayConfig();
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '設定の読み込みに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (newConfig: GatewayConfig) => {
    setError(null);
    try {
      const response = await saveGatewayConfig(newConfig);
      showSuccess(response.message || '設定を保存しました');
      setConfig(newConfig);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '設定の保存に失敗しました';
      setError(errorMessage);
      showError(errorMessage);
    }
  };

  const handleCancel = () => {
    router.push('/dashboard');
  };

  if (isLoading) {
    return (
      <ProtectedRoute>
        <MainLayout>
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">設定を読み込み中...</p>
            </div>
          </div>
        </MainLayout>
      </ProtectedRoute>
    );
  }

  if (error && !config) {
    return (
      <ProtectedRoute>
        <MainLayout>
          <div className="max-w-2xl mx-auto px-4 py-16">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="text-red-600 mb-4">
                <svg className="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 text-center mb-2">
                設定の読み込みに失敗しました
              </h2>
              <p className="text-gray-600 text-center mb-4">{error}</p>
              <div className="flex gap-3">
                <button
                  onClick={loadConfig}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  再試行
                </button>
                <button
                  onClick={handleCancel}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  ダッシュボードに戻る
                </button>
              </div>
            </div>
          </div>
        </MainLayout>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <MainLayout>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Gateway設定</h1>
            <p className="mt-2 text-gray-600">
              MCP Gatewayの設定を管理します。機密情報にはBitwarden参照記法 {`{{ bw:item-id:field }}`} を使用してください。
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex items-center">
                <svg className="h-5 w-5 text-red-600 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm text-red-800">{error}</p>
              </div>
            </div>
          )}

          {/* Config Form */}
          {config && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <ConfigForm
                initialConfig={config}
                onSave={handleSave}
                onCancel={handleCancel}
              />
            </div>
          )}
        </div>
      </MainLayout>
    </ProtectedRoute>
  );
}
