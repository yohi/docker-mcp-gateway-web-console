// OAuth 関連 API クライアント
import { CatalogItem } from '../types/catalog';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface OAuthInitiatePayload {
  serverId: string;
  scopes: string[];
  authorizeUrl?: string;
  tokenUrl?: string;
  clientId?: string;
  redirectUri?: string;
  codeChallenge?: string;
  codeChallengeMethod?: string;
}

export interface OAuthInitiateResult {
  auth_url: string;
  state: string;
  required_scopes: string[];
}

export interface OAuthExchangeParams {
  code: string;
  state: string;
  serverId: string;
  codeVerifier?: string;
}

export interface OAuthExchangeResult {
  status: string;
  scope: string[];
  credential_key?: string;
  expires_at?: string;
}

export interface OAuthRefreshParams {
  serverId: string;
  credentialKey: string;
}

export interface OAuthRefreshResult {
  credential_key: string;
  refreshed: boolean;
  scope: string[];
  expires_at: string;
}

function toQuery(params: Record<string, string | undefined | null>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      query.append(key, value);
    }
  });
  return query.toString();
}

export async function initiateOAuth(payload: OAuthInitiatePayload): Promise<OAuthInitiateResult> {
  const response = await fetch(`${API_BASE_URL}/api/catalog/oauth/initiate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      server_id: payload.serverId,
      scopes: payload.scopes,
      authorize_url: payload.authorizeUrl,
      token_url: payload.tokenUrl,
      client_id: payload.clientId,
      redirect_uri: payload.redirectUri,
      code_challenge: payload.codeChallenge,
      code_challenge_method: payload.codeChallengeMethod ?? 'S256',
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || '認可の開始に失敗しました');
  }
  return response.json();
}

export async function exchangeOAuth(params: OAuthExchangeParams): Promise<OAuthExchangeResult> {
  const query = toQuery({
    code: params.code,
    state: params.state,
    server_id: params.serverId,
    code_verifier: params.codeVerifier,
  });
  const response = await fetch(`${API_BASE_URL}/api/catalog/oauth/callback?${query}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || 'トークン交換に失敗しました');
  }
  return response.json();
}

export async function refreshOAuth(params: OAuthRefreshParams): Promise<OAuthRefreshResult> {
  const response = await fetch(`${API_BASE_URL}/api/catalog/oauth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      server_id: params.serverId,
      credential_key: params.credentialKey,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || 'トークンリフレッシュに失敗しました');
  }
  return response.json();
}

export function collectScopes(item: CatalogItem): string[] {
  return item.required_scopes ?? [];
}
