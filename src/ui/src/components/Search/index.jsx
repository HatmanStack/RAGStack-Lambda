import React from 'react';
import { ContentLayout, Header } from '@cloudscape-design/components';
import { SearchInterface } from './SearchInterface';

export const Search = () => {
  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Query your Knowledge Base">
          Search Documents
        </Header>
      }
    >
      <SearchInterface />
    </ContentLayout>
  );
};
