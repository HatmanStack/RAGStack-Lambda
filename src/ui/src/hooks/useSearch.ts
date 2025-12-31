import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import type { GqlResponse } from '../types/graphql';

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
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');

  const search = useCallback(async (searchQuery, maxResults = 5) => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    setLoading(true);
    setError(null);
    setQuery(searchQuery);

    try {
      const response = await client.graphql({
        query: SEARCH_KB as any,
        variables: {
          query: searchQuery,
          maxResults
        }
      }) as GqlResponse;

      const searchResult = response.data?.searchKnowledgeBase as { error?: string; results?: unknown[] } | undefined;
      if (searchResult?.error) {
        setError(searchResult.error);
        setResults([]);
      } else {
        setResults(searchResult?.results || []);
      }

    } catch (err) {
      console.error('Search failed:', err);
      setError(err.message);
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
