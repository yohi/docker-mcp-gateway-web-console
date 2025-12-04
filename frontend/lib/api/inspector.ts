// Inspector API client

import {
  ToolInfo,
  ResourceInfo,
  PromptInfo,
  InspectorResponse,
} from '../types/inspector';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('session_id') || '';
}

export async function fetchTools(containerId: string): Promise<ToolInfo[]> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/inspector/${containerId}/tools`;

  const response = await fetch(url, {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch tools' }));
    throw new Error(error.detail || 'Failed to fetch tools');
  }

  return response.json();
}

export async function fetchResources(containerId: string): Promise<ResourceInfo[]> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/inspector/${containerId}/resources`;

  const response = await fetch(url, {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch resources' }));
    throw new Error(error.detail || 'Failed to fetch resources');
  }

  return response.json();
}

export async function fetchPrompts(containerId: string): Promise<PromptInfo[]> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/inspector/${containerId}/prompts`;

  const response = await fetch(url, {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch prompts' }));
    throw new Error(error.detail || 'Failed to fetch prompts');
  }

  return response.json();
}

export async function fetchCapabilities(containerId: string): Promise<InspectorResponse> {
  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/inspector/${containerId}/capabilities`;

  const response = await fetch(url, {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch capabilities' }));
    throw new Error(error.detail || 'Failed to fetch capabilities');
  }

  return response.json();
}
