import React, { useState, useEffect, useMemo, ChangeEvent } from 'react';
import {
  Table,
  Header,
  Button,
  ButtonDropdown,
  StatusIndicator,
  Pagination,
  TextFilter,
  SpaceBetween,
  Link,
  Box,
  CollectionPreferences,
  ProgressBar,
  Popover
} from '@cloudscape-design/components';
import { useCollection } from '@cloudscape-design/collection-hooks';
import type { DocumentItem } from '../../hooks/useDocuments';
import type { DocumentTableProps, TablePreferences } from './types';
import { useDemoMode } from '../../hooks/useDemoMode';

// Date range options for document retention display
const DATE_RANGE_OPTIONS = [
  { value: '1', label: 'Last 24 hours' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: 'all', label: 'All time' }
];

const DEFAULT_PREFERENCES: TablePreferences = {
  pageSize: 20,
  visibleContent: ['filename', 'type', 'status', 'progress', 'createdAt'],
  dateRange: '7' // Default to 7 days
};

// Load preferences from localStorage
const loadPreferences = (): TablePreferences => {
  try {
    const saved = localStorage.getItem('documentTablePreferences');
    if (saved) {
      return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) };
    }
  } catch {
    // Silently fall back to defaults on localStorage errors
  }
  return DEFAULT_PREFERENCES;
};

// Save preferences to localStorage
const savePreferences = (prefs: TablePreferences): void => {
  try {
    localStorage.setItem('documentTablePreferences', JSON.stringify(prefs));
  } catch {
    // Silently ignore localStorage save errors
  }
};

