// Gateway Config API client

import {
  ConfigReadResponse,
  ConfigWriteRequest,
  ConfigWriteResponse,
  GatewayConfig,
} from '../types/config';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

export async function fetchGatewayConfig(): Promise<GatewayConfig> {
  const headers = buildAuthHeaders();
  const url = `${API_BASE_URL}/api/config/gateway`;

  const response = await fetch(url, {
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch gateway config' }));
    throw new Error(error.detail || 'Failed to fetch gateway config');
  }

  const data: ConfigReadResponse = await response.json();
  return data.config;
}

export async function saveGatewayConfig(config: GatewayConfig): Promise<ConfigWriteResponse> {
  const headers = buildAuthHeaders();
  const url = `${API_BASE_URL}/api/config/gateway`;

  const requestBody: ConfigWriteRequest = { config };

  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to save gateway config' }));
    throw new Error(error.detail || 'Failed to save gateway config');
  }

  return response.json();
}
