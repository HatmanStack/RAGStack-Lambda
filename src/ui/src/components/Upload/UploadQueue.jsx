import React from 'react';
import {
  Container,
  Header,
  Table,
  ProgressBar,
  StatusIndicator,
  Button,
  SpaceBetween,
  Box
} from '@cloudscape-design/components';

export const UploadQueue = ({ uploads, onRetry, onRemove, onClearCompleted }) => {
  const getStatusIndicator = (status, error) => {
    switch (status) {
      case 'pending':
        return <StatusIndicator type="pending">Pending</StatusIndicator>;
      case 'uploading':
        return <StatusIndicator type="in-progress">Uploading</StatusIndicator>;
      case 'complete':
        return <StatusIndicator type="success">Complete</StatusIndicator>;
      case 'failed':
        return <StatusIndicator type="error">{error || 'Failed'}</StatusIndicator>;
      default:
        return <StatusIndicator type="info">{status}</StatusIndicator>;
    }
  };

  return (
    <Container
      header={
        <Header
          variant="h2"
          counter={`(${uploads.length})`}
          actions={
            <Button onClick={onClearCompleted} disabled={!uploads.some(u => u.status === 'complete')}>
              Clear completed
            </Button>
          }
        >
          Upload Queue
        </Header>
      }
    >
      <Table
        columnDefinitions={[
          {
            id: 'filename',
            header: 'File',
            cell: item => item.file.name,
            width: 300
          },
          {
            id: 'size',
            header: 'Size',
            cell: item => `${(item.file.size / 1024 / 1024).toFixed(2)} MB`,
            width: 100
          },
          {
            id: 'status',
            header: 'Status',
            cell: item => getStatusIndicator(item.status, item.error),
            width: 150
          },
          {
            id: 'progress',
            header: 'Progress',
            cell: item => (
              item.status === 'uploading' ? (
                <ProgressBar
                  value={item.progress}
                  variant="standalone"
                  label={`${item.progress}%`}
                />
              ) : (
                <Box>{item.progress}%</Box>
              )
            ),
            width: 200
          },
          {
            id: 'actions',
            header: 'Actions',
            cell: item => (
              <SpaceBetween direction="horizontal" size="xs">
                {item.status === 'failed' && (
                  <Button onClick={() => onRetry(item.id)} variant="inline-link">
                    Retry
                  </Button>
                )}
                <Button onClick={() => onRemove(item.id)} variant="inline-link">
                  Remove
                </Button>
              </SpaceBetween>
            ),
            width: 150
          }
        ]}
        items={uploads}
        empty={
          <Box textAlign="center" color="inherit">
            <b>No uploads</b>
            <Box padding={{ bottom: 's' }} variant="p" color="inherit">
              Upload files to get started
            </Box>
          </Box>
        }
      />
    </Container>
  );
};
