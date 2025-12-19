import React from 'react';
import InspectorPage from '@/app/inspector/[containerId]/page';
import InspectorPageClient from '@/app/inspector/[containerId]/InspectorPageClient';
import { resolveInspectorRouteParams } from '@/app/inspector/[containerId]/routeParams';
import { notFound } from 'next/navigation';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({ push: jest.fn(), replace: jest.fn() })),
  useSearchParams: jest.fn(() => new URLSearchParams()),
  useParams: jest.fn(() => ({ containerId: 'hook-container' })),
  notFound: jest.fn(),
}));

jest.mock('@/app/inspector/[containerId]/InspectorPageClient', () => ({
  __esModule: true,
  default: jest.fn(() => null),
}));

const mockInspectorClient = InspectorPageClient as jest.Mock;
const mockNotFound = notFound as jest.Mock;

describe('resolveInspectorRouteParams', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('awaits promise-based params and searchParams inputs', async () => {
    const result = await resolveInspectorRouteParams(
      Promise.resolve({ containerId: 'abc-123' }),
      Promise.resolve(new URLSearchParams({ name: 'demo-name' }))
    );

    expect(result).toEqual({
      containerId: 'abc-123',
      containerName: 'demo-name',
    });
  });

  it('normalizes array-based params and searchParams values', async () => {
    const result = await resolveInspectorRouteParams(
      { containerId: ['first-id', 'extra'] } as any,
      { name: ['first-name', 'second-name'] }
    );

    expect(result).toEqual({
      containerId: 'first-id',
      containerName: 'first-name',
    });
  });
});

describe('InspectorPage (Next.js 15 params compatibility)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('passes resolved params to the client component', async () => {
    const element = await InspectorPage({
      params: Promise.resolve({ containerId: 'page-123' }),
      searchParams: Promise.resolve(new URLSearchParams({ name: 'page-name' })),
    } as any);

    expect(element?.props).toMatchObject({
      containerId: 'page-123',
      containerName: 'page-name',
    });
    expect(element?.type).toBe(mockInspectorClient);
  });

  it('invokes notFound when containerId is missing', async () => {
    mockNotFound.mockImplementation(() => {
      throw new Error('NOT_FOUND');
    });

    await expect(
      InspectorPage({
        params: Promise.resolve({}),
        searchParams: Promise.resolve(undefined),
      } as any)
    ).rejects.toThrow('NOT_FOUND');

    expect(mockNotFound).toHaveBeenCalled();
  });
});
