import { useCallback, useState } from 'react';

export function useAsync<T>() {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = useCallback(async (fn: () => Promise<T>) => {
    setLoading(true);
    setError('');
    try {
      const result = await fn();
      setData(result);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'unknown error');
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, setData, run };
}
