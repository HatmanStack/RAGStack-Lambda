import React from 'react';
import { Container, Header, SpaceBetween } from '@cloudscape-design/components';

export const Scrape = () => {
  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h1">Scrape Website</Header>}>
        {/* Configuration form will go here */}
        <p>Scrape configuration coming soon...</p>
      </Container>
    </SpaceBetween>
  );
};
