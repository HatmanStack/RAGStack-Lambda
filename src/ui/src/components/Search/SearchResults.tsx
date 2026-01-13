import React from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Container,
  Header,
  Box,
  SpaceBetween,
  ExpandableSection,
  Badge
} from '@cloudscape-design/components';
import type { SearchResult } from '../../hooks/useSearch';

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
}

type BadgeColor = 'blue' | 'grey' | 'green' | 'red';

export const SearchResults = ({ results, query }: SearchResultsProps) => {
  const getDocumentIdFromSource = (source: string): string => {
    // Extract document ID from S3 URI (format: s3://bucket/document-id/filename)
    if (!source || typeof source !== 'string') {
      return 'Unknown';
    }
    const match = source.match(/([^/]+)\/[^/]+$/);
    return match ? match[1] : 'Unknown';
  };

  const getRelevanceColor = (score: number): BadgeColor => {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'blue';
    return 'grey';
  };

  return (
    <Container
      header={
        <Header variant="h2" counter={`(${results.length})`}>
          Search Results for "{query}"
        </Header>
      }
    >
      <SpaceBetween size="m">
        {results.map((result, index) => (
          <ExpandableSection
            key={index}
            headerText={
              <Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Box variant="span">Result {index + 1}</Box>
                  {result.score && (
                    <Badge color={getRelevanceColor(result.score)}>
                      {(result.score * 100).toFixed(0)}% relevant
                    </Badge>
                  )}
                </SpaceBetween>
              </Box>
            }
            defaultExpanded={index === 0}
          >
            <SpaceBetween size="m">
              <Box>
                <ReactMarkdown>
                  {result.content}
                </ReactMarkdown>
              </Box>

              {result.source && (
                <Box>
                  <Box variant="awsui-key-label">Source</Box>
                  <Box fontSize="body-s" color="text-body-secondary">
                    Document: {getDocumentIdFromSource(result.source)}
                  </Box>
                  <div style={{ fontFamily: 'monospace', fontSize: '12px', color: '#5f6b7a', wordBreak: 'break-all' }}>
                    {result.source}
                  </div>
                </Box>
              )}
            </SpaceBetween>
          </ExpandableSection>
        ))}
      </SpaceBetween>
    </Container>
  );
};
