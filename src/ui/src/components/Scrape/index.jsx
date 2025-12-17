import React, { useState } from 'react';
import { Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';
import { ScrapeForm } from './ScrapeForm';
import { useScrape } from '../../hooks/useScrape';
import { useNavigate } from 'react-router-dom';

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

    console.log('[Scrape] Submitting scrape with config:', JSON.stringify(scrapeInput, null, 2));

    try {
      const job = await startScrape(scrapeInput);
      console.log('[Scrape] Job created successfully:', job);

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
    </SpaceBetween>
  );
};
