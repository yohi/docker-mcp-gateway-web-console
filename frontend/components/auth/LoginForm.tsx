'use client';

import React, { useState } from 'react';
import { useSession } from '../../contexts/SessionContext';
import { LoginCredentials } from '../../lib/types/auth';

export default function LoginForm() {
  const { login, isLoading, error } = useSession();
  const [method, setMethod] = useState<'api_key' | 'master_password'>('api_key');
  const [email, setEmail] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [masterPassword, setMasterPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    // Validation
    if (!email) {
      setLocalError('メールアドレスを入力してください');
      return;
    }

    if (method === 'api_key' && !apiKey) {
      setLocalError('APIキーを入力してください');
      return;
    }

    if (method === 'master_password' && !masterPassword) {
      setLocalError('マスターパスワードを入力してください');
      return;
    }

    const credentials: LoginCredentials = {
      method,
      email,
      ...(method === 'api_key' ? { apiKey } : { masterPassword }),
    };

    try {
      await login(credentials);
    } catch (err) {
      // Error is handled by SessionContext
      console.error('Login error:', err);
    }
  };

  const displayError = localError || error;

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="bg-white shadow-md rounded-lg px-8 pt-6 pb-8 mb-4">
        <h2 className="text-2xl font-bold mb-6 text-center text-gray-800">
          Bitwardenでログイン
        </h2>

        {displayError && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {displayError}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Authentication Method Selection */}
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2">
              認証方法
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="api_key"
                  checked={method === 'api_key'}
                  onChange={(e) => setMethod(e.target.value as 'api_key')}
                  className="mr-2"
                  disabled={isLoading}
                />
                <span className="text-sm">APIキー</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="master_password"
                  checked={method === 'master_password'}
                  onChange={(e) => setMethod(e.target.value as 'master_password')}
                  className="mr-2"
                  disabled={isLoading}
                />
                <span className="text-sm">マスターパスワード</span>
              </label>
            </div>
          </div>

          {/* Email Input */}
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="email">
              メールアドレス
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              placeholder="your@email.com"
              disabled={isLoading}
              required
            />
          </div>

          {/* API Key Input */}
          {method === 'api_key' && (
            <div className="mb-6">
              <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="apiKey">
                APIキー
              </label>
              <input
                id="apiKey"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                placeholder="Bitwarden APIキー"
                disabled={isLoading}
                required
              />
            </div>
          )}

          {/* Master Password Input */}
          {method === 'master_password' && (
            <div className="mb-6">
              <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="masterPassword">
                マスターパスワード
              </label>
              <input
                id="masterPassword"
                type="password"
                value={masterPassword}
                onChange={(e) => setMasterPassword(e.target.value)}
                className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                placeholder="マスターパスワード"
                disabled={isLoading}
                required
              />
            </div>
          )}

          {/* Submit Button */}
          <div className="flex items-center justify-center">
            <button
              type="submit"
              disabled={isLoading}
              className={`bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full ${
                isLoading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {isLoading ? 'ログイン中...' : 'ログイン'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
