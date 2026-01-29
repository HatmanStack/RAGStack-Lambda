import React from 'react';
import {
  SpaceBetween,
  Button,
  Alert,
  ProgressBar,
  Box,
  StatusIndicator,
} from '@cloudscape-design/components';
import { useReindex } from '../../hooks/useReindex';
import { useDemoMode } from '../../hooks/useDemoMode';
import type { ReindexStatus } from '../../types/graphql';

// Status messages for different reindex states
const STATUS_MESSAGES: Record<ReindexStatus, string> = {
  PENDING: 'Preparing reindex...',
  CREATING_KB: 'Creating new Knowledge Base...',
  PROCESSING: 'Processing documents...',
  DELETING_OLD_KB: 'Cleaning up old Knowledge Base...',
  COMPLETED: 'Reindex completed successfully!',
  FAILED: 'Reindex failed',
};

export function ReindexSection() {
  const {
    status,
    progress,
    error,
    isStarting,
    isInProgress,
    newKnowledgeBaseId,
    startReindex,
    clearState,
  } = useReindex();
  const { isEnabled: isDemoMode } = useDemoMode();

  const handleStartReindex = async () => {
    const confirmed = window.confirm(
      'Are you sure you want to regenerate metadata for all documents?\n\n' +
      'This will:\n' +
      '- Create a new Knowledge Base\n' +
      '- Re-process all documents with current metadata settings\n' +
      '- Delete the old Knowledge Base after completion\n\n' +
      'During this process, queries may return partial results.'
    );

    if (confirmed) {
      await startReindex();
    }
  };

  // Render progress section when reindex is in progress
  const renderProgress = () => {
    if (!progress) return null;

    const statusMessage = status ? STATUS_MESSAGES[status] : '';

    return (
      <SpaceBetween size="s">
        <Box>
          <StatusIndicator type="in-progress">
            {statusMessage}
          </StatusIndicator>
        </Box>

        {status === 'PROCESSING' && (
          <>
            <ProgressBar
              value={progress.percentComplete}
              label="Reindex progress"
              description={`Processing ${progress.processedCount} of ${progress.totalDocuments} documents`}
              additionalInfo={progress.currentDocument ? `Current: ${progress.currentDocument}` : undefined}
            />

            {progress.errorCount > 0 && (
              <Alert type="warning">
                {progress.errorCount} errors encountered during processing
              </Alert>
            )}
          </>
        )}
      </SpaceBetween>
    );
  };

  // Render completion message
  const renderCompletion = () => {
    if (status !== 'COMPLETED') return null;

    return (
      <Alert
        type="success"
        dismissible
        onDismiss={clearState}
        header="Reindex completed successfully!"
      >
        {progress && (
          <span>
            Processed {progress.processedCount} of {progress.totalDocuments} documents.
            {progress.errorCount > 0 && ` (${progress.errorCount} errors)`}
          </span>
        )}
        {newKnowledgeBaseId && (
          <Box margin={{ top: 'xs' }}>
            <small>New Knowledge Base ID: {newKnowledgeBaseId}</small>
          </Box>
        )}
      </Alert>
    );
  };

  // Render error message
  const renderError = () => {
    if (status !== 'FAILED' || !error) return null;

    return (
      <Alert
        type="error"
        dismissible
        onDismiss={clearState}
        header="Reindex failed"
      >
        {error}
      </Alert>
    );
  };

  return (
    <SpaceBetween size="m">
      <Box variant="h3">Reindex Knowledge Base</Box>

      {/* Demo mode info */}
      {isDemoMode && (
        <Alert type="info">
          Reindex All Documents is disabled in Demo Mode.
        </Alert>
      )}

      {/* Progress display */}
      {isInProgress && renderProgress()}

      {/* Completion message */}
      {renderCompletion()}

      {/* Error message */}
      {renderError()}

      {/* Action button */}
      <Button
        onClick={handleStartReindex}
        loading={isStarting}
        disabled={isInProgress || isStarting || isDemoMode}
        iconName="refresh"
      >
        {isInProgress ? 'Reindexing...' : 'Reindex All Documents'}
      </Button>

      {/* Info alert */}
      {!isDemoMode && (
        <Alert type="warning">
          This will regenerate metadata for all documents using current settings.
          The process may take several minutes to hours for large knowledge bases.
          During reindexing, queries may return partial results.
        </Alert>
      )}
    </SpaceBetween>
  );
}
