'use client';

import { useRouter } from 'next/navigation';
import { InspectorPanel } from '../../../components/inspector';
import ProtectedRoute from '../../../components/auth/ProtectedRoute';
import { MainLayout } from '../../../components/layout';

type InspectorPageClientProps = {
  containerId: string;
  containerName?: string;
};

export default function InspectorPageClient({
  containerId,
  containerName,
}: InspectorPageClientProps) {
  const router = useRouter();

  const handleClose = () => {
    router.push('/dashboard');
  };

  return (
    <ProtectedRoute>
      <MainLayout>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-6">
            <button
              onClick={handleClose}
              className="text-blue-600 hover:text-blue-800 flex items-center gap-2 font-medium"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              ダッシュボードに戻る
            </button>
          </div>
          <InspectorPanel
            containerId={containerId}
            containerName={containerName}
            onClose={handleClose}
          />
        </div>
      </MainLayout>
    </ProtectedRoute>
  );
}
