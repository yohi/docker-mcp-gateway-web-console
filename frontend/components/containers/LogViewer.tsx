'use client';

import { useEffect, useRef, useState } from 'react';
import { LogEntry } from '../../lib/types/containers';
import { createLogWebSocket } from '../../lib/api/containers';

interface LogViewerProps {
  containerId: string;
  onClose: () => void;
}

export default function LogViewer({ containerId, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const sessionId = localStorage.getItem('session_id');
    if (!sessionId) {
      setError('セッションIDが見つかりません');
      return;
    }

    const ws = createLogWebSocket(containerId);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Send session_id as first message
      ws.send(JSON.stringify({ session_id: sessionId }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.error) {
          setError(data.error);
          return;
        }

        const logEntry: LogEntry = {
          timestamp: data.timestamp,
          message: data.message,
          stream: data.stream,
        };

        setLogs((prev) => [...prev, logEntry]);
      } catch (err) {
        console.error('Failed to parse log message:', err);
      }
    };

    ws.onerror = (event) => {
      setError('WebSocket接続エラーが発生しました');
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [containerId]);

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ja-JP', { hour12: false });
  };

  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-gray-800">コンテナログ</h2>
            <span
              className={`px-3 py-1 rounded-full text-xs font-semibold ${
                connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}
            >
              {connected ? '接続中' : '切断'}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={clearLogs}
              className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 text-sm font-medium transition-colors"
            >
              クリア
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium transition-colors"
            >
              閉じる
            </button>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 text-red-700 px-4 py-3 border-b border-red-200">
            <p className="font-semibold">エラー:</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Logs container */}
        <div className="flex-1 overflow-y-auto bg-gray-900 p-4 font-mono text-sm">
          {logs.length === 0 ? (
            <div className="text-gray-400 text-center py-8">
              ログを待機中...
            </div>
          ) : (
            logs.map((log, index) => (
              <div
                key={index}
                className={`py-1 ${
                  log.stream === 'stderr' ? 'text-red-400' : 'text-green-400'
                }`}
              >
                <span className="text-gray-500 mr-2">
                  [{formatTimestamp(log.timestamp)}]
                </span>
                <span className="text-yellow-400 mr-2">[{log.stream}]</span>
                <span className="text-gray-200">{log.message}</span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 bg-gray-50 text-sm text-gray-600">
          <p>
            ログ数: {logs.length} | コンテナID:{' '}
            <code className="bg-gray-200 px-2 py-1 rounded">
              {containerId.substring(0, 12)}
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}
