'use client';

import React from 'react';

export interface LoadingIndicatorProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
  fullScreen?: boolean;
}

/**
 * Loading indicator component for displaying progress
 * Can be used inline or as a full-screen overlay
 */
export default function LoadingIndicator({
  size = 'medium',
  message,
  fullScreen = false,
}: LoadingIndicatorProps) {
  const getSizeClasses = () => {
    switch (size) {
      case 'small':
        return 'w-6 h-6 border-2';
      case 'large':
        return 'w-16 h-16 border-4';
      case 'medium':
      default:
        return 'w-10 h-10 border-2';
    }
  };

  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3">
      <div
        className={`${getSizeClasses()} border-blue-500 border-t-transparent rounded-full animate-spin`}
        role="status"
        aria-label="読み込み中"
      />
      {message && (
        <p className="text-sm text-gray-600 font-medium">{message}</p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div
        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        role="dialog"
        aria-modal="true"
        aria-label="読み込み中"
      >
        <div className="bg-white rounded-lg p-8 shadow-xl">
          {spinner}
        </div>
      </div>
    );
  }

  return spinner;
}
