import {
  GitHubItemSummary,
  GitHubTokenDeleteResponse,
  GitHubTokenSaveResponse,
  GitHubTokenSearchResponse,
  GitHubTokenStatus,
} from '../types/githubToken';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('session_id') || '';
}

function buildAuthHeaders(): Record<string, string> {
  const sessionId = getSessionId();
  if (!sessionId) {
    throw new Error('セッションが見つかりません。再ログインしてください。');
  }
  return { Authorization: `Bearer ${sessionId}` };
}

export async function fetchGitHubTokenStatus(): Promise<GitHubTokenStatus> {
  const headers = buildAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/github-token/status`, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'ステータス取得に失敗しました' }));
    throw new Error(error.detail || 'ステータス取得に失敗しました');
  }
  return response.json();
}

export async function searchBitwardenItems(query: string, limit = 20): Promise<GitHubItemSummary[]> {
  const headers = buildAuthHeaders();
  const url = new URL(`${API_BASE_URL}/api/github-token/search`);
  url.searchParams.append('query', query);
  url.searchParams.append('limit', String(limit));

  const response = await fetch(url.toString(), { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Bitwarden検索に失敗しました' }));
    throw new Error(error.detail || 'Bitwarden検索に失敗しました');
  }
  const data: GitHubTokenSearchResponse = await response.json();
  return data.items;
}

export async function saveGitHubToken(itemId: string, field: string): Promise<GitHubTokenSaveResponse> {
  const headers = buildAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/github-token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify({ item_id: itemId, field }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'GitHubトークンの保存に失敗しました' }));
    throw new Error(error.detail || 'GitHubトークンの保存に失敗しました');
  }

  return response.json();
}

export async function deleteGitHubToken(): Promise<GitHubTokenDeleteResponse> {
  const headers = buildAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/github-token`, {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'GitHubトークンの削除に失敗しました' }));
    throw new Error(error.detail || 'GitHubトークンの削除に失敗しました');
  }

  return response.json();
}

