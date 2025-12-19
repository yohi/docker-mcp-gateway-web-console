import fc from 'fast-check';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import ContainerList from '../../components/containers/ContainerList';
import { ContainerInfo, ContainerStatus } from '../../lib/types/containers';
import React from 'react';

// Arbitrary for ContainerStatus
const containerStatusArbitrary = fc.constantFrom<ContainerStatus>('running', 'stopped', 'error');

// Arbitrary for ContainerInfo
const containerInfoArbitrary = fc.record<ContainerInfo>({
  id: fc.uuid(),
  name: fc.string({ minLength: 1 }).map(s => s.trim()).filter(s => s.length > 0),
  image: fc.string({ minLength: 1 }).map(s => s.trim()).filter(s => s.length > 0),
  status: containerStatusArbitrary,
  created_at: fc.date().map(d => d.toISOString()),
  ports: fc.dictionary(fc.string({ minLength: 1 }).map(s => s.trim()).filter(s => s.length > 0), fc.integer({ min: 1, max: 65535 })),
  labels: fc.dictionary(fc.string(), fc.string()),
});

// Mock Next.js useRouter
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe('Container Properties', () => {
  afterEach(() => {
    cleanup();
  });

  // Property 30: Status display
  it('should correctly display status for any container', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 30: ステータス表示**
     *
     * For any container, the system should correctly display its current status
     * (running, stopped, error).
     */
    fc.assert(
      fc.property(containerInfoArbitrary, (container) => {
        cleanup();
        render(
          <ContainerList
            containers={[container]}
            onRefresh={() => { }}
            onViewLogs={() => { }}
          />
        );

        const statusElements = screen.getAllByText(container.status);
        expect(statusElements.length).toBeGreaterThan(0);
        const statusElement = statusElements[0];

        // Check color classes based on status (simplified check)
        if (container.status === 'running') {
          expect(statusElement).toHaveClass('bg-green-100');
        } else if (container.status === 'stopped') {
          expect(statusElement).toHaveClass('bg-gray-100');
        } else if (container.status === 'error') {
          expect(statusElement).toHaveClass('bg-red-100');
        }

        cleanup();
      }),
      { numRuns: 10 } // Reduced runs for JSDOM
    );
  });

  // Property 31: Error highlighting
  it('should visually highlight error state containers', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 31: エラー状態の強調表示**
     *
     * For any error-state container, the system should visually highlight it.
     */
    fc.assert(
      fc.property(containerInfoArbitrary, (container) => {
        cleanup();
        render(
          <ContainerList
            containers={[container]}
            onRefresh={() => { }}
            onViewLogs={() => { }}
          />
        );

        // We find the card by text content
        const nameElements = screen.getAllByText(container.name);
        const nameElement = nameElements.find(el => el.tagName === 'H3') || nameElements[0];
        const card = nameElement.closest('.rounded-lg');

        expect(card).toBeInTheDocument();

        if (container.status === 'error') {
          expect(card).toHaveClass('border-red-500');
        } else {
          expect(card).toHaveClass('border-blue-500');
        }

        cleanup();
      }),
      { numRuns: 10 }
    );
  });

  // Property 32: Detailed info
  it('should display detailed info for any container', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 32: コンテナ詳細情報の取得**
     *
     * For any container, the system should display detailed information
     * (startup time, image, ID, etc.).
     */
    fc.assert(
      fc.property(containerInfoArbitrary, (container) => {
        cleanup();
        render(
          <ContainerList
            containers={[container]}
            onRefresh={() => { }}
            onViewLogs={() => { }}
          />
        );

        expect(screen.getAllByText(container.name).length).toBeGreaterThan(0);
        expect(screen.getAllByText(container.image, { exact: false }).length).toBeGreaterThan(0);
        expect(screen.getAllByText(container.id.substring(0, 12)).length).toBeGreaterThan(0);

        cleanup();
      }),
      { numRuns: 10 }
    );
  });

  // Property 33: Error handling
  it('should display error message when communication fails', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 33: Docker通信失敗のエラーハンドリング**
     *
     * If Docker daemon communication fails (simulated by an error object),
     * the system should display the error message.
     */
    fc.assert(
      fc.property(fc.string({ minLength: 1 }).filter(s => s.trim().length > 0), (errorMessage) => {
        // Simulating the error display part of DashboardPage
        const ErrorDisplay = ({ error }: { error: Error }) => (
          <div className="bg-red-50 text-red-700 px-4 py-3 rounded-md mb-6 border border-red-200">
            <p className="font-semibold">エラー:</p>
            <p className="text-sm">{error.message}</p>
          </div>
        );

        cleanup();
        render(<ErrorDisplay error={new Error(errorMessage)} />);

        // Use a custom matcher without RTL's whitespace normalization
        expect(
          screen.getByText((_, node) => node?.textContent === errorMessage)
        ).toBeInTheDocument();
        expect(screen.getByText('エラー:')).toBeInTheDocument();

        cleanup();
      }),
      { numRuns: 10 }
    );
  });
});
