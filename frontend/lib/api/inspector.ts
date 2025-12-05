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

async function fetchInspectorData<T>(
  containerId: string,
  endpoint: string,
  defaultErrorMessage: string
): Promise<T> {
  const trimmedContainerId = containerId ? containerId.trim() : '';

  if (!trimmedContainerId || !/^[a-zA-Z0-9_-]+$/.test(trimmedContainerId)) {
    throw new Error('Invalid containerId');
  }

  const sessionId = getSessionId();
  const url = `${API_BASE_URL}/api/inspector/${trimmedContainerId}/${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'X-Session-ID': sessionId,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: defaultErrorMessage }));
    throw new Error(error.detail || defaultErrorMessage);
  }

  return response.json();
}

export async function fetchTools(containerId: string): Promise<ToolInfo[]> {
  return fetchInspectorData<ToolInfo[]>(containerId, 'tools', 'Failed to fetch tools');
}

export async function fetchResources(containerId: string): Promise<ResourceInfo[]> {
  return fetchInspectorData<ResourceInfo[]>(containerId, 'resources', 'Failed to fetch resources');
}

export async function fetchPrompts(containerId: string): Promise<PromptInfo[]> {
  return fetchInspectorData<PromptInfo[]>(containerId, 'prompts', 'Failed to fetch prompts');
}

export async function fetchCapabilities(containerId: string): Promise<InspectorResponse> {
  return fetchInspectorData<InspectorResponse>(containerId, 'capabilities', 'Failed to fetch capabilities');
}
