import React, { useState } from 'react';
import { ContentLayout, Header, SpaceBetween } from '@cloudscape-design/components';
import { DocumentTable } from './DocumentTable';
import { DocumentDetail } from './DocumentDetail';
import { useDocuments } from '../../hooks/useDocuments';

export const Dashboard = () => {
  const { documents, loading, refreshDocuments } = useDocuments();
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="View and manage your documents">
          Dashboard
        </Header>
      }
    >
      <SpaceBetween size="l">
        <DocumentTable
          documents={documents}
          loading={loading}
          onRefresh={refreshDocuments}
          onSelectDocument={setSelectedDocumentId}
        />
      </SpaceBetween>

      <DocumentDetail
        documentId={selectedDocumentId}
        visible={!!selectedDocumentId}
        onDismiss={() => setSelectedDocumentId(null)}
      />
    </ContentLayout>
  );
};
