import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ConfirmDialog from '../../../components/common/ConfirmDialog';

describe('ConfirmDialog', () => {
  const defaultProps = {
    title: 'Confirm Action',
    message: 'Are you sure?',
    onConfirm: jest.fn(),
    onCancel: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders dialog with title and message', () => {
    render(<ConfirmDialog {...defaultProps} />);

    expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('renders with default button text', () => {
    render(<ConfirmDialog {...defaultProps} />);

    expect(screen.getByText('確認')).toBeInTheDocument();
    expect(screen.getByText('キャンセル')).toBeInTheDocument();
  });

  it('renders with custom button text', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        confirmText="Delete"
        cancelText="Cancel"
      />
    );

    expect(screen.getByText('Delete')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', () => {
    render(<ConfirmDialog {...defaultProps} />);

    const confirmButton = screen.getByText('確認');
    fireEvent.click(confirmButton);

    expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
    expect(defaultProps.onCancel).not.toHaveBeenCalled();
  });

  it('calls onCancel when cancel button is clicked', () => {
    render(<ConfirmDialog {...defaultProps} />);

    const cancelButton = screen.getByText('キャンセル');
    fireEvent.click(cancelButton);

    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
    expect(defaultProps.onConfirm).not.toHaveBeenCalled();
  });

  it('calls onCancel when backdrop is clicked', () => {
    render(<ConfirmDialog {...defaultProps} />);

    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog);

    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
    expect(defaultProps.onConfirm).not.toHaveBeenCalled();
  });

  it('does not call onCancel when dialog content is clicked', () => {
    render(<ConfirmDialog {...defaultProps} />);

    const title = screen.getByText('Confirm Action');
    fireEvent.click(title);

    expect(defaultProps.onCancel).not.toHaveBeenCalled();
  });

  it('renders danger type with red button', () => {
    render(<ConfirmDialog {...defaultProps} type="danger" />);

    const confirmButton = screen.getByText('確認');
    expect(confirmButton).toHaveClass('bg-red-500', 'hover:bg-red-700');
  });

  it('renders warning type with yellow button', () => {
    render(<ConfirmDialog {...defaultProps} type="warning" />);

    const confirmButton = screen.getByText('確認');
    expect(confirmButton).toHaveClass('bg-yellow-500', 'hover:bg-yellow-700');
  });

  it('renders info type with blue button', () => {
    render(<ConfirmDialog {...defaultProps} type="info" />);

    const confirmButton = screen.getByText('確認');
    expect(confirmButton).toHaveClass('bg-blue-500', 'hover:bg-blue-700');
  });

  it('has proper accessibility attributes', () => {
    render(<ConfirmDialog {...defaultProps} />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'dialog-title');
    expect(dialog).toHaveAttribute('aria-describedby', 'dialog-message');

    const title = screen.getByText('Confirm Action');
    expect(title).toHaveAttribute('id', 'dialog-title');

    const message = screen.getByText('Are you sure?');
    expect(message).toHaveAttribute('id', 'dialog-message');
  });
});
