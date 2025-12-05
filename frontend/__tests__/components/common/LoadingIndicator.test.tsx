import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import LoadingIndicator from '../../../components/common/LoadingIndicator';

describe('LoadingIndicator', () => {
  it('renders loading spinner', () => {
    render(<LoadingIndicator />);

    const spinner = screen.getByRole('status');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveAttribute('aria-label', '読み込み中');
  });

  it('renders with message', () => {
    render(<LoadingIndicator message="Loading data..." />);

    expect(screen.getByText('Loading data...')).toBeInTheDocument();
  });

  it('renders small size', () => {
    render(<LoadingIndicator size="small" />);

    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-6', 'h-6', 'border-2');
  });

  it('renders medium size', () => {
    render(<LoadingIndicator size="medium" />);

    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-10', 'h-10', 'border-2');
  });

  it('renders large size', () => {
    render(<LoadingIndicator size="large" />);

    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-16', 'h-16', 'border-4');
  });

  it('renders as inline by default', () => {
    render(<LoadingIndicator />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders as full-screen overlay when specified', () => {
    render(<LoadingIndicator fullScreen />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', '読み込み中');
    expect(dialog).toHaveClass('fixed', 'inset-0', 'bg-black', 'bg-opacity-50');
  });

  it('renders full-screen with message', () => {
    render(<LoadingIndicator fullScreen message="Processing..." />);

    expect(screen.getByText('Processing...')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
