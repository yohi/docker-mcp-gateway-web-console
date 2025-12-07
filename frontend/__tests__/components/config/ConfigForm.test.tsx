import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ConfigForm from '@/components/config/ConfigForm';
import { GatewayConfig } from '@/lib/types/config';
import { validateGatewayConfig } from '@/lib/utils/configValidator';

// Mock validateGatewayConfig
jest.mock('@/lib/utils/configValidator', () => ({
  validateGatewayConfig: jest.fn(),
}));

// Mock SecretReferenceInput to simplify testing
jest.mock('@/components/config/SecretReferenceInput', () => {
  return function MockSecretReferenceInput({ value, onChange, label }: any) {
    return (
      <div data-testid={`secret-input-${label}`}>
        <label>{label}</label>
        <input 
          value={value} 
          onChange={(e) => onChange(e.target.value)} 
          data-testid={`input-${label}`}
        />
      </div>
    );
  };
});

// Mock window.prompt and window.confirm
const mockPrompt = jest.fn();
const mockConfirm = jest.fn();
window.prompt = mockPrompt;
window.confirm = mockConfirm;

const mockConfig: GatewayConfig = {
  version: '1.0',
  global_settings: {
    'log_level': 'info',
  },
  servers: [
    {
      name: 'server1',
      container_id: 'container1',
      enabled: true,
      config: {
        'API_KEY': 'secret123',
      },
    },
  ],
};

describe('ConfigForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (validateGatewayConfig as jest.Mock).mockReturnValue({ valid: true, errors: [], warnings: [] });
    mockConfirm.mockReturnValue(true); // Default confirm to true
  });

  it('renders initial configuration correctly', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    expect(screen.getByDisplayValue('1.0')).toBeInTheDocument();
    expect(screen.getByTestId('input-log_level')).toHaveValue('info');
    expect(screen.getByDisplayValue('server1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('container1')).toBeInTheDocument();
    expect(screen.getByTestId('input-API_KEY')).toHaveValue('secret123');
  });

  it('updates version', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);
    
    const versionInput = screen.getByDisplayValue('1.0');
    fireEvent.change(versionInput, { target: { value: '2.0' } });
    
    expect(versionInput).toHaveValue('2.0');
  });

  it('adds a global setting', () => {
    mockPrompt.mockReturnValue('new_setting');
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    fireEvent.click(screen.getByText('Add Setting'));

    expect(mockPrompt).toHaveBeenCalledWith('Enter setting key:');
    expect(screen.getByTestId('input-new_setting')).toBeInTheDocument();
  });

  it('removes a global setting', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    // Find the remove button for the log_level setting. 
    // Since there is only one global setting in mockConfig, we can find the first "Remove" button in that section.
    // However, there are multiple "Remove" buttons (global setting, server, server config).
    // The structure is: Global Settings -> Remove button.
    // We can scope it.
    
    const removeButtons = screen.getAllByText('Remove');
    // First remove button should be for global setting (based on render order in component)
    fireEvent.click(removeButtons[0]);

    expect(screen.queryByTestId('input-log_level')).not.toBeInTheDocument();
  });

  it('adds a server', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    fireEvent.click(screen.getByText('Add Server'));

    // Should have 2 servers now (Server 1 and Server 2)
    expect(screen.getByText('Server 2')).toBeInTheDocument();
  });

  it('removes a server', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    const removeServerButton = screen.getAllByText('Remove')[1]; // Second remove button (Server remove)
    fireEvent.click(removeServerButton);

    expect(mockConfirm).toHaveBeenCalled();
    expect(screen.queryByText('Server 1')).not.toBeInTheDocument();
    expect(screen.getByText('No servers configured')).toBeInTheDocument();
  });

  it('updates server fields', () => {
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    const nameInput = screen.getByDisplayValue('server1');
    fireEvent.change(nameInput, { target: { value: 'updated-server' } });
    expect(nameInput).toHaveValue('updated-server');

    const idInput = screen.getByDisplayValue('container1');
    fireEvent.change(idInput, { target: { value: 'updated-id' } });
    expect(idInput).toHaveValue('updated-id');

    const checkbox = screen.getByLabelText('Enabled');
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it('adds server config', () => {
    mockPrompt.mockReturnValue('NEW_ENV');
    render(<ConfigForm initialConfig={mockConfig} onSave={jest.fn()} />);

    fireEvent.click(screen.getByText('Add Config'));

    expect(mockPrompt).toHaveBeenCalledWith('Enter config key:');
    expect(screen.getByTestId('input-NEW_ENV')).toBeInTheDocument();
  });

  it('calls onSave with updated config when valid', async () => {
    const mockOnSave = jest.fn().mockResolvedValue(undefined);
    render(<ConfigForm initialConfig={mockConfig} onSave={mockOnSave} />);

    // Change version to trigger an update
    fireEvent.change(screen.getByDisplayValue('1.0'), { target: { value: '2.0' } });

    fireEvent.submit(screen.getByRole('button', { name: 'Save Configuration' }));

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledTimes(1);
    });

    const savedConfig = mockOnSave.mock.calls[0][0];
    expect(savedConfig.version).toBe('2.0');
  });

  it('shows validation errors and prevents save', async () => {
    const mockOnSave = jest.fn();
    (validateGatewayConfig as jest.Mock).mockReturnValue({
      valid: false,
      errors: ['Invalid version format'],
      warnings: []
    });

    render(<ConfigForm initialConfig={mockConfig} onSave={mockOnSave} />);

    expect(screen.getByText('Invalid version format')).toBeInTheDocument();
    
    const saveButton = screen.getByRole('button', { name: 'Save Configuration' });
    expect(saveButton).toBeDisabled();

    fireEvent.click(saveButton); // Should fail even if not disabled (e.g. handled in submit)
    
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it('shows warnings but allows save', async () => {
    const mockOnSave = jest.fn().mockResolvedValue(undefined);
    (validateGatewayConfig as jest.Mock).mockReturnValue({
      valid: true,
      errors: [],
      warnings: ['Performance warning']
    });

    render(<ConfigForm initialConfig={mockConfig} onSave={mockOnSave} />);

    expect(screen.getByText('Performance warning')).toBeInTheDocument();
    
    const saveButton = screen.getByRole('button', { name: 'Save Configuration' });
    expect(saveButton).not.toBeDisabled();

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalled();
    });
  });
});
