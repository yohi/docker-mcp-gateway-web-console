import useSWR from 'swr';
import { useSession } from '../contexts/SessionContext';
import { fetchContainers } from '../lib/api/containers';
import { ContainerInfo } from '../lib/types/containers';

export function useContainers(refreshIntervalMs: number | null = null) {
    const { session } = useSession();
    const refreshInterval = refreshIntervalMs ?? 0; // デフォルトは自動ポーリングなし

    const { data, error, mutate } = useSWR(
        session ? 'containers' : null,
        () => fetchContainers(true),
        {
            refreshInterval,
            revalidateOnFocus: false,
        }
    );

    return {
        containers: (data?.containers || []) as ContainerInfo[],
        isLoading: !data && !error,
        isError: !!error,
        error,
        refresh: mutate,
    };
}
