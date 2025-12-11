'use client';

import { useEffect, useState } from 'react';
import { fetchContainerSummaries } from '@/lib/api/containers';
import { ContainerSummary } from '@/lib/types/containers';

export function useContainerSummaries() {
  const [summaries, setSummaries] = useState<ContainerSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const data = await fetchContainerSummaries();
        if (!cancelled) {
          setSummaries(data);
        }
      } catch {
        if (!cancelled) {
          setSummaries([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { summaries, isLoading };
}
