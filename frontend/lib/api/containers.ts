// Container API client

import {
  ContainerListResponse,
  ContainerConfig,
  ContainerCreateResponse,
  ContainerActionResponse,
} from '../types/containers';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('session_id') || '';
}

export async function fetchContainers(all: boolean = true): Promise<ContainerListResponse> {
  const sessionId = getSessionId();
  const url = new URL(`${API_BASE_URL}/api/containers`);
  url.searchParams.append('all', String(all));

  const response = await fetch(url.toString(), {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch containers' }));
    throw new Error(error.detail || 'Failed to fetch containers');
  }

  return response.json();
}

export async function createContainer(config: ContainerConfig): Promise<ContainerCreateResponse> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/containers`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': sessionId,
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create container' }));
    throw new Error(error.detail || 'Failed to create container');
  }

  return response.json();
}

export async function startContainer(containerId: string): Promise<ContainerActionResponse> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/containers/${containerId}/start`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start container' }));
    throw new Error(error.detail || 'Failed to start container');
  }

  return response.json();
}

export async function stopContainer(containerId: string, timeout: number = 10): Promise<ContainerActionResponse> {
  const sessionId = getSessionId();
  const url = new URL(`${API_BASE_URL}/api/containers/${containerId}/stop`);
  url.searchParams.append('timeout', String(timeout));

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to stop container' }));
    throw new Error(error.detail || 'Failed to stop container');
  }

  return response.json();
}

export async function restartContainer(containerId: string, timeout: number = 10): Promise<ContainerActionResponse> {
  const sessionId = getSessionId();
  const url = new URL(`${API_BASE_URL}/api/containers/${containerId}/restart`);
  url.searchParams.append('timeout', String(timeout));

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to restart container' }));
    throw new Error(error.detail || 'Failed to restart container');
  }

  return response.json();
}

export async function deleteContainer(containerId: string, force: boolean = false): Promise<ContainerActionResponse> {
  const sessionId = getSessionId();
  const url = new URL(`${API_BASE_URL}/api/containers/${containerId}`);
  url.searchParams.append('force', String(force));

  const response = await fetch(url.toString(), {
    method: 'DELETE',
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete container' }));
    throw new Error(error.detail || 'Failed to delete container');
  }

  return response.json();
}

export function createLogWebSocket(containerId: string): WebSocket {
  const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
  return new WebSocket(`${wsUrl}/api/containers/${containerId}/logs`);
}
