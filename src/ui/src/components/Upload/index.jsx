import React, { useCallback } from 'react';
import { SpaceBetween } from '@cloudscape-design/components';
import { UploadZone } from './UploadZone';
import { UploadQueue } from './UploadQueue';
import { useUpload } from '../../hooks/useUpload';

export const Upload = () => {
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
      setTimeout(() => uploadFile(uploadId), 100);
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
