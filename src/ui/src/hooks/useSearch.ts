import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import type { GqlResponse } from '../types/graphql';

export interface SearchResult {
  content: string;
  source: string;
  score: number;
}

const SEARCH_KB = gql`
  query SearchKnowledgeBase($query: String!, $maxResults: Int) {
    searchKnowledgeBase(query: $query, maxResults: $maxResults) {
      query
      results {
        content
        source
        score
      }
      total
      error
    }
  }
`;

const client = generateClient();

export const useSearch = () => {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const search = useCallback(async (searchQuery: string, maxResults = 5) => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    setLoading(true);
    setError(null);
    setQuery(searchQuery);

    try {
      const response = await client.graphql({
        query: SEARCH_KB as ReturnType<typeof gql>,
        variables: {
          query: searchQuery,
          maxResults
        }
      }) as GqlResponse;

      const searchResult = response.data?.searchKnowledgeBase as { error?: string; results?: SearchResult[] } | undefined;
      if (searchResult?.error) {
        setError(searchResult.error);
        setResults([]);
      } else {
        setResults(searchResult?.results || []);
      }

    } catch (err) {
      console.error('Search failed:', err);
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearResults = useCallback(() => {
    setResults([]);
    setQuery('');
    setError(null);
  }, []);

  return {
    results,
    loading,
    error,
    query,
    search,
    clearResults
  };
};
