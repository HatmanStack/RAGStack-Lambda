import { useState, useCallback, useEffect } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import type { GqlResponse } from '../types/graphql';

interface MetadataStatsResult {
  keys?: MetadataKeyStats[];
  totalKeys?: number;
  lastAnalyzed?: string | null;
  error?: string;
}

interface FilterExamplesResult {
  examples?: FilterExample[];
  totalExamples?: number;
  lastGenerated?: string | null;
  error?: string;
}

interface AnalyzeResult {
  success?: boolean;
  vectorsSampled?: number;
  keysAnalyzed?: number;
  examplesGenerated?: number;
  executionTimeMs?: number;
  error?: string;
}

const GET_METADATA_STATS = gql`
  query GetMetadataStats {
    getMetadataStats {
      keys {
        keyName
        dataType
        occurrenceCount
        sampleValues
        lastAnalyzed
        status
      }
      totalKeys
      lastAnalyzed
      error
    }
  }
`;

const GET_FILTER_EXAMPLES = gql`
  query GetFilterExamples {
    getFilterExamples {
      examples {
        name
        description
        useCase
        filter
      }
      totalExamples
      lastGenerated
      error
    }
  }
`;

const ANALYZE_METADATA = gql`
  mutation AnalyzeMetadata {
    analyzeMetadata {
      success
      vectorsSampled
      keysAnalyzed
      examplesGenerated
      executionTimeMs
      error
    }
  }
`;

export interface MetadataKeyStats {
  keyName: string;
  dataType: string;
  occurrenceCount: number;
  sampleValues: string[];
  lastAnalyzed: string | null;
  status: string;
}

export interface FilterExample {
  name: string;
  description: string;
  useCase: string;
  filter: string; // JSON string
}

export interface MetadataAnalysisResult {
  success: boolean;
  vectorsSampled: number;
  keysAnalyzed: number;
  examplesGenerated: number;
  executionTimeMs: number;
  error?: string;
}

const client = generateClient();

export const useMetadataStats = () => {
  const [stats, setStats] = useState<MetadataKeyStats[]>([]);
  const [totalKeys, setTotalKeys] = useState(0);
  const [lastAnalyzed, setLastAnalyzed] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = (await client.graphql({
        query: GET_METADATA_STATS as unknown as string,
      })) as GqlResponse;

      const result = response.data?.getMetadataStats as MetadataStatsResult | undefined;
      if (result?.error) {
        setError(result.error);
        setStats([]);
      } else {
        setStats(result?.keys || []);
        setTotalKeys(result?.totalKeys || 0);
        setLastAnalyzed(result?.lastAnalyzed || null);
      }
    } catch (err) {
      console.error('Failed to fetch metadata stats:', err);
      setError((err as Error).message);
      setStats([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    totalKeys,
    lastAnalyzed,
    loading,
    error,
    refetch: fetchStats,
  };
};

export const useFilterExamples = () => {
  const [examples, setExamples] = useState<FilterExample[]>([]);
  const [totalExamples, setTotalExamples] = useState(0);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchExamples = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = (await client.graphql({
        query: GET_FILTER_EXAMPLES as unknown as string,
      })) as GqlResponse;

      const result = response.data?.getFilterExamples as FilterExamplesResult | undefined;
      if (result?.error) {
        setError(result.error);
        setExamples([]);
      } else {
        setExamples(result?.examples || []);
        setTotalExamples(result?.totalExamples || 0);
        setLastGenerated(result?.lastGenerated || null);
      }
    } catch (err) {
      console.error('Failed to fetch filter examples:', err);
      setError((err as Error).message);
      setExamples([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchExamples();
  }, [fetchExamples]);

  return {
    examples,
    totalExamples,
    lastGenerated,
    loading,
    error,
    refetch: fetchExamples,
  };
};

export const useMetadataAnalyzer = () => {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MetadataAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (): Promise<MetadataAnalysisResult | null> => {
    setAnalyzing(true);
    setError(null);
    setResult(null);

    try {
      const response = (await client.graphql({
        query: ANALYZE_METADATA as unknown as string,
      })) as GqlResponse;

      const analysisResult = response.data?.analyzeMetadata as AnalyzeResult | undefined;
      if (analysisResult?.error) {
        setError(analysisResult.error);
        return null;
      }

      const typedResult: MetadataAnalysisResult = {
        success: analysisResult?.success ?? false,
        vectorsSampled: analysisResult?.vectorsSampled ?? 0,
        keysAnalyzed: analysisResult?.keysAnalyzed ?? 0,
        examplesGenerated: analysisResult?.examplesGenerated ?? 0,
        executionTimeMs: analysisResult?.executionTimeMs ?? 0,
      };
      setResult(typedResult);
      return typedResult;
    } catch (err) {
      console.error('Metadata analysis failed:', err);
      const errorMessage = (err as Error).message;
      setError(errorMessage);
      return null;
    } finally {
      setAnalyzing(false);
    }
  }, []);

  return {
    analyze,
    analyzing,
    result,
    error,
  };
};
