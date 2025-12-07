import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import InspectorPanel from '@/components/inspector/InspectorPanel';
import { fetchCapabilities } from '@/lib/api/inspector';
import { ToolInfo, ResourceInfo, PromptInfo } from '@/lib/types/inspector';

// Mock the API
jest.mock('@/lib/api/inspector', () => ({
  fetchCapabilities: jest.fn(),
}));

const mockTools: ToolInfo[] = [
  { name: 'test-tool', description: 'A test tool', input_schema: {} }
];

const mockResources: ResourceInfo[] = [
  { uri: 'test://resource', name: 'test-resource', description: 'A test resource', mime_type: 'text/plain' }
];

const mockPrompts: PromptInfo[] = [
  { name: 'test-prompt', description: 'A test prompt', arguments: [] }
];

describe('InspectorPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state initially', async () => {
    (fetchCapabilities as jest.Mock).mockReturnValue(new Promise(() => {})); // Never resolves
    render(<InspectorPanel containerId="test-container" />);
    
    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    // Check for spinner in tab content (Tools list is default)
    expect(screen.getByText('Tools を読み込み中...')).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    (fetchCapabilities as jest.Mock).mockRejectedValue(new Error('Fetch failed'));
    render(<InspectorPanel containerId="test-container" />);

    await waitFor(() => {
      expect(screen.getByText('Fetch failed')).toBeInTheDocument();
    });
  });

  it('renders capabilities after successful fetch', async () => {
    (fetchCapabilities as jest.Mock).mockResolvedValue({
      tools: mockTools,
      resources: mockResources,
      prompts: mockPrompts,
    });

    render(<InspectorPanel containerId="test-container" containerName="My Container" />);

    await waitFor(() => {
      expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
    });

    // Check header
    expect(screen.getByText('My Container')).toBeInTheDocument();
    
    // Check default view (Tools)
    expect(screen.getByText('test-tool')).toBeInTheDocument();
    expect(screen.getByText('A test tool')).toBeInTheDocument();

    // Check counts in tabs
    const toolTab = screen.getByRole('button', { name: /Tools/i });
    expect(toolTab).toBeInTheDocument();
    expect(toolTab).toHaveTextContent('1');
    
    const resourceTab = screen.getByRole('button', { name: /Resources/i });
    expect(resourceTab).toHaveTextContent('1');

    const promptTab = screen.getByRole('button', { name: /Prompts/i });
    expect(promptTab).toHaveTextContent('1');
  });

  it('switches tabs correctly', async () => {
    (fetchCapabilities as jest.Mock).mockResolvedValue({
      tools: mockTools,
      resources: mockResources,
      prompts: mockPrompts,
    });

    render(<InspectorPanel containerId="test-container" />);
    await waitFor(() => expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument());

    // Switch to Resources
    fireEvent.click(screen.getByRole('button', { name: /Resources/i }));
    expect(screen.getByTestId('resources-list')).toBeInTheDocument();
    expect(screen.getByText('test-resource')).toBeInTheDocument();
    expect(screen.queryByTestId('tools-list')).not.toBeInTheDocument();

    // Switch to Prompts
    fireEvent.click(screen.getByRole('button', { name: /Prompts/i }));
    expect(screen.getByTestId('prompts-list')).toBeInTheDocument();
    expect(screen.getByText('test-prompt')).toBeInTheDocument();
    expect(screen.queryByTestId('resources-list')).not.toBeInTheDocument();
  });

  it('refreshes data when refresh button is clicked', async () => {
    (fetchCapabilities as jest.Mock).mockResolvedValue({
      tools: mockTools,
      resources: mockResources,
      prompts: mockPrompts,
    });

    render(<InspectorPanel containerId="test-container" />);
    await waitFor(() => expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument());

    // Clear mock calls
    (fetchCapabilities as jest.Mock).mockClear();
    (fetchCapabilities as jest.Mock).mockResolvedValue({
      tools: [],
      resources: [],
      prompts: [],
    });

    fireEvent.click(screen.getByRole('button', { name: '更新' }));
    
    expect(screen.getByText('読み込み中...')).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchCapabilities).toHaveBeenCalledWith('test-container');
    });
  });

  it('calls onClose when close button is clicked', async () => {
    (fetchCapabilities as jest.Mock).mockResolvedValue({ tools: [], resources: [], prompts: [] });
    const onClose = jest.fn();
    render(<InspectorPanel containerId="test-container" onClose={onClose} />);
    await waitFor(() => expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument());

    // Find the SVG close button (it doesn't have text, but is the second button in header)
    // Or we can query by role/selector.
    // The component has: <button onClick={onClose}>...</button>
    // It's the button inside the header flex group.
    
    // Let's assume it's one of the buttons.
    // The "更新" button has text "更新".
    // The close button has an SVG.
    // We can try to find by SVG path or assume it's the last button.
    
    // Easier: add aria-label to the component code? I can't modify the component now unless I refactor.
    // I'll try to find buttons.
    const buttons = screen.getAllByRole('button');
    // Expected buttons: Refresh, Close (if provided), Tools Tab, Resources Tab, Prompts Tab.
    // The Close button is in the header, likely the second one.
    fireEvent.click(buttons[1]); // 0 is Refresh, 1 is Close
    
    expect(onClose).toHaveBeenCalled();
  });
});
