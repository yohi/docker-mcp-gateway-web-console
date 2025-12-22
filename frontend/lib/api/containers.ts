// Container API client

import {
  ContainerListResponse,
  ContainerConfig,
  ContainerCreateResponse,
  ContainerActionResponse,
  ContainerInstallPayload,
  ContainerInstallResponse,
  InstallationError,
  ContainerSummary,
} from '../types/containers';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

function getUrl(path: string): URL {
  if (API_BASE_URL) {
    return new URL(path, API_BASE_URL);
  }
  if (typeof window !== 'undefined') {
    return new URL(path, window.location.origin);
  }
  return new URL(path, 'http://127.0.0.1:3000');
}

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('session_id') || '';
}

function buildAuthHeaders(): Record<string, string> {
  const sessionId = getSessionId();
  return sessionId ? { Authorization: `Bearer ${sessionId}` } : {};
}

export async function fetchContainers(all: boolean = true): Promise<ContainerListResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl('/api/containers');
  url.searchParams.append('all', String(all));

  const response = await fetch(url.toString(), {
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch containers' }));
    throw new Error(error.detail || 'Failed to fetch containers');
  }

  return response.json();
}

export async function createContainer(config: ContainerConfig): Promise<ContainerCreateResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl('/api/containers');

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create container' }));
    throw new Error(error.detail || 'Failed to create container');
  }

  return response.json();
}

export async function installContainer(
  payload: ContainerInstallPayload
): Promise<ContainerInstallResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl('/api/containers/install');

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    const message =
      err instanceof Error
        ? `インストール要求の送信に失敗しました: ${err.message}`
        : 'インストール要求の送信に失敗しました';
    throw { message } satisfies InstallationError;
  }

  const responseBody = await response.json().catch(() => null);

  if (!response.ok) {
    const errorInfo: InstallationError = {
      status: response.status,
      message:
        (responseBody && (responseBody.detail || responseBody.message)) ||
        'コンテナのインストールに失敗しました',
      detail: responseBody?.detail,
      data: responseBody,
    };
    throw errorInfo;
  }

  return (responseBody || {}) as ContainerInstallResponse;
}

export async function startContainer(containerId: string): Promise<ContainerActionResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl(`/api/containers/${containerId}/start`);

  const response = await fetch(url, {
    method: 'POST',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start container' }));
    throw new Error(error.detail || 'Failed to start container');
  }

  return response.json();
}

export async function stopContainer(containerId: string, timeout: number = 10): Promise<ContainerActionResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl(`/api/containers/${containerId}/stop`);
  url.searchParams.append('timeout', String(timeout));

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to stop container' }));
    throw new Error(error.detail || 'Failed to stop container');
  }

  return response.json();
}

export async function restartContainer(containerId: string, timeout: number = 10): Promise<ContainerActionResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl(`/api/containers/${containerId}/restart`);
  url.searchParams.append('timeout', String(timeout));

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to restart container' }));
    throw new Error(error.detail || 'Failed to restart container');
  }

  return response.json();
}

export async function deleteContainer(containerId: string, force: boolean = false): Promise<ContainerActionResponse> {
  const headers = buildAuthHeaders();
  const url = getUrl(`/api/containers/${containerId}`);
  url.searchParams.append('force', String(force));

  const response = await fetch(url.toString(), {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete container' }));
    throw new Error(error.detail || 'Failed to delete container');
  }

  return response.json();
}

export function createLogWebSocket(containerId: string): WebSocket {
  const base = API_BASE_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:3000');
  const wsUrl = base.replace('http://', 'ws://').replace('https://', 'wss://');
  return new WebSocket(`${wsUrl}/api/containers/${containerId}/logs`);
}

export async function fetchContainerConfig(containerId: string): Promise<ContainerConfig> {
  const headers = buildAuthHeaders();
  const url = getUrl(`/api/containers/${containerId}/config`);

  const response = await fetch(url, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch container config' }));
    throw new Error(error.detail || 'Failed to fetch container config');
  }

  return (await response.json()) as ContainerConfig;
}

export async function fetchContainerSummaries(): Promise<{ warning?: string | null; containers: ContainerSummary[] }> {
  const headers = buildAuthHeaders();
  const url = getUrl('/api/containers');
  url.searchParams.append('all', 'true');

  const response = await fetch(url.toString(), {
    headers,
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error('認証が失効しました。再ログインしてください。');
    }
    const message = response.statusText || 'Failed to fetch container summaries';
    let detail = '';
    try {
      detail = await response.text();
    } catch {
      detail = '';
    }
    const errorMessage = detail ? `${message}: ${detail}` : message;
    throw new Error(errorMessage);
  }

  const body = (await response.json()) as ContainerListResponse;
  return {
    warning: body?.warning,
    containers: (body?.containers || []).map((c) => ({
      id: c.id,
      name: c.name,
      image: c.image,
      status: c.status,
    })),
  };
}
