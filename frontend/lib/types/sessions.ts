// セッション/実行系の型定義

export interface SessionCreateRequest {
  serverId: string;
  image: string;
  image_digest?: string | null;
  image_thumbprint?: string | null;
  env: Record<string, string>;
  idle_minutes?: number;
}

export interface SessionCreateResponse {
  session_id: string;
  container_id: string;
  gateway_endpoint: string;
  metrics_endpoint: string;
  idle_deadline: string;
}

export interface SessionExecRequest {
  sessionId: string;
  tool: string;
  args: string[];
  asyncMode: boolean;
  maxRunSeconds?: number;
  outputBytesLimit?: number;
}

export interface SessionExecSyncResponse {
  output: string;
  exit_code: number;
  timeout: boolean;
  truncated: boolean;
  started_at: string;
  finished_at: string;
}

export interface SessionExecAsyncResponse {
  job_id: string;
  status: string;
  queued_at: string;
  started_at: string | null;
  result_url: string | null;
}

export interface SessionJobStatusResponse {
  job_id: string;
  status: string;
  output?: string | null;
  exit_code?: number | null;
  timeout: boolean;
  truncated: boolean;
  started_at?: string | null;
  finished_at?: string | null;
}
