import React, { useState, useCallback } from 'react';
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
  Spinner,
  ExpandableSection,
  Alert
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getDocument } from '../../graphql/queries/getDocument';

const client = generateClient();

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

// Component to display parsed page content
const PageContent = ({ documentId }) => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const fetchContent = useCallback(async () => {
    if (!documentId || content !== null) return;

    setLoading(true);
    setError(null);

    try {
      const { data } = await client.graphql({
        query: getDocument,
        variables: { documentId }
      });

      const doc = data?.getDocument;
      if (!doc?.previewUrl) {
        setError('No parsed content available');
        return;
      }

      // Fetch the actual content from the presigned URL
      const response = await fetch(doc.previewUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch content: ${response.status}`);
      }
      const text = await response.text();
      setContent(text);
    } catch (err) {
      console.error('Failed to fetch page content:', err);
      setError(err.message || 'Failed to load content');
    } finally {
      setLoading(false);
    }
  }, [documentId, content]);

  const handleExpand = (isExpanded) => {
    setExpanded(isExpanded);
    if (isExpanded && content === null && !loading) {
      fetchContent();
    }
  };

  if (!documentId) {
    return <Box color="text-status-inactive">Not yet processed</Box>;
  }

  return (
    <ExpandableSection
      headerText="Parsed Content"
      expanded={expanded}
      onChange={({ detail }) => handleExpand(detail.expanded)}
    >
      {loading && (
        <Box textAlign="center" padding="s">
          <Spinner /> Loading content...
        </Box>
      )}
      {error && (
        <Alert type="error">{error}</Alert>
      )}
      {content && (
        <Box>
          <pre style={{
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            maxHeight: '400px',
            overflow: 'auto',
            backgroundColor: '#f5f5f5',
            padding: '12px',
            borderRadius: '4px',
            fontSize: '13px',
            lineHeight: '1.5'
          }}>
            {content}
          </pre>
        </Box>
      )}
    </ExpandableSection>
  );
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
      header: 'Original Page',
      cell: item => (
        <Link href={item.url} external>{item.title || item.url}</Link>
      ),
      width: 300
    },
    {
      id: 'content',
      header: 'Parsed Content',
      cell: item => <PageContent documentId={item.documentId} />,
      width: 400
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => {
        const status = item.status?.toUpperCase();
        const statusConfig = {
          COMPLETED: { type: 'success', label: 'Completed' },
          PENDING: { type: 'pending', label: 'Pending' },
          PROCESSING: { type: 'in-progress', label: 'Processing' },
          FAILED: { type: 'error', label: 'Failed' },
          SKIPPED: { type: 'stopped', label: 'Skipped' }
        };
        const config = statusConfig[status] || { type: 'info', label: item.status };
        return <StatusIndicator type={config.type}>{config.label}</StatusIndicator>;
      },
      width: 120
    },
    {
      id: 'depth',
      header: 'Depth',
      cell: item => item.depth,
      width: 80
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
            isActive && (
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
