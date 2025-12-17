import React, { useState, useEffect, useMemo } from 'react';
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

// Date range options for document retention display
const DATE_RANGE_OPTIONS = [
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: 'all', label: 'All time' }
];

const DEFAULT_PREFERENCES = {
  pageSize: 20,
  visibleContent: ['filename', 'type', 'status', 'progress', 'createdAt'],
  dateRange: '7' // Default to 7 days
};

// Load preferences from localStorage
const loadPreferences = () => {
  try {
    const saved = localStorage.getItem('documentTablePreferences');
    if (saved) {
      return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) };
    }
  } catch (e) {
    console.warn('Failed to load preferences:', e);
  }
  return DEFAULT_PREFERENCES;
};

// Save preferences to localStorage
const savePreferences = (prefs) => {
  try {
    localStorage.setItem('documentTablePreferences', JSON.stringify(prefs));
  } catch (e) {
    console.warn('Failed to save preferences:', e);
  }
};

// Filter documents by date range
const filterByDateRange = (items, dateRangeDays) => {
  if (dateRangeDays === 'all') return items;

  const days = parseInt(dateRangeDays, 10);
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);

  return items.filter(item => {
    if (!item.createdAt) return true; // Keep items without dates
    const itemDate = new Date(item.createdAt);
    return itemDate >= cutoffDate;
  });
};

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

  if (type === 'image') {
    const imageStatusMap = {
      'PENDING': { type: 'pending', text: 'Pending' },
      'PROCESSING': { type: 'in-progress', text: 'Processing' },
      'INDEXED': { type: 'success', text: 'Indexed' },
      'FAILED': { type: 'error', text: 'Failed' }
    };
    const config = imageStatusMap[status] || { type: 'info', text: status };
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
  switch (type) {
    case 'scrape': return 'Website';
    case 'image': return 'Image';
    default: return 'Document';
  }
};

export const DocumentTable = ({ documents, loading, onRefresh, onSelectDocument }) => {
  const [selectedItems, setSelectedItems] = useState([]);
  const [preferences, setPreferences] = useState(loadPreferences);

  // Save preferences when they change
  useEffect(() => {
    savePreferences(preferences);
  }, [preferences]);

  // Filter documents by date range preference
  const filteredDocuments = useMemo(() => {
    return filterByDateRange(documents, preferences.dateRange);
  }, [documents, preferences.dateRange]);

  // Get current date range label for display
  const dateRangeLabel = DATE_RANGE_OPTIONS.find(
    opt => opt.value === preferences.dateRange
  )?.label || 'Last 7 days';

  const { items, filteredItemsCount, collectionProps, filterProps, paginationProps, actions } =
    useCollection(filteredDocuments, {
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
      pagination: { pageSize: preferences.pageSize },
      sorting: {
        defaultState: {
          sortingColumn: {
            sortingField: 'createdAt'
          },
          isDescending: true
        }
      }
    });

  const getTypeIcon = (type) => {
    switch (type) {
      case 'scrape': return <Icon name="external" size="small" />;
      case 'image': return <Icon name="file" size="small" />;
      default: return null;
    }
  };

  const columnDefinitions = [
    {
      id: 'filename',
      header: 'Name',
      cell: item => (
        <SpaceBetween direction="horizontal" size="xs">
          {getTypeIcon(item.type)}
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
          counter={`(${filteredDocuments.length}${filteredDocuments.length !== documents.length ? ` of ${documents.length}` : ''})`}
          description={`Showing: ${dateRangeLabel}`}
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
          onConfirm={({ detail }) => {
            const newPrefs = {
              pageSize: detail.pageSize,
              visibleContent: detail.visibleContent,
              dateRange: detail.custom?.dateRange || preferences.dateRange
            };
            setPreferences(newPrefs);
            // Reset to first page when preferences change
            if (actions?.setCurrentPage) {
              actions.setCurrentPage(1);
            }
          }}
          preferences={{
            pageSize: preferences.pageSize,
            visibleContent: preferences.visibleContent,
            custom: { dateRange: preferences.dateRange }
          }}
          pageSizePreference={{
            title: 'Page size',
            options: [
              { value: 10, label: '10 items' },
              { value: 20, label: '20 items' },
              { value: 50, label: '50 items' },
              { value: 100, label: '100 items' }
            ]
          }}
          visibleContentPreference={{
            title: 'Visible columns',
            options: [
              {
                label: 'Properties',
                options: [
                  { id: 'filename', label: 'Name', editable: false },
                  { id: 'type', label: 'Type' },
                  { id: 'status', label: 'Status' },
                  { id: 'progress', label: 'Progress' },
                  { id: 'createdAt', label: 'Created' }
                ]
              }
            ]
          }}
          customPreference={(value, setValue) => (
            <SpaceBetween size="m">
              <Box>
                <Box variant="awsui-key-label">Show documents from</Box>
                <select
                  value={value?.dateRange || '7'}
                  onChange={(e) => setValue({ ...value, dateRange: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid #aab7b8',
                    fontSize: '14px'
                  }}
                >
                  {DATE_RANGE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </Box>
            </SpaceBetween>
          )}
        />
      }
    />
  );
};
