'use client';

import { useState } from 'react';
import {
  createSession,
  executeSession,
  getJobStatus,
} from '@/lib/api/sessions';
import {
  SessionCreateResponse,
  SessionExecAsyncResponse,
  SessionExecSyncResponse,
  SessionJobStatusResponse,
} from '@/lib/types/sessions';

interface SessionExecutionPanelProps {
  serverId: string;
  image: string;
  defaultEnv: Record<string, string>;
}

export default function SessionExecutionPanel({
  serverId,
  image,
  defaultEnv,
}: SessionExecutionPanelProps) {
  const [session, setSession] = useState<SessionCreateResponse | null>(null);
  const [tool, setTool] = useState('');
  const [args, setArgs] = useState('');
  const [asyncMode, setAsyncMode] = useState(false);
  const [maxRunSeconds, setMaxRunSeconds] = useState<number | undefined>(undefined);
  const [outputLimit, setOutputLimit] = useState<number | undefined>(undefined);
  const [execResult, setExecResult] = useState<SessionExecSyncResponse | null>(null);
  const [jobInfo, setJobInfo] = useState<SessionExecAsyncResponse | null>(null);
  const [jobStatus, setJobStatus] = useState<SessionJobStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const created = await createSession({
        serverId,
        image,
        env: defaultEnv,
      });
      setSession(created);
      setExecResult(null);
      setJobInfo(null);
      setJobStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'セッションの作成に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!session) {
      setError('先にゲートウェイを起動してください');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const payloadArgs = args.trim() ? args.trim().split(/\s+/) : [];
      const result = await executeSession({
        sessionId: session.session_id,
        tool,
        args: payloadArgs,
        asyncMode,
        maxRunSeconds,
        outputBytesLimit: outputLimit,
      });
      if ('job_id' in result) {
        setJobInfo(result as SessionExecAsyncResponse);
        setExecResult(null);
        setJobStatus(null);
      } else {
        setExecResult(result as SessionExecSyncResponse);
        setJobInfo(null);
        setJobStatus(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '実行に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  const handleFetchJobStatus = async () => {
    if (!session || !jobInfo) return;
    try {
      setLoading(true);
      const status = await getJobStatus(session.session_id, jobInfo.job_id);
      setJobStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ジョブ状態の取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleCreateSession}
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
          disabled={loading}
        >
          ゲートウェイを起動
        </button>
        <div className="text-xs text-gray-600 self-center">
          server_id={serverId}
        </div>
      </div>

      {session && (
        <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 space-y-1">
          <div className="font-semibold">ゲートウェイ状態</div>
          <div>container_id: {session.container_id}</div>
          <div>endpoint: {session.gateway_endpoint}</div>
          <div>metrics: {session.metrics_endpoint}</div>
          <div>idle_deadline: {session.idle_deadline}</div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-gray-800" htmlFor="exec-tool">
            ツール名
          </label>
          <input
            id="exec-tool"
            value={tool}
            onChange={(e) => setTool(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
            placeholder="mcp-exec ツール"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-gray-800" htmlFor="exec-args">
            引数
          </label>
          <input
            id="exec-args"
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
            placeholder="空白区切り"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-700" htmlFor="max-run">
            最大実行秒数 (任意)
          </label>
          <input
            id="max-run"
            type="number"
            min={10}
            max={300}
            value={maxRunSeconds ?? ''}
            onChange={(e) =>
              setMaxRunSeconds(e.target.value ? Number(e.target.value) : undefined)
            }
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-700" htmlFor="output-limit">
            出力バイト上限 (任意)
          </label>
          <input
            id="output-limit"
            type="number"
            min={32000}
            max={1000000}
            value={outputLimit ?? ''}
            onChange={(e) =>
              setOutputLimit(e.target.value ? Number(e.target.value) : undefined)
            }
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-center gap-2 pt-6">
          <input
            id="async-mode"
            type="checkbox"
            checked={asyncMode}
            onChange={(e) => setAsyncMode(e.target.checked)}
            className="h-4 w-4"
          />
          <label htmlFor="async-mode" className="text-sm text-gray-800">
            非同期で実行
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleExecute}
          className="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-400"
          disabled={loading || !tool}
        >
          {asyncMode ? '非同期実行' : '同期実行'}
        </button>
        {jobInfo && (
          <button
            type="button"
            onClick={handleFetchJobStatus}
            className="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-indigo-400"
            disabled={loading}
          >
            状態を更新
          </button>
        )}
      </div>

      {execResult && (
        <div className="rounded border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 space-y-2">
          <div className="font-semibold">同期実行結果</div>
          <div className="whitespace-pre-wrap break-words">{execResult.output}</div>
          <div>exit_code: {execResult.exit_code}</div>
          {execResult.timeout && <div className="text-red-700">タイムアウトしました</div>}
          {execResult.truncated && (
            <div className="text-yellow-700">出力は切り詰められました</div>
          )}
        </div>
      )}

      {jobInfo && (
        <div className="rounded border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 space-y-1">
          <div className="font-semibold">非同期ジョブ</div>
          <div>job_id: {jobInfo.job_id}</div>
          <div>status: {jobInfo.status}</div>
          <div>queued_at: {jobInfo.queued_at}</div>
        </div>
      )}

      {jobStatus && (
        <div className="rounded border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 space-y-1">
          <div className="font-semibold">ジョブ結果</div>
          <div>status: {jobStatus.status}</div>
          {jobStatus.output && (
            <div className="whitespace-pre-wrap break-words">{jobStatus.output}</div>
          )}
          {jobStatus.exit_code !== undefined && jobStatus.exit_code !== null && (
            <div>exit_code: {jobStatus.exit_code}</div>
          )}
          {jobStatus.timeout && <div className="text-red-700">タイムアウト</div>}
          {jobStatus.truncated && (
            <div className="text-yellow-700">出力は切り詰められました</div>
          )}
        </div>
      )}
    </div>
  );
}
