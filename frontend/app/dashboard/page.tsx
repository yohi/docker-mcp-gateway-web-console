'use client';

import ProtectedRoute from '../../components/auth/ProtectedRoute';
import LogoutButton from '../../components/auth/LogoutButton';
import { useSession } from '../../contexts/SessionContext';

export default function DashboardPage() {
  const { session } = useSession();

  return (
    <ProtectedRoute>
      <main className="flex min-h-screen flex-col p-8 bg-gray-50">
        <div className="max-w-7xl mx-auto w-full">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-gray-800">ダッシュボード</h1>
              <p className="text-gray-600 mt-2">
                ログイン中: {session?.user_email}
              </p>
            </div>
            <LogoutButton />
          </div>

          <div className="bg-white shadow-md rounded-lg p-6">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">
              Docker MCP Gateway Console
            </h2>
            <p className="text-gray-600">
              コンテナ管理機能は今後実装されます。
            </p>
          </div>
        </div>
      </main>
    </ProtectedRoute>
  );
}
