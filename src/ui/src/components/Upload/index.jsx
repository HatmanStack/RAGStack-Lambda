import React, { useState, useCallback } from 'react';
import { SpaceBetween, Tabs, ContentLayout, Header } from '@cloudscape-design/components';
import { UploadZone } from './UploadZone';
import { UploadQueue } from './UploadQueue';
import { ImageUpload } from '../ImageUpload';
import { useUpload } from '../../hooks/useUpload';

const DocumentUploadContent = () => {
  const {
    uploads,
    uploading,
    addUpload,
    uploadFile,
    removeUpload,
    clearCompleted
  } = useUpload();

  const handleFilesSelected = useCallback((files) => {
    files.forEach(file => {
      const uploadId = addUpload(file);
      // Auto-start upload
      setTimeout(() => {
        uploadFile(uploadId);
      }, 100);
    });
  }, [addUpload, uploadFile]);

  const handleRetry = useCallback((uploadId) => {
    uploadFile(uploadId);
  }, [uploadFile]);

  return (
    <SpaceBetween size="l">
      <UploadZone
        onFilesSelected={handleFilesSelected}
        disabled={uploading}
      />
      {uploads.length > 0 && (
        <UploadQueue
          uploads={uploads}
          onRetry={handleRetry}
          onRemove={removeUpload}
          onClearCompleted={clearCompleted}
        />
      )}
    </SpaceBetween>
  );
};

export const Upload = () => {
  const [activeTabId, setActiveTabId] = useState('documents');

  const tabs = [
    {
      id: 'documents',
      label: 'Documents',
      content: <DocumentUploadContent />
    },
    {
      id: 'images',
      label: 'Images',
      content: <ImageUpload />
    }
  ];

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Upload documents and images to your knowledge base"
        >
          Upload
        </Header>
      }
    >
      <Tabs
        tabs={tabs}
        activeTabId={activeTabId}
        onChange={({ detail }) => setActiveTabId(detail.activeTabId)}
      />
    </ContentLayout>
  );
};
