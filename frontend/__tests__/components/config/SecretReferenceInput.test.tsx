import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SecretReferenceInput from '@/components/config/SecretReferenceInput';

describe('SecretReferenceInput', () => {
  it('renders input with label', () => {
    const mockOnChange = jest.fn();
    render(
      <SecretReferenceInput
        value=""
        onChange={mockOnChange}
        label="Test Label"
      />
    );

    expect(screen.getByText('Test Label')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('calls onChange when input value changes', () => {
    const mockOnChange = jest.fn();
    render(
      <SecretReferenceInput
        value=""
        onChange={mockOnChange}
      />
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'test value' } });

    expect(mockOnChange).toHaveBeenCalledWith('test value');
  });

  it('detects Bitwarden reference notation', () => {
    const mockOnChange = jest.fn();
    const { rerender } = render(
      <SecretReferenceInput
        value=""
        onChange={mockOnChange}
      />
    );

    // Initially no Bitwarden indicator
    expect(screen.queryByText('🔐 Bitwarden')).not.toBeInTheDocument();

    // Update with Bitwarden reference
    rerender(
      <SecretReferenceInput
        value="{{ bw:item123:password }}"
        onChange={mockOnChange}
      />
    );

    // Should show Bitwarden indicator
    expect(screen.getByText('🔐 Bitwarden')).toBeInTheDocument();
    expect(screen.getByText(/This value will be resolved from Bitwarden/)).toBeInTheDocument();
  });

  it('shows error message when provided', () => {
    const mockOnChange = jest.fn();
    render(
      <SecretReferenceInput
        value=""
        onChange={mockOnChange}
        error="This field is required"
      />
    );

    expect(screen.getByText('This field is required')).toBeInTheDocument();
  });

  it('applies error styling when error is present', () => {
    const mockOnChange = jest.fn();
    render(
      <SecretReferenceInput
        value=""
        onChange={mockOnChange}
        error="Error message"
      />
    );

    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('border-red-500');
  });

  it('shows tip for non-reference values', () => {
    const mockOnChange = jest.fn();
    render(
      <SecretReferenceInput
        value="regular value"
        onChange={mockOnChange}
      />
    );

    expect(screen.getByText(/Tip: Use/)).toBeInTheDocument();
  });
});
