import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SessionExecutionPanel from '../../../components/catalog/SessionExecutionPanel';
import { createSession, executeSession, getJobStatus } from '../../../lib/api/sessions';

jest.mock('../../../lib/api/sessions', () => ({
  createSession: jest.fn(),
  executeSession: jest.fn(),
  getJobStatus: jest.fn(),
}));

const sessionResponse = {
  session_id: 'sess-1',
  container_id: 'cont-1',
  gateway_endpoint: 'unix:///tmp/gw.sock',
  metrics_endpoint: 'http://localhost:9090',
  idle_deadline: '2025-12-10T00:00:00Z',
};

describe('SessionExecutionPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (createSession as jest.Mock).mockResolvedValue(sessionResponse);
  });

  it('creates session and shows endpoints', async () => {
    render(
      <SessionExecutionPanel
        serverId="server-1"
        image="image:latest"
        defaultEnv={{ API_KEY: 'x' }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'ゲートウェイを起動' }));

    await waitFor(() => {
      expect(createSession).toHaveBeenCalledWith(
        expect.objectContaining({
          serverId: 'server-1',
          image: 'image:latest',
        })
      );
    });

    expect(await screen.findByText('unix:///tmp/gw.sock')).toBeInTheDocument();
    expect(screen.getByText('cont-1')).toBeInTheDocument();
  });

  it('runs sync exec and shows timeout/truncate flags', async () => {
    (executeSession as jest.Mock).mockResolvedValue({
      output: 'hello',
      exit_code: 124,
      timeout: true,
      truncated: true,
      started_at: '2025-12-10T00:00:00Z',
      finished_at: '2025-12-10T00:00:05Z',
    });

    render(
      <SessionExecutionPanel
        serverId="server-1"
        image="image:latest"
        defaultEnv={{}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'ゲートウェイを起動' }));
    await screen.findByText('unix:///tmp/gw.sock');

    fireEvent.change(screen.getByLabelText('ツール名'), { target: { value: 'ping' } });
    fireEvent.change(screen.getByLabelText('引数'), { target: { value: 'localhost' } });

    fireEvent.click(screen.getByRole('button', { name: '同期実行' }));

    await waitFor(() => {
      expect(executeSession).toHaveBeenCalledWith(
        expect.objectContaining({
          sessionId: 'sess-1',
          tool: 'ping',
          args: ['localhost'],
          asyncMode: false,
        })
      );
    });

    expect(await screen.findByText('hello')).toBeInTheDocument();
    expect(screen.getByText(/タイムアウト/)).toBeInTheDocument();
    expect(screen.getByText(/出力は切り詰められました/)).toBeInTheDocument();
  });

  it('polls async job status', async () => {
    (executeSession as jest.Mock).mockResolvedValue({
      job_id: 'job-1',
      status: 'queued',
      queued_at: '2025-12-10T00:00:00Z',
      started_at: null,
      result_url: null,
    });
    (getJobStatus as jest.Mock).mockResolvedValue({
      job_id: 'job-1',
      status: 'succeeded',
      output: 'done',
      exit_code: 0,
      timeout: false,
      truncated: false,
      started_at: '2025-12-10T00:00:01Z',
      finished_at: '2025-12-10T00:00:02Z',
    });

    render(
      <SessionExecutionPanel
        serverId="server-1"
        image="image:latest"
        defaultEnv={{}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'ゲートウェイを起動' }));
    await screen.findByText('unix:///tmp/gw.sock');

    fireEvent.change(screen.getByLabelText('ツール名'), { target: { value: 'echo' } });
    fireEvent.click(screen.getByLabelText('非同期で実行'));

    fireEvent.click(screen.getByRole('button', { name: '非同期実行' }));

    await waitFor(() => {
      expect(executeSession).toHaveBeenCalledWith(
        expect.objectContaining({
          asyncMode: true,
        })
      );
    });

    expect(await screen.findByText('job-1')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '状態を更新' }));

    await waitFor(() => {
      expect(getJobStatus).toHaveBeenCalledWith('sess-1', 'job-1');
    });

    expect(await screen.findByText('done')).toBeInTheDocument();
  });
});
