import { renderHook } from '@testing-library/react';
import { useContainers } from '../../hooks/useContainers';

// Mock dependencies
const mockUseSWR = jest.fn();
jest.mock('swr', () => ({
    __esModule: true,
    default: (...args: any[]) => mockUseSWR(...args),
}));

jest.mock('../../lib/api/containers');
jest.mock('../../contexts/SessionContext', () => ({
    useSession: () => ({ session: { id: 'test-session' } }),
}));

describe('useContainers', () => {
    const mockMutate = jest.fn();

    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('returns containers data when successful', () => {
        const mockContainers = [{ container_id: '1', name: 'test', image: 'test-image' }];
        mockUseSWR.mockReturnValue({
            data: { containers: mockContainers },
            error: undefined,
            mutate: mockMutate,
        });

        const { result } = renderHook(() => useContainers());

        expect(result.current.containers).toEqual(mockContainers);
        expect(result.current.isLoading).toBe(false);
        expect(result.current.isError).toBe(false);
    });

    it('handles loading state', () => {
        mockUseSWR.mockReturnValue({
            data: undefined,
            error: undefined,
            mutate: mockMutate,
        });

        const { result } = renderHook(() => useContainers());

        expect(result.current.containers).toEqual([]);
        expect(result.current.isLoading).toBe(true);
    });

    it('handles error state', () => {
        const error = new Error('Failed');
        mockUseSWR.mockReturnValue({
            data: undefined,
            error: error,
            mutate: mockMutate,
        });

        const { result } = renderHook(() => useContainers());

        expect(result.current.isLoading).toBe(false);
        expect(result.current.isError).toBe(true);
        expect(result.current.error).toBe(error);
    });

    it('exposes refresh function', () => {
        mockUseSWR.mockReturnValue({
            data: { containers: [] },
            mutate: mockMutate,
        });

        const { result } = renderHook(() => useContainers());
        result.current.refresh();

        expect(mockMutate).toHaveBeenCalled();
    });
});
