import React from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Container,
  Header,
  Box,
  SpaceBetween,
  ExpandableSection,
  Badge,
  Link
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
                  <SpaceBetween direction="horizontal" size="s">
                    <Box fontSize="body-s" color="text-body-secondary">
                      {result.isSegment ? 'Video Segment' : (result.filename || `Document: ${result.documentId || getDocumentIdFromSource(result.source)}`)}
                    </Box>
                    {result.isSegment && result.timestampStart !== undefined && (
                      <Badge color="blue">
                        {Math.floor(result.timestampStart / 60)}:{String(Math.floor(result.timestampStart % 60)).padStart(2, '0')}
                      </Badge>
                    )}
                    {result.isSegment && result.segmentUrl && (
                      <Link href={result.segmentUrl} external fontSize="body-s">
                        Jump to Clip
                      </Link>
                    )}
                    {result.isSegment && result.documentUrl && (
                      <Link href={result.documentUrl} external fontSize="body-s">
                        Full Video
                      </Link>
                    )}
                    {!result.isSegment && !result.isScraped && result.documentUrl && (
                      <Link href={result.documentUrl} external fontSize="body-s">
                        Download
                      </Link>
                    )}
                    {result.isScraped && result.sourceUrl && (
                      <Link href={result.sourceUrl} external fontSize="body-s">
                        View Original
                      </Link>
                    )}
                  </SpaceBetween>
                  {!result.documentUrl && !result.segmentUrl && result.documentAccessAllowed === false && (
                    <Box fontSize="body-s" color="text-status-inactive">
                      Document download disabled
                    </Box>
                  )}
                </Box>
              )}
            </SpaceBetween>
          </ExpandableSection>
        ))}
      </SpaceBetween>
    </Container>
  );
};
