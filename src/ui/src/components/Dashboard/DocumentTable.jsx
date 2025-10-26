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
  CollectionPreferences
} from '@cloudscape-design/components';
import { useCollection } from '@cloudscape-design/collection-hooks';

const getStatusIndicator = (status) => {
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

export const DocumentTable = ({ documents, loading, onRefresh, onSelectDocument }) => {
  const [selectedItems, setSelectedItems] = useState([]);

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps } =
    useCollection(documents, {
      filtering: {
        empty: (
          <Box textAlign="center" color="inherit">
            <b>No documents</b>
            <Box padding={{ bottom: 's' }} variant="p" color="inherit">
              Upload documents to get started
            </Box>
          </Box>
        ),
        noMatch: (
          <Box textAlign="center" color="inherit">
            <b>No matches</b>
            <Box padding={{ bottom: 's' }} variant="p" color="inherit">
              No documents match the filter criteria
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
          Documents
        </Header>
      }
      columnDefinitions={[
        {
          id: 'filename',
          header: 'Filename',
          cell: item => (
            <Link onFollow={() => onSelectDocument(item.documentId)}>
              {item.filename}
            </Link>
          ),
          sortingField: 'filename',
          isRowHeader: true
        },
        {
          id: 'status',
          header: 'Status',
          cell: item => getStatusIndicator(item.status),
          sortingField: 'status'
        },
        {
          id: 'fileType',
          header: 'Type',
          cell: item => item.fileType?.toUpperCase() || 'N/A',
          sortingField: 'fileType'
        },
        {
          id: 'totalPages',
          header: 'Pages',
          cell: item => item.totalPages || '-',
          sortingField: 'totalPages'
        },
        {
          id: 'isTextNative',
          header: 'Text Native',
          cell: item => item.isTextNative ? '✓' : '-',
          sortingField: 'isTextNative'
        },
        {
          id: 'createdAt',
          header: 'Uploaded',
          cell: item => new Date(item.createdAt).toLocaleString(),
          sortingField: 'createdAt'
        }
      ]}
      items={items}
      loading={loading}
      loadingText="Loading documents"
      selectionType="single"
      selectedItems={selectedItems}
      onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
      filter={
        <TextFilter
          {...filterProps}
          filteringPlaceholder="Find documents"
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
            visibleContent: ['filename', 'status', 'fileType', 'totalPages', 'createdAt']
          }}
        />
      }
    />
  );
};
