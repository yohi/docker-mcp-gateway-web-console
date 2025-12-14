'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  deleteGitHubToken,
  fetchGitHubTokenStatus,
  saveGitHubToken,
  searchBitwardenItems,
} from '@/lib/api/githubToken';
import { GitHubItemSummary, GitHubTokenStatus } from '@/lib/types/githubToken';
import { useToast } from '@/contexts/ToastContext';

interface SelectionState {
  [itemId: string]: string;
}

export default function GitHubTokenSection() {
  const { showError, showSuccess } = useToast();
  const [status, setStatus] = useState<GitHubTokenStatus | null>(null);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [items, setItems] = useState<GitHubItemSummary[]>([]);
  const [selection, setSelection] = useState<SelectionState>({});
  const [savingItemId, setSavingItemId] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [inlineError, setInlineError] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const formattedUpdatedAt = useMemo(() => {
    if (!status?.updated_at) return null;
    return new Date(status.updated_at).toLocaleString();
  }, [status?.updated_at]);

  const loadStatus = async () => {
    setLoadingStatus(true);
    setInlineError(null);
    try {
      const s = await fetchGitHubTokenStatus();
      setStatus(s);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'ステータス取得に失敗しました';
      showError(message);
      setInlineError(message);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      showError('検索キーワードを入力してください');
      setInlineError('検索キーワードを入力してください');
      return;
    }
    setSearching(true);
    setInlineError(null);
    try {
      const results = await searchBitwardenItems(trimmed, 20);
      setItems(results);
      const defaults: SelectionState = {};
      results.forEach((item) => {
        if (item.fields.length > 0) {
          defaults[item.id] = item.fields[0];
        }
      });
      setSelection(defaults);
      if (results.length === 0) {
        showError('検索結果がありません。キーワードを変えて再試行してください。');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Bitwarden検索に失敗しました';
      showError(message);
      setInlineError(message);
    } finally {
      setSearching(false);
    }
  };

  const handleSave = async (itemId: string) => {
    const field = selection[itemId];
    if (!field) {
      showError('保存するフィールドを選択してください');
      return;
    }
    setSavingItemId(itemId);
    setInlineError(null);
    try {
      const response = await saveGitHubToken(itemId, field);
      setStatus(response.status);
      showSuccess('GitHubトークンを保存しました');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'GitHubトークンの保存に失敗しました';
      showError(message);
      setInlineError(message);
    } finally {
      setSavingItemId(null);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteGitHubToken();
      setStatus({ configured: false, source: null, updated_at: null, updated_by: null });
      showSuccess('保存済みのGitHubトークンを削除しました');
      setInlineError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'GitHubトークンの削除に失敗しました';
      showError(message);
      setInlineError(message);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">GitHubトークン設定</h2>
          <p className="text-sm text-gray-600 mt-1">
            Bitwardenに保存されたGitHub PATを検索して設定します。トークン値は表示されません。
          </p>
        </div>
        <div className="text-sm text-gray-700">
          {loadingStatus ? (
            <span>読み込み中...</span>
          ) : status?.configured ? (
            <div className="text-green-700">
              <span className="font-medium">設定済み</span>
              {formattedUpdatedAt && <span className="ml-2 text-gray-600">更新: {formattedUpdatedAt}</span>}
              {status?.source && <div className="text-xs text-gray-500">source: {status.source}</div>}
            </div>
          ) : (
            <span className="text-gray-600">未設定</span>
          )}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Bitwardenアイテム名で検索"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          onClick={handleSearch}
          disabled={searching || query.trim() === ''}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {searching ? '検索中...' : 'Bitwardenを検索'}
        </button>
        <button
          type="button"
          onClick={handleDelete}
          className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
        >
          クリア
        </button>
      </div>

      {inlineError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
          {inlineError}
        </div>
      )}

      {items.length > 0 && (
        <div className="border border-gray-200 rounded-md divide-y">
          {items.map((item) => (
            <div key={item.id} className="p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-gray-900">{item.name}</div>
                <div className="text-xs text-gray-500">ID: {item.id}</div>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 items-center">
                <select
                  value={selection[item.id] || ''}
                  onChange={(e) => setSelection((prev) => ({ ...prev, [item.id]: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]"
                >
                  <option value="" disabled>
                    フィールドを選択
                  </option>
                  {item.fields.map((field) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleSave(item.id)}
                  disabled={savingItemId === item.id}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-60"
                >
                  {savingItemId === item.id ? '保存中...' : 'Bitwardenから設定'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
