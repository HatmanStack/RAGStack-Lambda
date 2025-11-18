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

export const SearchResults = ({ results, query }) => {
  const getDocumentIdFromSource = (source) => {
    // Extract document ID from S3 URI (format: s3://bucket/document-id/filename)
    if (!source || typeof source !== 'string') {
      return 'Unknown';
    }
    const match = source.match(/([^/]+)\/[^/]+$/);
    return match ? match[1] : 'Unknown';
  };

  const getRelevanceColor = (score) => {
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
                  <Box fontFamily="monospace" fontSize="body-s" color="text-body-secondary" style={{ wordBreak: 'break-all' }}>
                    {result.source}
                  </Box>
                </Box>
              )}
            </SpaceBetween>
          </ExpandableSection>
        ))}
      </SpaceBetween>
    </Container>
  );
};
