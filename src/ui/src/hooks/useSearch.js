import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';

const QUERY_KB = gql`
  query QueryKnowledgeBase($query: String!, $maxResults: Int) {
    queryKnowledgeBase(query: $query, maxResults: $maxResults) {
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
      const { data } = await client.graphql({
        query: QUERY_KB,
        variables: {
          query: searchQuery,
          maxResults
        }
      });

      if (data.queryKnowledgeBase.error) {
        setError(data.queryKnowledgeBase.error);
        setResults([]);
      } else {
        setResults(data.queryKnowledgeBase.results || []);
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
