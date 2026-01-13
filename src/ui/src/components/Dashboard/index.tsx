import React, { useState } from 'react';
import { ContentLayout, Header, SpaceBetween } from '@cloudscape-design/components';
import { DocumentTable } from './DocumentTable';
import { DocumentDetail } from './DocumentDetail';
import { ScrapeJobDetail } from './ScrapeJobDetail';
import { ImageDetail } from './ImageDetail';
import { useDocuments } from '../../hooks/useDocuments';
import { useScrape } from '../../hooks/useScrape';

type ItemType = 'document' | 'scrape' | 'image' | null;

export const Dashboard = () => {
  const { documents, loading, refreshDocuments, deleteDocuments } = useDocuments();
  const { fetchJobDetail, selectedJob, cancelScrape } = useScrape();
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<ItemType>(null);

  const handleSelectItem = (id: string, type: string) => {
    setSelectedDocumentId(id);
    setSelectedType(type as ItemType);
    if (type === 'scrape') {
      fetchJobDetail(id);
    }
  };

  const handleDismiss = () => {
    setSelectedDocumentId(null);
    setSelectedType(null);
  };

  const handleCancelScrape = async (jobId: string) => {
    try {
      await cancelScrape(jobId);
      refreshDocuments();
    } catch (err) {
      console.error('Failed to cancel scrape:', err);
    }
  };

  const handleDelete = async (documentIds: string[]) => {
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

      {selectedType === 'image' && selectedDocumentId && (
        <ImageDetail
          imageId={selectedDocumentId}
          visible={!!selectedDocumentId && selectedType === 'image'}
          onDismiss={handleDismiss}
          onDelete={async () => {
            handleDismiss();
            refreshDocuments();
          }}
        />
      )}

      {selectedType === 'document' && selectedDocumentId && (
        <DocumentDetail
          documentId={selectedDocumentId}
          visible={!!selectedDocumentId && selectedType === 'document'}
          onDismiss={handleDismiss}
        />
      )}
    </ContentLayout>
  );
};
