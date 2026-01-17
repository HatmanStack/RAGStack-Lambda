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
import type { ScrapeJobDetailProps, ScrapeUrlItem, StatusConfig } from './types';

type StatusIndicatorType = 'pending' | 'in-progress' | 'success' | 'error' | 'warning' | 'stopped' | 'info';

const JOB_STATUS_MAP: Record<string, StatusConfig> = {
  PENDING: { type: 'pending', label: 'Pending' },
  DISCOVERING: { type: 'in-progress', label: 'Discovering' },
  PROCESSING: { type: 'in-progress', label: 'Processing' },
  COMPLETED: { type: 'success', label: 'Completed' },
  COMPLETED_WITH_ERRORS: { type: 'warning', label: 'Completed with errors' },
  FAILED: { type: 'error', label: 'Failed' },
  CANCELLED: { type: 'stopped', label: 'Cancelled' }
};

const PAGE_STATUS_MAP: Record<string, StatusConfig> = {
  COMPLETED: { type: 'success', label: 'Completed' },
  PENDING: { type: 'pending', label: 'Pending' },
  PROCESSING: { type: 'in-progress', label: 'Processing' },
  FAILED: { type: 'error', label: 'Failed' },
  SKIPPED: { type: 'stopped', label: 'Skipped' }
};

const getStatusIndicator = (status: string) => {
  const config = JOB_STATUS_MAP[status] || { type: 'pending', label: status };
  return <StatusIndicator type={config.type as StatusIndicatorType}>{config.label}</StatusIndicator>;
};

interface ScrapeJobInfo {
  jobId: string;
  baseUrl: string;
  title?: string;
  status: string;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  createdAt?: string;
  failedUrls?: string[];
  jobMetadata?: Record<string, unknown> | string;
  config?: {
    maxPages?: number;
    maxDepth?: number;
    scope?: string;
  };
}

interface ScrapePageItem {
  url: string;
  title?: string;
  status?: string;
  contentUrl?: string;
  depth?: number;
  error?: string;
}

export const ScrapeJobDetail = ({ job, visible, onDismiss, onCancel }: ScrapeJobDetailProps) => {
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

  const { job: jobInfo, pages = [] } = job as { job?: ScrapeJobInfo; pages?: ScrapePageItem[] };

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
      header: 'Original Page',
      cell: (item: ScrapePageItem) => (
        <Link href={item.url} external>{item.title || item.url}</Link>
      ),
      width: 300
    },
    {
      id: 'content',
      header: 'Parsed Content',
      cell: (item: ScrapePageItem) => item.contentUrl ? (
        <Link href={item.contentUrl} external>View parsed text</Link>
      ) : (
        <Box color="text-status-inactive">-</Box>
      ),
      width: 150
    },
    {
      id: 'status',
      header: 'Status',
      cell: (item: ScrapePageItem) => {
        const status = item.status?.toUpperCase() || '';
        const config = PAGE_STATUS_MAP[status] || { type: 'info', label: item.status || 'Unknown' };
        return <StatusIndicator type={config.type as StatusIndicatorType}>{config.label}</StatusIndicator>;
      },
      width: 120
    },
    {
      id: 'depth',
      header: 'Depth',
      cell: (item: ScrapePageItem) => item.depth,
      width: 80
    },
    {
      id: 'error',
      header: 'Error',
      cell: (item: ScrapePageItem) => item.error || '-'
    }
  ];

  const isActive = ['PENDING', 'DISCOVERING', 'PROCESSING'].includes(jobInfo.status);
  const progress = jobInfo.totalUrls && jobInfo.totalUrls > 0
    ? Math.round(((jobInfo.processedCount || 0) / jobInfo.totalUrls) * 100)
    : 0;

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header={
        <Header
          actions={
            isActive && onCancel && (
              <Button onClick={() => onCancel(jobInfo.jobId)}>Cancel</Button>
            )
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
            {jobInfo.createdAt ? new Date(jobInfo.createdAt).toLocaleString() : 'N/A'}
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

        {jobInfo.jobMetadata && (() => {
          const metadata = typeof jobInfo.jobMetadata === 'string'
            ? JSON.parse(jobInfo.jobMetadata)
            : jobInfo.jobMetadata;
          const entries = Object.entries(metadata).filter(([, v]) => v != null && v !== '');
          if (entries.length === 0) return null;
          return (
            <Container header={<Header variant="h3">Extracted Metadata</Header>}>
              <ColumnLayout columns={2} variant="text-grid">
                {entries.map(([key, value]) => (
                  <div key={key}>
                    <Box variant="awsui-key-label">{key.replace(/_/g, ' ')}</Box>
                    <Box>{String(value)}</Box>
                  </div>
                ))}
              </ColumnLayout>
            </Container>
          );
        })()}

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
