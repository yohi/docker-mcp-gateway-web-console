import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Toast from '../../../components/common/Toast';

describe('Toast', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('renders toast with message', () => {
    const onClose = jest.fn();
    render(<Toast message="Test message" type="info" onClose={onClose} />);

    expect(screen.getByText('Test message')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders success toast with correct styling', () => {
    const onClose = jest.fn();
    render(<Toast message="Success!" type="success" onClose={onClose} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveClass('bg-green-100', 'border-green-400', 'text-green-700');
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('renders error toast with correct styling', () => {
    const onClose = jest.fn();
    render(<Toast message="Error occurred" type="error" onClose={onClose} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveClass('bg-red-100', 'border-red-400', 'text-red-700');
    expect(screen.getByText('✕')).toBeInTheDocument();
  });

  it('renders warning toast with correct styling', () => {
    const onClose = jest.fn();
    render(<Toast message="Warning!" type="warning" onClose={onClose} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveClass('bg-yellow-100', 'border-yellow-400', 'text-yellow-700');
    expect(screen.getByText('⚠')).toBeInTheDocument();
  });

  it('renders info toast with correct styling', () => {
    const onClose = jest.fn();
    render(<Toast message="Info" type="info" onClose={onClose} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveClass('bg-blue-100', 'border-blue-400', 'text-blue-700');
    expect(screen.getByText('ℹ')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = jest.fn();
    render(<Toast message="Test" type="info" onClose={onClose} />);

    const closeButton = screen.getByLabelText('閉じる');
    closeButton.click();

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('auto-dismisses after specified duration', () => {
    const onClose = jest.fn();
    render(<Toast message="Test" type="info" duration={3000} onClose={onClose} />);

    expect(onClose).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not auto-dismiss when duration is 0', () => {
    const onClose = jest.fn();
    render(<Toast message="Test" type="info" duration={0} onClose={onClose} />);

    act(() => {
      jest.advanceTimersByTime(10000);
    });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('has proper accessibility attributes', () => {
    const onClose = jest.fn();
    render(<Toast message="Test" type="info" onClose={onClose} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
  });
});
