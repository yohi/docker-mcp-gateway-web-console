import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ContainerActions from '../../../components/containers/ContainerActions';
import { ContainerInfo } from '../../../lib/types/containers';
import * as api from '../../../lib/api/containers';

// Mock API module
jest.mock('../../../lib/api/containers', () => ({
  startContainer: jest.fn(),
  stopContainer: jest.fn(),
  restartContainer: jest.fn(),
  deleteContainer: jest.fn(),
}));

// Mock useRouter
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe('ContainerActions', () => {
  const mockContainer: ContainerInfo = {
    id: '123',
    name: 'test-container',
    image: 'test-image',
    status: 'stopped',
    created_at: '2023-01-01',
    ports: {},
    labels: {},
  };

  const mockRefresh = jest.fn();
  const mockViewLogs = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders Start button when stopped', () => {
    render(
      <ContainerActions 
        container={{ ...mockContainer, status: 'stopped' }} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    expect(screen.getByText('起動')).toBeInTheDocument();
    expect(screen.queryByText('停止')).not.toBeInTheDocument();
  });

  it('renders Stop and Restart buttons when running', () => {
    render(
      <ContainerActions 
        container={{ ...mockContainer, status: 'running' }} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    expect(screen.getByText('停止')).toBeInTheDocument();
    expect(screen.getByText('再起動')).toBeInTheDocument();
    expect(screen.queryByText('起動')).not.toBeInTheDocument();
  });

  it('calls startContainer API on click', async () => {
    (api.startContainer as jest.Mock).mockResolvedValue({});

    render(
      <ContainerActions 
        container={{ ...mockContainer, status: 'stopped' }} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    fireEvent.click(screen.getByText('起動'));

    expect(api.startContainer).toHaveBeenCalledWith('123');
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
  });

  it('calls stopContainer API on click', async () => {
    (api.stopContainer as jest.Mock).mockResolvedValue({});

    render(
      <ContainerActions 
        container={{ ...mockContainer, status: 'running' }} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    fireEvent.click(screen.getByText('停止'));

    expect(api.stopContainer).toHaveBeenCalledWith('123');
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
  });

  it('shows delete confirmation', () => {
    render(
      <ContainerActions 
        container={mockContainer} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    fireEvent.click(screen.getByText('削除'));
    expect(screen.getByText('確認')).toBeInTheDocument();
    expect(screen.getByText('キャンセル')).toBeInTheDocument();
  });

  it('calls deleteContainer API on confirmation', async () => {
    (api.deleteContainer as jest.Mock).mockResolvedValue({});

    render(
      <ContainerActions 
        container={mockContainer} 
        onRefresh={mockRefresh} 
        onViewLogs={mockViewLogs} 
      />
    );

    fireEvent.click(screen.getByText('削除')); // Show confirm
    fireEvent.click(screen.getByText('確認')); // Confirm

    expect(api.deleteContainer).toHaveBeenCalledWith('123', false);
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
  });
});
