import React, { useState } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Alert,
  Box,
  CopyToClipboard,
  ExpandableSection,
} from '@cloudscape-design/components';
import { ScrapeForm } from './ScrapeForm';
import { useScrape } from '../../hooks/useScrape';
import { useNavigate } from 'react-router-dom';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

const startScrapeMutation = `mutation StartScrape($input: StartScrapeInput!) {
  startScrape(input: $input) {
    jobId
    baseUrl
    title
    status
    createdAt
  }
}`;

const getScrapeJobQuery = `query GetScrapeJob($jobId: ID!) {
  getScrapeJob(jobId: $jobId) {
    job {
      jobId
      baseUrl
      title
      status
      totalUrls
      processedCount
      failedCount
    }
    pages {
      url
      title
      status
      documentId
    }
  }
}`;

const listScrapeJobsQuery = `query ListScrapeJobs($limit: Int, $nextToken: String) {
  listScrapeJobs(limit: $limit, nextToken: $nextToken) {
    items {
      jobId
      baseUrl
      title
      status
      totalUrls
      processedCount
      createdAt
    }
    nextToken
  }
}`;

const jsExample = graphqlEndpoint
  ? `// Start a scrape job
const response = await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'  // or 'Authorization': 'Bearer COGNITO_TOKEN'
  },
  body: JSON.stringify({
    query: \`${startScrapeMutation}\`,
    variables: {
      input: {
        url: 'https://example.com/docs',
        maxPages: 50,
        maxDepth: 3,
        scope: 'HOSTNAME',  // SUBPAGES | HOSTNAME | DOMAIN
        scrapeMode: 'AUTO'  // FAST | FULL | AUTO
      }
    }
  })
});
const { data } = await response.json();
console.log('Job started:', data.startScrape.jobId);

// Poll for job status
const statusResponse = await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'
  },
  body: JSON.stringify({
    query: \`${getScrapeJobQuery}\`,
    variables: { jobId: data.startScrape.jobId }
  })
});`
  : '';

export const Scrape = () => {
  const navigate = useNavigate();
  const { startScrape, checkDuplicate, loading: hookLoading, error: hookError, clearError } = useScrape();
  const [duplicateWarning, setDuplicateWarning] = useState(null);
  const [pendingConfig, setPendingConfig] = useState(null);

  const handleSubmit = async (config) => {
    // If force flag is set (from "proceed anyway"), skip duplicate check
    if (!config.force) {
      // Check for duplicate
      const duplicate = await checkDuplicate(config.url);
      if (duplicate?.exists) {
        setDuplicateWarning({
          date: new Date(duplicate.lastScrapedAt).toLocaleDateString(),
          jobId: duplicate.jobId,
          title: duplicate.title
        });
        setPendingConfig(config);
        return;
      }
    }

    // Clear warning and proceed with scrape
    setDuplicateWarning(null);
    setPendingConfig(null);

    const scrapeInput = {
      url: config.url,
      maxPages: config.maxPages,
      maxDepth: config.maxDepth,
      scope: config.scope,
      includePatterns: config.includePatterns,
      excludePatterns: config.excludePatterns,
      scrapeMode: config.scrapeMode,
      cookies: config.cookies,
      forceRescrape: config.forceRescrape
    };


    try {
      const job = await startScrape(scrapeInput);

      // Navigate to dashboard to see the new job
      if (job?.jobId) {
        navigate('/');
      }
    } catch (err) {
      // Error is handled by hook, but log details here too
      console.error('[Scrape] Scrape submission failed:', err);
      console.error('[Scrape] Error type:', err.constructor.name);
      console.error('[Scrape] Error message:', err.message);
      if (err.errors) {
        console.error('[Scrape] GraphQL errors:', JSON.stringify(err.errors, null, 2));
      }
    }
  };

  const handleProceedAnyway = async () => {
    if (pendingConfig) {
      await handleSubmit({ ...pendingConfig, force: true });
    }
  };

  const handleDismissWarning = () => {
    setDuplicateWarning(null);
    setPendingConfig(null);
  };

  return (
    <SpaceBetween size="l">
      {hookError && (
        <Alert
          type="error"
          dismissible
          onDismiss={clearError}
          header="Scrape failed"
        >
          {hookError}
          <br />
          <small style={{ color: '#666' }}>Check browser console (F12) for details</small>
        </Alert>
      )}
      <Container header={<Header variant="h1">Scrape Website</Header>}>
        <ScrapeForm
          onSubmit={handleSubmit}
          onProceedAnyway={handleProceedAnyway}
          loading={hookLoading}
          duplicateWarning={duplicateWarning}
          onDismissWarning={handleDismissWarning}
        />
      </Container>

      {graphqlEndpoint && (
        <Container>
          <ExpandableSection
            headerText="Use Scrape API in Your Application"
            variant="footer"
          >
            <SpaceBetween size="m">
              <Box variant="p">
                Programmatically scrape websites using the GraphQL API.
                Authentication uses API key or Cognito tokens (same as chat and search).
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

              <Box variant="h4">Start Scrape Mutation</Box>
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
                  {startScrapeMutation}
                </code>
              </Box>
              <CopyToClipboard
                copyText={startScrapeMutation}
                copyButtonText="Copy Mutation"
                copySuccessText="Copied!"
              />

              <Box variant="h4">Get Job Status Query</Box>
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
                  {getScrapeJobQuery}
                </code>
              </Box>
              <CopyToClipboard
                copyText={getScrapeJobQuery}
                copyButtonText="Copy Query"
                copySuccessText="Copied!"
              />

              <Box variant="h4">List Jobs Query</Box>
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
                  {listScrapeJobsQuery}
                </code>
              </Box>
              <CopyToClipboard
                copyText={listScrapeJobsQuery}
                copyButtonText="Copy Query"
                copySuccessText="Copied!"
              />

              {jsExample && (
                <>
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
                </>
              )}

              <Box variant="small" color="text-body-secondary">
                Scope options: SUBPAGES (same path prefix), HOSTNAME (same host), DOMAIN (includes subdomains).
                Scrape mode: FAST (HTTP only), FULL (Playwright), AUTO (auto-detect).
              </Box>
            </SpaceBetween>
          </ExpandableSection>
        </Container>
      )}
    </SpaceBetween>
  );
};
