import React, { useState } from 'react';
import { Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';
import { ScrapeForm } from './ScrapeForm';
import { useScrape } from '../../hooks/useScrape';
import { useNavigate } from 'react-router-dom';
import { ApiDocs } from '../common/ApiDocs';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

const graphqlExample = `# Start a scrape job
mutation StartScrape($input: StartScrapeInput!) {
  startScrape(input: $input) { jobId, status }
}

# Check job status
query GetScrapeJob($jobId: ID!) {
  getScrapeJob(jobId: $jobId) {
    job { status, processedCount, totalUrls }
  }
}`;

const jsExample = `// Start scrape job
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: START_SCRAPE_MUTATION,
    variables: {
      input: {
        url: 'https://docs.example.com',
        maxPages: 100,           // Max pages to crawl (default: 100)
        maxDepth: 3,             // Link depth from start (default: 3)
        scope: 'HOSTNAME',       // SUBPAGES | HOSTNAME | DOMAIN
        includePatterns: ['/docs/*', '/api/*'],  // Only these paths
        excludePatterns: ['/blog/*'],            // Skip these paths
        scrapeMode: 'AUTO',      // AUTO | FAST | FULL (browser)
        forceRescrape: false     // Re-scrape unchanged pages
      }
    }
  })
});
const { jobId } = (await res.json()).data.startScrape;`;

const curlExample = `curl -X POST 'ENDPOINT' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: API_KEY' \\
  -d '{
    "query": "mutation StartScrape($input: StartScrapeInput!) { startScrape(input: $input) { jobId, status } }",
    "variables": {
      "input": {
        "url": "https://docs.example.com",
        "maxPages": 100,
        "scope": "HOSTNAME"
      }
    }
  }'`;

export const Scrape = () => {
  const navigate = useNavigate();
  const { startScrape, checkDuplicate, loading: hookLoading, error: hookError, clearError } = useScrape();
  const [duplicateWarning, setDuplicateWarning] = useState(null);
  const [pendingConfig, setPendingConfig] = useState(null);

  const handleSubmit = async (config) => {
    if (!config.force) {
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

    setDuplicateWarning(null);
    setPendingConfig(null);

    try {
      const job = await startScrape({
        url: config.url,
        maxPages: config.maxPages,
        maxDepth: config.maxDepth,
        scope: config.scope,
        includePatterns: config.includePatterns,
        excludePatterns: config.excludePatterns,
        scrapeMode: config.scrapeMode,
        cookies: config.cookies,
        forceRescrape: config.forceRescrape
      });

      if (job?.jobId) {
        navigate('/');
      }
    } catch (err) {
      console.error('[Scrape] Failed:', err);
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
        <Alert type="error" dismissible onDismiss={clearError} header="Scrape failed">
          {hookError}
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
        <ApiDocs
          title="Scrape API"
          description="Start scrapes programmatically. Configure maxPages, maxDepth, scope (SUBPAGES|HOSTNAME|DOMAIN), include/exclude patterns, and scrapeMode (AUTO|FAST|FULL)."
          endpoint={graphqlEndpoint}
          examples={[
            { id: 'graphql', label: 'GraphQL', code: graphqlExample },
            { id: 'js', label: 'JavaScript', code: jsExample },
            { id: 'curl', label: 'cURL', code: curlExample },
          ]}
        />
      )}
    </SpaceBetween>
  );
};
