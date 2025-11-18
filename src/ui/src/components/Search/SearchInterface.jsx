import React, { useState } from 'react';
import {
  Container,
  Header,
  FormField,
  Input,
  Button,
  SpaceBetween,
  Box,
  Alert
} from '@cloudscape-design/components';
import { useSearch } from '../../hooks/useSearch';
import { SearchResults } from './SearchResults';

export const SearchInterface = () => {
  const [inputValue, setInputValue] = useState('');
  const { results, loading, error, query, search, clearResults } = useSearch();

  const handleSearch = () => {
    const trimmedValue = inputValue.trim();
    if (!trimmedValue) {
      return;
    }
    search(trimmedValue);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleSearch();
    }
  };

  const handleClear = () => {
    setInputValue('');
    clearResults();
  };

  return (
    <SpaceBetween size="l">
      <Container
        header={
          <Header variant="h2" description="Search your indexed documents">
            Knowledge Base Search
          </Header>
        }
      >
        <SpaceBetween size="m">
          <FormField
            label="Search query"
            description="Enter a question or search term"
          >
            <Input
              value={inputValue}
              onChange={({ detail }) => setInputValue(detail.value)}
              onKeyDown={handleKeyPress}
              placeholder="e.g., What information is in the documents?"
              disabled={loading}
              autoFocus
            />
          </FormField>

          <SpaceBetween direction="horizontal" size="xs">
            <Button
              variant="primary"
              onClick={handleSearch}
              loading={loading}
              disabled={!inputValue.trim() || loading}
            >
              Search
            </Button>
            <Button
              onClick={handleClear}
              disabled={results.length === 0 && !error && !inputValue}
            >
              Clear
            </Button>
          </SpaceBetween>

          {error && (
            <Alert type="error" header="Search failed">
              {error}
            </Alert>
          )}
        </SpaceBetween>
      </Container>

      {results.length > 0 && (
        <SearchResults results={results} query={query} />
      )}

      {!loading && results.length === 0 && query && !error && (
        <Container>
          <Box textAlign="center" padding="xxl">
            <Box variant="p" color="text-body-secondary">
              No results found for "{query}"
            </Box>
          </Box>
        </Container>
      )}
    </SpaceBetween>
  );
};
