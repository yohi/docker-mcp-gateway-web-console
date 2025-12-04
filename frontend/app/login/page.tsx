'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import LoginForm from '../../components/auth/LoginForm';
import { useSession } from '../../contexts/SessionContext';

export default function LoginPage() {
  const { session, isLoading } = useSession();
  const router = useRouter();

  useEffect(() => {
    // Redirect to dashboard if already logged in
    if (!isLoading && session) {
      router.push('/dashboard');
    }
  }, [session, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-gray-600">読み込み中...</p>
        </div>
      </div>
    );
  }

  if (session) {
    return null; // Will redirect
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50">
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold mb-2 text-gray-800">
          Docker MCP Gateway Console
        </h1>
        <p className="text-gray-600">
          Bitwardenアカウントでログインしてください
        </p>
      </div>
      <LoginForm />
    </main>
  );
}