// Filter documents by date range
const filterByDateRange = (items: DocumentItem[], dateRangeDays: string): DocumentItem[] => {
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

type StatusIndicatorType = 'pending' | 'in-progress' | 'success' | 'error' | 'warning' | 'info' | 'stopped';

interface StatusMapEntry {
  type: StatusIndicatorType;
  text: string;
}

const getStatusIndicator = (status: string, type: string) => {
  if (type === 'scrape') {
    const scrapeStatusMap: Record<string, StatusMapEntry> = {
      'PENDING': { type: 'pending', text: 'Pending' },
      'DISCOVERING': { type: 'in-progress', text: 'Discovering' },
      'PROCESSING': { type: 'in-progress', text: 'Processing' },
      'COMPLETED': { type: 'success', text: 'Completed' },
      'COMPLETED_WITH_ERRORS': { type: 'warning', text: 'Completed with errors' },
      'FAILED': { type: 'error', text: 'Failed' },
      'CANCELLED': { type: 'stopped', text: 'Cancelled' }
    };
    const config = scrapeStatusMap[status] || { type: 'info' as StatusIndicatorType, text: status };
    return <StatusIndicator type={config.type}>{config.text}</StatusIndicator>;
  }

  if (type === 'image') {
    const imageStatusMap: Record<string, StatusMapEntry> = {
      'PENDING': { type: 'pending', text: 'Pending' },
      'PROCESSING': { type: 'in-progress', text: 'Processing' },
      'SYNC_QUEUED': { type: 'in-progress', text: 'Syncing' },
      'INDEXED': { type: 'success', text: 'Indexed' },
      'FAILED': { type: 'error', text: 'Failed' },
      'INGESTION_FAILED': { type: 'error', text: 'Ingestion Failed' }
    };
    const config = imageStatusMap[status] || { type: 'info' as StatusIndicatorType, text: status };
    return <StatusIndicator type={config.type}>{config.text}</StatusIndicator>;
  }

  const statusMap: Record<string, StatusMapEntry> = {
    'UPLOADED': { type: 'pending', text: 'Uploaded' },
    'PROCESSING': { type: 'in-progress', text: 'Processing' },
    'OCR_COMPLETE': { type: 'in-progress', text: 'OCR Complete' },
    'EMBEDDING_COMPLETE': { type: 'in-progress', text: 'Embedding Complete' },
    'INDEXED': { type: 'success', text: 'Indexed' },
    'FAILED': { type: 'error', text: 'Failed' }
  };

  const config = statusMap[status] || { type: 'info' as StatusIndicatorType, text: status };
  return <StatusIndicator type={config.type}>{config.text}</StatusIndicator>;
};

const getTypeLabel = (type: string): string => {
  switch (type) {
    case 'scrape': return 'Website';
    case 'image': return 'Image';
    case 'media': return 'Media';
    default: return 'Document';
  }
};

export const DocumentTable = ({ documents, loading, onRefresh, onSelectDocument, onDelete, onReprocess, onReindex }: DocumentTableProps) => {
  const [selectedItems, setSelectedItems] = useState<DocumentItem[]>([]);
  const [preferences, setPreferences] = useState<TablePreferences>(loadPreferences);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const { isEnabled: isDemoMode } = useDemoMode();

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

  const handleAction = async (actionId: string) => {
    if (selectedItems.length === 0) return;

    // Filter items based on action type
    const scrapeItems = selectedItems.filter(i => i.type === 'scrape');
    const nonScrapeItems = selectedItems.filter(i => i.type !== 'scrape');

    if (actionId === 'reindex') {
      if (!onReindex) return;

      // Check for unprocessed items (no output_s3_uri/caption_s3_uri)
      const unprocessedItems = selectedItems.filter(i =>
        i.status?.toLowerCase() === 'uploaded' || i.status?.toLowerCase() === 'pending'
      );

      if (unprocessedItems.length === selectedItems.length) {
        window.alert('Selected items have not been processed yet. Use Reprocess to run the full pipeline first.');
        return;
      }

      let confirmMessage = `Reindex ${selectedItems.length - unprocessedItems.length} item(s)? This will re-extract metadata and reingest to the Knowledge Base.`;
      if (unprocessedItems.length > 0) {
        confirmMessage += ` (${unprocessedItems.length} unprocessed item(s) will be skipped)`;
      }

      const confirmed = window.confirm(confirmMessage);
      if (!confirmed) return;

      setActionInProgress('reindex');
      try {
        const documentIds = selectedItems
          .filter(i => !unprocessedItems.includes(i))
          .map(item => item.documentId);
        await onReindex(documentIds);
        setSelectedItems([]);
      } catch (err) {
        console.error('Reindex failed:', err);
        window.alert(`Reindex failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      } finally {
        setActionInProgress(null);
      }
    } else if (actionId === 'reprocess') {
      if (!onReprocess) return;

      if (scrapeItems.length > 0 && nonScrapeItems.length === 0) {
        window.alert('Scrape jobs cannot be reprocessed. Please start a new scrape from the Scrape page.');
        return;
      }

      let confirmMessage = `Reprocess ${nonScrapeItems.length} item(s)? This will re-run OCR, extract metadata, and reingest to the Knowledge Base.`;
      if (scrapeItems.length > 0) {
        confirmMessage += ` (${scrapeItems.length} scrape job(s) will be skipped)`;
      }

      const confirmed = window.confirm(confirmMessage);
      if (!confirmed) return;

      setActionInProgress('reprocess');
      try {
        const documentIds = nonScrapeItems.map(item => item.documentId);
        await onReprocess(documentIds);
        setSelectedItems([]);
      } catch (err) {
        console.error('Reprocess failed:', err);
        window.alert(`Reprocess failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      } finally {
        setActionInProgress(null);
      }
    } else if (actionId === 'delete') {
      if (!onDelete) return;

      const confirmed = window.confirm(
        `Are you sure you want to delete ${selectedItems.length} item(s)? This will remove them from S3 and the Knowledge Base. This cannot be undone.`
      );
      if (!confirmed) return;

      setActionInProgress('delete');
      try {
        const documentIds = selectedItems.map(item => item.documentId);
        await onDelete(documentIds);
        setSelectedItems([]);
      } catch (err) {
        console.error('Delete failed:', err);
      } finally {
        setActionInProgress(null);
      }
    }
  };

  const columnDefinitions = [
    {
      id: 'filename',
      header: 'Name',
      cell: (item: DocumentItem) => (
        <Link onFollow={() => onSelectDocument(item.documentId, item.type)}>
          {item.filename}
        </Link>
      ),
      sortingField: 'filename',
      isRowHeader: true,
      width: 300,
      minWidth: 150
    },
    {
      id: 'type',
      header: 'Type',
      cell: (item: DocumentItem) => getTypeLabel(item.type),
      sortingField: 'type'
    },
    {
      id: 'status',
      header: 'Status',
      cell: (item: DocumentItem) => getStatusIndicator(item.status, item.type),
      sortingField: 'status'
    },
    {
      id: 'progress',
      header: 'Progress',
      cell: (item: DocumentItem) => {
        if (item.type === 'scrape' && ['DISCOVERING', 'PROCESSING'].includes(item.status)) {
          const progress = item.totalPages && item.totalPages > 0
            ? Math.round(((item.processedCount || 0) / item.totalPages) * 100)
            : 0;
          return (
            <ProgressBar
              value={progress}
              label={`${item.processedCount || 0}/${item.totalPages || 0} pages`}
            />
          );
        }
        if (item.type === 'scrape' && item.totalPages && item.totalPages > 0) {
          return `${item.processedCount || 0}/${item.totalPages} pages`;
        }
        return item.totalPages ? `${item.totalPages} pages` : '-';
      }
    },
    {
      id: 'createdAt',
      header: 'Created',
      cell: (item: DocumentItem) => item.createdAt ? new Date(item.createdAt).toLocaleString() : '-',
      sortingField: 'createdAt'
    }
  ];

  return (
    <div className="table-scroll-container">
      <Table
        {...collectionProps}
        header={
        <Header
          variant="h2"
          counter={`(${filteredDocuments.length}${filteredDocuments.length !== documents.length ? ` of ${documents.length}` : ''})`}
          description={`Showing: ${dateRangeLabel}`}
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Popover
                header="Document Actions"
                content={
                  <SpaceBetween size="s">
                    <div>
                      <strong>Reindex</strong> - Re-extracts metadata from existing OCR text and reingests to the Knowledge Base. Faster than Reprocess since it skips OCR. Use when metadata extraction settings have changed.
                    </div>
                    <div>
                      <strong>Reprocess</strong> - Re-runs the full processing pipeline: OCR extraction, metadata generation, and Knowledge Base ingestion. Use when documents failed processing or the source file has changed.
                    </div>
                    <div>
                      <strong>Delete</strong> - Permanently removes documents from both the S3 data bucket and the Knowledge Base. This action cannot be undone.
                    </div>
                    <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e9ebed' }}>
                      <strong>Tip:</strong> To reindex all documents at once, use the Reindex feature in Settings.
                    </div>
                  </SpaceBetween>
                }
                triggerType="custom"
                dismissButton={false}
                position="bottom"
                size="large"
              >
                <Button variant="inline-icon" iconName="status-info" ariaLabel="About document actions" />
              </Popover>
              <ButtonDropdown
                items={[
                  { id: 'reindex', text: 'Reindex', description: 'Re-extract metadata only' },
                  {
                    id: 'reprocess',
                    text: 'Reprocess',
                    description: isDemoMode ? 'Disabled in Demo Mode' : 'Full pipeline (OCR + metadata)',
                    disabled: isDemoMode
                  },
                  {
                    id: 'delete',
                    text: 'Delete',
                    description: isDemoMode ? 'Disabled in Demo Mode' : 'Remove from S3 and KB',
                    disabled: isDemoMode
                  }
                ]}
                onItemClick={({ detail }) => handleAction(detail.id)}
                disabled={selectedItems.length === 0 || actionInProgress !== null}
                loading={actionInProgress !== null}
              >
                Actions{selectedItems.length > 0 ? ` (${selectedItems.length})` : ''}
              </ButtonDropdown>
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
      visibleColumns={preferences.visibleContent}
      items={items}
      loading={loading}
      loadingText="Loading items"
      selectionType="multi"
      selectedItems={selectedItems}
      onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems as DocumentItem[])}
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
            const newPrefs: TablePreferences = {
              pageSize: detail.pageSize || DEFAULT_PREFERENCES.pageSize,
              visibleContent: (detail.visibleContent as string[]) || DEFAULT_PREFERENCES.visibleContent,
              dateRange: (detail.custom as { dateRange?: string })?.dateRange || preferences.dateRange
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
                  value={(value as { dateRange?: string })?.dateRange || '7'}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setValue({ ...value, dateRange: e.target.value })}
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
    </div>
  );
};
