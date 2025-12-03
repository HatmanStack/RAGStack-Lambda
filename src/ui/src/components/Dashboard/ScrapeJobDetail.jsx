import React from 'react';
import {
  Modal,
  Box,
  SpaceBetween,
  ColumnLayout,
  Container,
  Header,
  StatusIndicator,
  Button,
  ProgressBar,
  Link,
  Table,
  Spinner
} from '@cloudscape-design/components';

const getStatusIndicator = (status) => {
  const statusMap = {
    PENDING: { type: 'pending', label: 'Pending' },
    DISCOVERING: { type: 'in-progress', label: 'Discovering' },
    PROCESSING: { type: 'in-progress', label: 'Processing' },
    COMPLETED: { type: 'success', label: 'Completed' },
    COMPLETED_WITH_ERRORS: { type: 'warning', label: 'Completed with errors' },
    FAILED: { type: 'error', label: 'Failed' },
    CANCELLED: { type: 'stopped', label: 'Cancelled' }
  };
  const config = statusMap[status] || { type: 'pending', label: status };
  return <StatusIndicator type={config.type}>{config.label}</StatusIndicator>;
};

export const ScrapeJobDetail = ({ job, visible, onDismiss, onCancel }) => {
  if (!visible) return null;

  // Show loading while job details are being fetched
  if (!job) {
    return (
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        header="Scrape Job Details"
        size="large"
      >
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
        </Box>
      </Modal>
    );
  }

  const { job: jobInfo, pages = [] } = job;

  if (!jobInfo) {
    return (
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        header="Scrape Job Details"
        size="large"
      >
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
        </Box>
      </Modal>
    );
  }

  const pageColumns = [
    {
      id: 'url',
      header: 'URL',
      cell: item => (
        <Link href={item.url} external>{item.title || item.url}</Link>
      )
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => (
        <StatusIndicator type={item.status === 'completed' ? 'success' : 'error'}>
          {item.status}
        </StatusIndicator>
      )
    },
    {
      id: 'depth',
      header: 'Depth',
      cell: item => item.depth
    },
    {
      id: 'error',
      header: 'Error',
      cell: item => item.error || '-'
    }
  ];

  const isActive = ['PENDING', 'DISCOVERING', 'PROCESSING'].includes(jobInfo.status);
  const progress = jobInfo.totalUrls > 0
    ? Math.round((jobInfo.processedCount / jobInfo.totalUrls) * 100)
    : 0;

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header={
        <Header
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              {isActive && (
                <Button onClick={() => onCancel(jobInfo.jobId)}>Cancel</Button>
              )}
              <Button variant="primary" onClick={onDismiss}>Close</Button>
            </SpaceBetween>
          }
        >
          {jobInfo.title || jobInfo.baseUrl}
        </Header>
      }
      size="large"
    >
      <SpaceBetween size="l">
        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="awsui-key-label">Status</Box>
            {getStatusIndicator(jobInfo.status)}
          </div>
          <div>
            <Box variant="awsui-key-label">Source URL</Box>
            <Link href={jobInfo.baseUrl} external>{jobInfo.baseUrl}</Link>
          </div>
          <div>
            <Box variant="awsui-key-label">Created</Box>
            {new Date(jobInfo.createdAt).toLocaleString()}
          </div>
          <div>
            <Box variant="awsui-key-label">Configuration</Box>
            <SpaceBetween size="xs">
              <span>Max pages: {jobInfo.config?.maxPages || '-'}</span>
              <span>Max depth: {jobInfo.config?.maxDepth || '-'}</span>
              <span>Scope: {jobInfo.config?.scope || '-'}</span>
            </SpaceBetween>
          </div>
        </ColumnLayout>

        <Container header={<Header variant="h3">Progress</Header>}>
          <ProgressBar
            value={progress}
            description={`${jobInfo.processedCount || 0} processed, ${jobInfo.failedCount || 0} failed`}
            label={`${jobInfo.totalUrls || 0} pages discovered`}
          />
        </Container>

        {jobInfo.failedUrls && jobInfo.failedUrls.length > 0 && (
          <Container header={<Header variant="h3">Failed URLs</Header>}>
            <ul>
              {jobInfo.failedUrls.slice(0, 10).map(url => (
                <li key={url}><Link href={url} external>{url}</Link></li>
              ))}
              {jobInfo.failedUrls.length > 10 && (
                <li>...and {jobInfo.failedUrls.length - 10} more</li>
              )}
            </ul>
          </Container>
        )}

        {pages.length > 0 && (
          <Table
            header={<Header variant="h3">Pages ({pages.length})</Header>}
            columnDefinitions={pageColumns}
            items={pages}
            variant="embedded"
            stickyHeader
          />
        )}
      </SpaceBetween>
    </Modal>
  );
};
