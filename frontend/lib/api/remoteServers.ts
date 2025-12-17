import { RemoteServer, RemoteTestResult } from '../types/remote';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchRemoteServers(): Promise<RemoteServer[]> {
  const response = await fetch(`${API_BASE_URL}/api/remote-servers`);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: 'Failed to fetch remote servers' }));
    throw new Error(error.message || 'Failed to fetch remote servers');
  }

  return response.json();
}

export async function fetchRemoteServerById(serverId: string): Promise<RemoteServer> {
  const response = await fetch(`${API_BASE_URL}/api/remote-servers/${serverId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to fetch remote server' }));
    throw new Error(error.message || 'Failed to fetch remote server');
  }

  return response.json();
}

export interface RemoteOAuthStartResponse {
  auth_url: string;
  state: string;
  required_scopes: string[];
}

export async function startRemoteOAuth(params: {
  serverId: string;
  codeChallenge: string;
  scopes?: string[];
}): Promise<RemoteOAuthStartResponse> {
  const response = await fetch(`${API_BASE_URL}/api/oauth/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      server_id: params.serverId,
      scopes: params.scopes ?? [],
      code_challenge: params.codeChallenge,
      code_challenge_method: 'S256',
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Could not start authentication' }));
    throw new Error(error.message || 'Could not start authentication');
  }

  return response.json();
}

export interface RegisterRemoteServerRequest {
  catalog_item_id: string;
  name: string;
  endpoint: string;
}

export async function registerRemoteServer(
  params: RegisterRemoteServerRequest
): Promise<RemoteServer> {
  const response = await fetch(`${API_BASE_URL}/api/remote-servers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to register remote server' }));
    throw new Error(error.message || 'Failed to register remote server');
  }

  return response.json();
}

export async function testRemoteServer(serverId: string): Promise<RemoteTestResult> {
  const response = await fetch(`${API_BASE_URL}/api/remote-servers/${serverId}/test`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to test remote server connection' }));
    throw new Error(error.message || 'Failed to test remote server connection');
  }

  return response.json();
}
