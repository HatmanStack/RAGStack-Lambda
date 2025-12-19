import React, { useState } from 'react';
import { Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';
import { ScrapeForm } from './ScrapeForm';
import { useScrape } from '../../hooks/useScrape';
import { useNavigate } from 'react-router-dom';
import { ApiDocs } from '../common/ApiDocs';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

const startMutation = `mutation StartScrape($input: StartScrapeInput!) {
  startScrape(input: $input) { jobId, status }
}`;

const statusQuery = `query GetScrapeJob($jobId: ID!) {
  getScrapeJob(jobId: $jobId) {
    job { status, processedCount, totalUrls }
  }
}`;

const jsExample = `const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: \`${startMutation}\`,
    variables: { input: { url: 'https://docs.example.com', maxPages: 50, scope: 'HOSTNAME' } }
  })
});
const { jobId } = (await res.json()).data.startScrape;`;

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
          title="Scrape API (Server-side)"
          description="For backend integrations. Scope: SUBPAGES | HOSTNAME | DOMAIN"
          endpoint={graphqlEndpoint}
          examples={[
            { id: 'start', label: 'Start', code: startMutation },
            { id: 'status', label: 'Status', code: statusQuery },
            { id: 'js', label: 'JavaScript', code: jsExample },
          ]}
        />
      )}
    </SpaceBetween>
  );
};
