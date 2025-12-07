'use client';

import React, { useState } from 'react';
import { useSession } from '../../contexts/SessionContext';
import { LoginCredentials } from '../../lib/types/auth';

export default function LoginForm() {
  const { login, isLoading, error } = useSession();
  const [method, setMethod] = useState<'api_key' | 'master_password'>('api_key');
  const [email, setEmail] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [masterPassword, setMasterPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const [isTwoStepEnabled, setIsTwoStepEnabled] = useState(false);
  const [twoStepMethod, setTwoStepMethod] = useState<number>(0);
  const [twoStepCode, setTwoStepCode] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    // Validation
    if (!email) {
      setLocalError('メールアドレスを入力してください');
      return;
    }

    if (method === 'api_key') {
      if (!clientId || !clientSecret) {
        setLocalError('Client IDとClient Secretを入力してください');
        return;
      }
      if (!masterPassword) {
        setLocalError('マスターパスワードを入力してください (Vault解除用)');
        return;
      }
    }

    if (method === 'master_password' && !masterPassword) {
      setLocalError('マスターパスワードを入力してください');
      return;
    }

    if (method === 'master_password' && isTwoStepEnabled && !twoStepCode) {
      setLocalError('二段階認証コードを入力してください');
      return;
    }

    const credentials: LoginCredentials = {
      method,
      email,
      ...(method === 'api_key'
        ? { clientId, clientSecret, masterPassword }
        : { masterPassword }
      ),
      ...(method === 'master_password' && isTwoStepEnabled ? {
        twoStepLoginMethod: twoStepMethod,
        twoStepLoginCode: twoStepCode
      } : {}),
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

        <form onSubmit={handleSubmit} role="form">
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

          {/* API Key Inputs */}
          {method === 'api_key' && (
            <div className="mb-6 space-y-4">
              <div>
                <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="clientId">
                  Client ID
                </label>
                <input
                  id="clientId"
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  placeholder="user.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  disabled={isLoading}
                  required
                />
              </div>
              <div>
                <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="clientSecret">
                  Client Secret
                </label>
                <input
                  id="clientSecret"
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  placeholder="Client Secret"
                  disabled={isLoading}
                  required
                />
              </div>
            </div>
          )}

          {/* Master Password Input - Required for both methods now (for API key it unlocks vault) */}
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="masterPassword">
              マスターパスワード {method === 'api_key' && <span className="text-xs font-normal text-gray-500">(Vault解除用)</span>}
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

          {/* Two-step Login Toggle - Only for Master Password method */}
          {method === 'master_password' && (
            <div className="mb-6">
              <div className="mt-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={isTwoStepEnabled}
                    onChange={(e) => setIsTwoStepEnabled(e.target.checked)}
                    className="mr-2"
                    disabled={isLoading}
                  />
                  <span className="text-sm text-gray-700">二段階認証を使用する</span>
                </label>
              </div>

              {/* Two-step Login Fields */}
              {isTwoStepEnabled && (
                <div className="mt-4 p-4 border border-gray-200 rounded-md bg-gray-50">
                  <div className="mb-4">
                    <label className="block text-gray-700 text-xs font-bold mb-2" htmlFor="twoStepMethod">
                      二段階認証メソッド
                    </label>
                    <select
                      id="twoStepMethod"
                      value={twoStepMethod}
                      onChange={(e) => setTwoStepMethod(Number(e.target.value))}
                      className="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline text-sm"
                      disabled={isLoading}
                    >
                      <option value={0}>認証アプリ (Authenticator)</option>
                      <option value={1}>メール (Email)</option>
                      <option value={3}>YubiKey</option>
                    </select>
                  </div>

                  <div className="mb-2">
                    <label className="block text-gray-700 text-xs font-bold mb-2" htmlFor="twoStepCode">
                      認証コード
                    </label>
                    <input
                      id="twoStepCode"
                      type="text"
                      value={twoStepCode}
                      onChange={(e) => setTwoStepCode(e.target.value)}
                      className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                      placeholder="認証コードを入力"
                      disabled={isLoading}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Submit Button */}
          <div className="flex items-center justify-center">
            <button
              type="submit"
              disabled={isLoading}
              className={`bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full ${isLoading ? 'opacity-50 cursor-not-allowed' : ''
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
