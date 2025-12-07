import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ContainerList from '../../../components/containers/ContainerList';
import { ContainerInfo } from '../../../lib/types/containers';

// Mock ContainerActions to isolate ContainerList tests
jest.mock('../../../components/containers/ContainerActions', () => {
  return function MockContainerActions({ onViewLogs, container }: any) {
    return (
      <div data-testid={`actions-${container.id}`}>
        <button onClick={() => onViewLogs(container.id)}>Logs</button>
      </div>
    );
  };
});

describe('ContainerList', () => {
  const mockContainers: ContainerInfo[] = [
    {
      id: '1',
      name: 'container-1',
      image: 'image-1',
      status: 'running',
      created_at: '2023-01-01T00:00:00Z',
      ports: { '8080': 80 },
      labels: {},
    },
    {
      id: '2',
      name: 'container-2',
      image: 'image-2',
      status: 'stopped',
      created_at: '2023-01-02T00:00:00Z',
      ports: {},
      labels: {},
    },
  ];

  it('renders empty state when no containers provided', () => {
    render(
      <ContainerList 
        containers={[]} 
        onRefresh={jest.fn()} 
        onViewLogs={jest.fn()} 
      />
    );

    expect(screen.getByText('コンテナがありません')).toBeInTheDocument();
  });

  it('renders list of containers', () => {
    render(
      <ContainerList 
        containers={mockContainers} 
        onRefresh={jest.fn()} 
        onViewLogs={jest.fn()} 
      />
    );

    expect(screen.getByText('container-1')).toBeInTheDocument();
    expect(screen.getByText('container-2')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('stopped')).toBeInTheDocument();
  });

  it('displays port mappings', () => {
    render(
      <ContainerList 
        containers={mockContainers} 
        onRefresh={jest.fn()} 
        onViewLogs={jest.fn()} 
      />
    );

    expect(screen.getByText('80 → 8080')).toBeInTheDocument();
  });

  it('passes onViewLogs callback', () => {
    const handleViewLogs = jest.fn();
    render(
      <ContainerList 
        containers={mockContainers} 
        onRefresh={jest.fn()} 
        onViewLogs={handleViewLogs} 
      />
    );

    const logsButton = screen.getAllByText('Logs')[0];
    fireEvent.click(logsButton);
    expect(handleViewLogs).toHaveBeenCalledWith('1');
  });
});
