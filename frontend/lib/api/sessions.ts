// セッション作成・実行系の API クライアント
import {
  SessionCreateRequest,
  SessionCreateResponse,
  SessionExecAsyncResponse,
  SessionExecRequest,
  SessionExecSyncResponse,
  SessionJobStatusResponse,
} from '../types/sessions';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function createSession(payload: SessionCreateRequest): Promise<SessionCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      server_id: payload.serverId,
      image: payload.image,
      image_digest: payload.image_digest,
      image_thumbprint: payload.image_thumbprint,
      env: payload.env,
      idle_minutes: payload.idle_minutes ?? 30,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.message || 'セッションの作成に失敗しました');
  }

  return response.json();
}

export async function executeSession(
  payload: SessionExecRequest
): Promise<SessionExecSyncResponse | SessionExecAsyncResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${payload.sessionId}/exec`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool: payload.tool,
      args: payload.args,
      async_mode: payload.asyncMode,
      max_run_seconds: payload.maxRunSeconds,
      output_bytes_limit: payload.outputBytesLimit,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.message || '実行に失敗しました');
  }

  return response.json();
}

export async function getJobStatus(
  sessionId: string,
  jobId: string
): Promise<SessionJobStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/jobs/${jobId}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.message || 'ジョブ状態の取得に失敗しました');
  }
  return response.json();
}
