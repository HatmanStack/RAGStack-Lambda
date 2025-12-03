import React, { useState } from 'react';
import { Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';
import { ScrapeForm } from './ScrapeForm';

export const Scrape = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [duplicateWarning, setDuplicateWarning] = useState(null);

  const handleSubmit = async (config) => {
    setLoading(true);
    setError(null);
    try {
      // TODO: Wire up to useScrape hook in Task 3
      console.log('Scrape config:', config);
    } catch (err) {
      setError(err.message || 'Failed to start scrape');
    } finally {
      setLoading(false);
    }
  };

  const handleDismissWarning = () => {
    setDuplicateWarning(null);
  };

  return (
    <SpaceBetween size="l">
      {error && (
        <Alert
          type="error"
          dismissible
          onDismiss={() => setError(null)}
          header="Scrape failed"
        >
          {error}
        </Alert>
      )}
      <Container header={<Header variant="h1">Scrape Website</Header>}>
        <ScrapeForm
          onSubmit={handleSubmit}
          loading={loading}
          duplicateWarning={duplicateWarning}
          onDismissWarning={handleDismissWarning}
        />
      </Container>
    </SpaceBetween>
  );
};
