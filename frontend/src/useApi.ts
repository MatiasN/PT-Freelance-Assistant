import { useCallback, useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

interface Settled<T> {
  load: () => Promise<T>;
  version: number;
  data: T | null;
  error: string | null;
}

export function useApi<T>(load: () => Promise<T>): ApiState<T> {
  const [version, setVersion] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => {
        if (!cancelled) {
          setSettled({ load, version, data, error: null });
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          const error = caught instanceof Error ? caught.message : "Unexpected error";
          setSettled({ load, version, data: null, error });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [load, version]);

  const reload = useCallback(() => setVersion((current) => current + 1), []);
  const loading = settled?.load !== load || settled.version !== version;
  return { data: settled?.data ?? null, error: settled?.error ?? null, loading, reload };
}
