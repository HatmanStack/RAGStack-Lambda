import { useState, useEffect, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { getKeyLibrary } from '../graphql/queries/getKeyLibrary';
import type { GqlResponse } from '../types/graphql';

interface MetadataKey {
  keyName: string;
  dataType: string;
  sampleValues: string[];
  occurrenceCount: number;
  status: string;
}

interface UseKeyLibraryReturn {
  keys: MetadataKey[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const client = generateClient();

export function useKeyLibrary(): UseKeyLibraryReturn {
  const [keys, setKeys] = useState<MetadataKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = (await client.graphql({
        query: getKeyLibrary,
      })) as GqlResponse;

      const keyLibrary = response.data?.getKeyLibrary;

      if (Array.isArray(keyLibrary)) {
        setKeys(
          keyLibrary.map((key: Record<string, unknown>) => ({
            keyName: (key.keyName as string) || '',
            dataType: (key.dataType as string) || 'string',
            sampleValues: (key.sampleValues as string[]) || [],
            occurrenceCount: (key.occurrenceCount as number) || 0,
            status: (key.status as string) || 'active',
          }))
        );
      } else {
        setKeys([]);
      }
    } catch (err) {
      console.error('Failed to fetch key library:', err);
      setError((err as Error).message);
      setKeys([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  return {
    keys,
    loading,
    error,
    refetch: fetchKeys,
  };
}
