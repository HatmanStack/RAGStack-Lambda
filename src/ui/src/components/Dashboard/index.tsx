import React, { useState } from 'react';
import { ContentLayout, Header, SpaceBetween } from '@cloudscape-design/components';
import { DocumentTable } from './DocumentTable';
import { DocumentDetail } from './DocumentDetail';
import { ScrapeJobDetail } from './ScrapeJobDetail';
import { ImageDetail } from './ImageDetail';
import { useDocuments } from '../../hooks/useDocuments';
import { useScrape } from '../../hooks/useScrape';

export const Dashboard = () => {
  const { documents, loading, refreshDocuments, deleteDocuments } = useDocuments();
  const { fetchJobDetail, selectedJob, cancelScrape } = useScrape();
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [selectedType, setSelectedType] = useState(null);

  const handleSelectItem = (id, type) => {
    setSelectedDocumentId(id);
    setSelectedType(type);
    if (type === 'scrape') {
      fetchJobDetail(id);
    }
  };

  const handleDismiss = () => {
    setSelectedDocumentId(null);
    setSelectedType(null);
  };

  const handleCancelScrape = async (jobId) => {
    try {
      await cancelScrape(jobId);
      refreshDocuments();
    } catch (err) {
      console.error('Failed to cancel scrape:', err);
    }
  };

  const handleDelete = async (documentIds) => {
    try {
      const result = await deleteDocuments(documentIds);
      // Partial failures are returned in result.failedIds if any
      return result;
    } catch (err) {
      console.error('Failed to delete documents:', err);
      throw err;
    }
  };

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="View and manage your documents and scrape jobs">
          Dashboard
        </Header>
      }
    >
      <SpaceBetween size="l">
        <DocumentTable
          documents={documents}
          loading={loading}
          onRefresh={refreshDocuments}
          onSelectDocument={handleSelectItem}
          onDelete={handleDelete}
        />
      </SpaceBetween>

      {selectedType === 'scrape' && (
        <ScrapeJobDetail
          job={selectedJob}
          visible={!!selectedDocumentId && selectedType === 'scrape'}
          onDismiss={handleDismiss}
          onCancel={handleCancelScrape}
        />
      )}

      {selectedType === 'image' && (
        <ImageDetail
          imageId={selectedDocumentId}
          visible={!!selectedDocumentId && selectedType === 'image'}
          onDismiss={handleDismiss}
          onDelete={() => {
            handleDismiss();
            refreshDocuments();
          }}
        />
      )}

      {selectedType === 'document' && (
        <DocumentDetail
          documentId={selectedDocumentId}
          visible={!!selectedDocumentId && selectedType === 'document'}
          onDismiss={handleDismiss}
        />
      )}
    </ContentLayout>
  );
};
