'use client';

import React from 'react';
import Navigation from './Navigation';

interface MainLayoutProps {
  children: React.ReactNode;
}

/**
 * MainLayout component provides the main application layout structure
 * with navigation and responsive design.
 * 
 * This component wraps authenticated pages and provides:
 * - Top navigation bar
 * - Responsive layout
 * - Consistent spacing and styling
 */
export default function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Navigation />
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}
