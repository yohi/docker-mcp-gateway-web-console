import useSWR from 'swr';
import { useSession } from '../contexts/SessionContext';
import { fetchContainers } from '../lib/api/containers';
import { ContainerInfo } from '../lib/types/containers';

export function useContainers() {
    const { session } = useSession();

    const { data, error, mutate } = useSWR(
        session ? 'containers' : null,
        () => fetchContainers(true),
        {
            refreshInterval: 5000,
            revalidateOnFocus: true,
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
