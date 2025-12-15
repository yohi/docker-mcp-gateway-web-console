import { RemoteServer } from '../types/remote';

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
