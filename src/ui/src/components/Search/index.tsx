import React from 'react';
import { ContentLayout, Header, SpaceBetween } from '@cloudscape-design/components';
import { SearchInterface } from './SearchInterface';
import { MetadataPanel } from './MetadataPanel';
import { ApiDocs } from '../common/ApiDocs';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

const graphqlQuery = `query SearchKnowledgeBase($query: String!, $maxResults: Int) {
  searchKnowledgeBase(query: $query, maxResults: $maxResults) {
    results { content, source, score }
  }
}`;

const jsExample = `const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: \`${graphqlQuery}\`,
    variables: { query: 'your search', maxResults: 5 }
  })
});
const { data } = await res.json();`;

const curlExample = `curl -X POST 'ENDPOINT' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: API_KEY' \\
  -d '{"query": "...", "variables": {"query": "search text"}}'`;

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

        <MetadataPanel />

        {graphqlEndpoint && (
          <ApiDocs
            title="Search API (Server-side)"
            description="For backend integrations, MCP servers, and scripts."
            endpoint={graphqlEndpoint}
            examples={[
              { id: 'graphql', label: 'GraphQL', code: graphqlQuery },
              { id: 'js', label: 'JavaScript', code: jsExample },
              { id: 'curl', label: 'cURL', code: curlExample },
            ]}
          />
        )}
      </SpaceBetween>
    </ContentLayout>
  );
};
