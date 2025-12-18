import React from 'react';
import {
  ContentLayout,
  Header,
  SpaceBetween,
  Container,
  Box,
  CopyToClipboard,
  ExpandableSection,
} from '@cloudscape-design/components';
import { SearchInterface } from './SearchInterface';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

const searchQuery = `query SearchKnowledgeBase($query: String!, $maxResults: Int) {
  searchKnowledgeBase(query: $query, maxResults: $maxResults) {
    query
    total
    error
    results {
      content
      source
      score
    }
  }
}`;

const curlExample = graphqlEndpoint
  ? `curl -X POST '${graphqlEndpoint}' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: YOUR_API_KEY' \\
  -d '{
    "query": "${searchQuery.replace(/\n/g, '\\n').replace(/"/g, '\\"')}",
    "variables": { "query": "your search query", "maxResults": 10 }
  }'`
  : '';

const jsExample = graphqlEndpoint
  ? `const response = await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'
  },
  body: JSON.stringify({
    query: \`${searchQuery}\`,
    variables: { query: 'your search query', maxResults: 10 }
  })
});
const { data } = await response.json();
console.log(data.searchKnowledgeBase.results);`
  : '';

export const Search = () => {
  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Query your Knowledge Base">
          Search Documents
        </Header>
      }
    >
      <SpaceBetween size="l">
        <SearchInterface />

        {graphqlEndpoint && (
          <Container>
            <ExpandableSection
              headerText="Use Search API in Your Application"
              variant="footer"
            >
              <SpaceBetween size="m">
                <Box variant="p">
                  Integrate Knowledge Base search into your applications using the GraphQL API.
                  Authentication uses the same Cognito user pool or API key as the chat interface.
                </Box>

                <Box variant="h4">GraphQL Endpoint</Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      padding: '8px 12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      wordBreak: 'break-all',
                    }}
                  >
                    {graphqlEndpoint}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={graphqlEndpoint}
                  copyButtonText="Copy Endpoint"
                  copySuccessText="Copied!"
                />

                <Box variant="h4">GraphQL Query</Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                    }}
                  >
                    {searchQuery}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={searchQuery}
                  copyButtonText="Copy Query"
                  copySuccessText="Copied!"
                />

                <Box variant="h4">JavaScript Example</Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                    }}
                  >
                    {jsExample}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={jsExample}
                  copyButtonText="Copy JavaScript"
                  copySuccessText="Copied!"
                />

                <Box variant="h4">cURL Example</Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                    }}
                  >
                    {curlExample}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={curlExample}
                  copyButtonText="Copy cURL"
                  copySuccessText="Copied!"
                />

                <Box variant="small" color="text-body-secondary">
                  Replace YOUR_API_KEY with your AppSync API key from the AWS Console,
                  or use Cognito authentication tokens for user-scoped access.
                </Box>
              </SpaceBetween>
            </ExpandableSection>
          </Container>
        )}
      </SpaceBetween>
    </ContentLayout>
  );
};
