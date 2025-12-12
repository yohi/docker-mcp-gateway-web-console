'use client';

import { useEffect, useState } from 'react';
import { fetchContainerSummaries } from '@/lib/api/containers';
import { ContainerSummary } from '@/lib/types/containers';

export function useContainerSummaries() {
  const [summaries, setSummaries] = useState<ContainerSummary[]>([]);
  const [warning, setWarning] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const { containers, warning } = await fetchContainerSummaries();
        if (!cancelled) {
          setSummaries(containers);
          setWarning(warning ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          setSummaries([]);
          const message =
            err instanceof Error ? err.message : typeof err === 'string' ? err : String(err);
          setWarning(message);
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

  return { summaries, warning, isLoading };
}
