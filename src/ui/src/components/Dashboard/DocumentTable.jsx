import React, { useState } from 'react';
import {
  Table,
  Header,
  Button,
  StatusIndicator,
  Pagination,
  TextFilter,
  SpaceBetween,
  Link,
  Box,
  CollectionPreferences,
  Icon,
  ProgressBar,
  Badge
} from '@cloudscape-design/components';
import { useCollection } from '@cloudscape-design/collection-hooks';

const getStatusIndicator = (status, type) => {
  if (type === 'scrape') {
    const scrapeStatusMap = {
      'PENDING': { type: 'pending', text: 'Pending' },
      'DISCOVERING': { type: 'in-progress', text: 'Discovering' },
      'PROCESSING': { type: 'in-progress', text: 'Processing' },
      'COMPLETED': { type: 'success', text: 'Completed' },
      'COMPLETED_WITH_ERRORS': { type: 'warning', text: 'Completed with errors' },
      'FAILED': { type: 'error', text: 'Failed' },
      'CANCELLED': { type: 'stopped', text: 'Cancelled' }
    };
    const config = scrapeStatusMap[status] || { type: 'info', text: status };
    return <StatusIndicator type={config.type}>{config.text}</StatusIndicator>;
  }

  const statusMap = {
    'UPLOADED': { type: 'pending', text: 'Uploaded' },
    'PROCESSING': { type: 'in-progress', text: 'Processing' },
    'OCR_COMPLETE': { type: 'in-progress', text: 'OCR Complete' },
    'EMBEDDING_COMPLETE': { type: 'in-progress', text: 'Embedding Complete' },
    'INDEXED': { type: 'success', text: 'Indexed' },
    'FAILED': { type: 'error', text: 'Failed' }
  };

  const config = statusMap[status] || { type: 'info', text: status };
  return <StatusIndicator type={config.type}>{config.text}</StatusIndicator>;
};

const getTypeLabel = (type) => {
  if (type === 'scrape') {
    return (
      <SpaceBetween direction="horizontal" size="xs">
        <Icon name="external" />
        <span>Website</span>
      </SpaceBetween>
    );
  }
  return 'Document';
};

export const DocumentTable = ({ documents, loading, onRefresh, onSelectDocument }) => {
  const [selectedItems, setSelectedItems] = useState([]);

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(documents, {
      filtering: {
        empty: (
          <Box textAlign="center" color="inherit">
            <b>No documents</b>
            <Box padding={{ bottom: 's' }} variant="p" color="inherit">
              Upload documents or scrape websites to get started
            </Box>
          </Box>
        ),
        noMatch: (
          <Box textAlign="center" color="inherit">
            <b>No matches</b>
            <Box padding={{ bottom: 's' }} variant="p" color="inherit">
              No items match the filter criteria
            </Box>
          </Box>
        )
      },
      pagination: { pageSize: 20 },
      sorting: {
        defaultState: {
          sortingColumn: {
            sortingField: 'createdAt'
          },
          isDescending: true
        }
      }
    });

  const columnDefinitions = [
    {
      id: 'filename',
      header: 'Name',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          {item.type === 'scrape' && <Icon name="external" size="small" />}
          <Link onFollow={() => onSelectDocument(item.documentId, item.type)}>
            {item.filename}
          </Link>
        </SpaceBetween>
      ),
      sortingField: 'filename',
      isRowHeader: true
    },
    {
      id: 'type',
      header: 'Type',
      cell: item => getTypeLabel(item.type),
      sortingField: 'type'
    },
    {
      id: 'status',
      header: 'Status',
      cell: item => getStatusIndicator(item.status, item.type),
      sortingField: 'status'
    },
    {
      id: 'progress',
      header: 'Progress',
      cell: item => {
        if (item.type === 'scrape' && ['DISCOVERING', 'PROCESSING'].includes(item.status)) {
          const progress = item.totalPages > 0
            ? Math.round((item.processedCount / item.totalPages) * 100)
            : 0;
          return (
            <ProgressBar
              value={progress}
              label={`${item.processedCount || 0}/${item.totalPages || 0} pages`}
            />
          );
        }
        if (item.type === 'scrape' && item.totalPages > 0) {
          return `${item.processedCount || 0}/${item.totalPages} pages`;
        }
        return item.totalPages ? `${item.totalPages} pages` : '-';
      }
    },
    {
      id: 'createdAt',
      header: 'Created',
      cell: item => new Date(item.createdAt).toLocaleString(),
      sortingField: 'createdAt'
    }
  ];

  return (
    <Table
      {...collectionProps}
      header={
        <Header
          variant="h2"
          counter={`(${documents.length})`}
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={onRefresh} iconName="refresh" loading={loading}>
                Refresh
              </Button>
            </SpaceBetween>
          }
        >
          Documents &amp; Scrapes
        </Header>
      }
      columnDefinitions={columnDefinitions}
      items={items}
      loading={loading}
      loadingText="Loading items"
      selectionType="single"
      selectedItems={selectedItems}
      onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
      filter={
        <TextFilter
          {...filterProps}
          filteringPlaceholder="Find documents or scrape jobs"
          countText={`${filteredItemsCount} ${filteredItemsCount === 1 ? 'match' : 'matches'}`}
        />
      }
      pagination={<Pagination {...paginationProps} />}
      preferences={
        <CollectionPreferences
          title="Preferences"
          confirmLabel="Confirm"
          cancelLabel="Cancel"
          preferences={{
            pageSize: 20,
            visibleContent: ['filename', 'type', 'status', 'progress', 'createdAt']
          }}
        />
      }
    />
  );
};
