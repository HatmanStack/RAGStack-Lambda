import React, { useState } from 'react';
import {
  Table,
  Box,
  SpaceBetween,
  StatusIndicator,
  Button,
  Modal,
  Toggle,
  Popover,
  ExpandableSection,
  CopyToClipboard,
  FormField,
} from '@cloudscape-design/components';
import type { FilterExample } from '../../hooks/useMetadata';
import { FilterKeyInput } from './FilterKeyInput';

interface FilterExamplesProps {
  examples: FilterExample[];
  totalExamples: number;
  lastGenerated: string | null;
  loading: boolean;
  error: string | null;
  enabledExamples?: string[]; // Names of enabled examples
  onToggleExample?: (name: string, enabled: boolean) => void;
  // New props for filter keys
  filterKeys?: string[];
  onFilterKeysChange?: (keys: string[]) => void;
  onRegenerateExamples?: () => Promise<void>;
  regenerating?: boolean;
}

const formatDate = (isoString: string | null): string => {
  if (!isoString) return 'Never';
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch {
    return isoString;
  }
};

export const FilterExamples: React.FC<FilterExamplesProps> = ({
  examples,
  totalExamples,
  lastGenerated,
  loading,
  error,
  enabledExamples = [],
  onToggleExample,
  filterKeys,
  onFilterKeysChange,
  onRegenerateExamples,
  regenerating,
}) => {
  const [selectedFilter, setSelectedFilter] = useState<FilterExample | null>(null);

  // Check if example is enabled (in the enabled list)
  const isEnabled = (name: string) => enabledExamples.includes(name);

  const enabledCount = examples.filter(e => isEnabled(e.name)).length;

  if (error) {
    return (
      <ExpandableSection
        variant="container"
        headerText="Filter Examples"
        defaultExpanded={false}
      >
        <StatusIndicator type="error">{error}</StatusIndicator>
      </ExpandableSection>
    );
  }

  if (examples.length === 0 && !loading) {
    return (
      <ExpandableSection
        variant="container"
        headerText="Filter Examples"
        headerDescription="No examples yet"
        defaultExpanded={false}
      >
        <SpaceBetween size="l">
          {/* Filter Keys Configuration */}
          <FormField
            label="Keys to Use for Filters"
            description="Select which metadata keys should be used when generating filter examples. Only these keys will be considered."
          >
            <SpaceBetween size="xs">
              <FilterKeyInput
                value={filterKeys || []}
                onChange={(keys) => onFilterKeysChange?.(keys)}
                disabled={regenerating}
              />
              <Box>
                <SpaceBetween direction="horizontal" size="xs">
                  <Button
                    variant="primary"
                    onClick={() => onRegenerateExamples?.()}
                    loading={regenerating}
                    disabled={!filterKeys || filterKeys.length === 0}
                  >
                    Regenerate Examples
                  </Button>
                  {filterKeys && filterKeys.length === 0 && (
                    <Box color="text-status-inactive" variant="small">
                      Add at least one key to generate examples
                    </Box>
                  )}
                </SpaceBetween>
              </Box>
            </SpaceBetween>
          </FormField>

          <Box textAlign="center" color="inherit" padding="l">
            <b>No filter examples</b>
            <Box variant="p" color="inherit">
              {filterKeys && filterKeys.length > 0
                ? 'Click "Regenerate Examples" to create filter examples using the selected keys.'
                : 'Select keys above, then click "Regenerate Examples" to create filter examples.'}
            </Box>
          </Box>
        </SpaceBetween>
      </ExpandableSection>
    );
  }

  const parseFilter = (filterJson: string): object => {
    try {
      let parsed = JSON.parse(filterJson);
      // Handle double-encoded JSON strings
      if (typeof parsed === 'string') {
        parsed = JSON.parse(parsed);
      }
      return parsed;
    } catch {
      return {};
    }
  };

  return (
    <>
      <ExpandableSection
        variant="container"
        headerText="Filter Examples"
        headerInfo={
          <Popover
            header="How Filter Examples Work"
            content="Select which metadata keys to use for filtering, then click 'Regenerate Examples' to create filter patterns. These examples guide the LLM when generating query-time filters. Toggle examples on/off to control which patterns are used."
            triggerType="custom"
            dismissButton={false}
            position="right"
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="About Filter Examples" />
            </span>
          </Popover>
        }
        headerDescription={`${enabledCount}/${totalExamples} enabled • Last generated: ${formatDate(lastGenerated)}`}
        defaultExpanded={false}
      >
        <SpaceBetween size="l">
          {/* Filter Keys Configuration */}
          <FormField
            label="Keys to Use for Filters"
            description="Select which metadata keys should be used when generating filter examples. Only these keys will be considered."
          >
            <SpaceBetween size="xs">
              <FilterKeyInput
                value={filterKeys || []}
                onChange={(keys) => onFilterKeysChange?.(keys)}
                disabled={regenerating}
              />
              <Box>
                <SpaceBetween direction="horizontal" size="xs">
                  <Button
                    variant="primary"
                    onClick={() => onRegenerateExamples?.()}
                    loading={regenerating}
                    disabled={!filterKeys || filterKeys.length === 0}
                  >
                    Regenerate Examples
                  </Button>
                  {filterKeys && filterKeys.length === 0 && (
                    <Box color="text-status-inactive" variant="small">
                      Add at least one key to generate examples
                    </Box>
                  )}
                </SpaceBetween>
              </Box>
            </SpaceBetween>
          </FormField>

          <div className="table-scroll-container">
          <Table
            loading={loading}
            loadingText="Loading filter examples..."
            items={examples}
            wrapLines={false}
            columnDefinitions={[
            {
              id: 'enabled',
              header: 'Active',
              cell: (item) => (
                <Toggle
                  checked={isEnabled(item.name)}
                  onChange={({ detail }) => {
                    onToggleExample?.(item.name, detail.checked);
                  }}
                  disabled={!onToggleExample}
                />
              ),
              width: 80,
            },
            {
              id: 'name',
              header: 'Name',
              cell: (item) => <Box fontWeight="bold">{item.name}</Box>,
              minWidth: 150,
            },
            {
              id: 'description',
              header: 'Description',
              cell: (item) => (
                <Box color="text-body-secondary">{item.description}</Box>
              ),
              minWidth: 200,
            },
            {
              id: 'useCase',
              header: 'Use Case',
              cell: (item) => item.useCase,
              width: 120,
            },
            {
              id: 'actions',
              header: 'Filter',
              cell: (item) => (
                <Button
                  variant="inline-link"
                  onClick={() => setSelectedFilter(item)}
                  iconName="script"
                >
                  View
                </Button>
              ),
              width: 100,
            },
          ]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No filter examples</b>
              <Box variant="p" color="inherit">
                {filterKeys && filterKeys.length > 0
                  ? 'Click "Regenerate Examples" to create filter examples using the selected keys.'
                  : 'Select keys above, then click "Regenerate Examples" to create filter examples.'}
              </Box>
            </Box>
          }
            variant="embedded"
            stripedRows
          />
          </div>
        </SpaceBetween>
      </ExpandableSection>

      {selectedFilter && (
        <Modal
          visible={true}
          onDismiss={() => setSelectedFilter(null)}
          header={selectedFilter.name}
          footer={
            <Button variant="primary" onClick={() => setSelectedFilter(null)}>
              Close
            </Button>
          }
        >
          <SpaceBetween size="m">
            <Box>
              <Box variant="awsui-key-label">Description</Box>
              <Box>{selectedFilter.description}</Box>
            </Box>
            <Box>
              <Box variant="awsui-key-label">Use Case</Box>
              <Box>{selectedFilter.useCase}</Box>
            </Box>
            <Box>
              <SpaceBetween direction="horizontal" size="xs">
                <Box variant="awsui-key-label">Filter JSON</Box>
                <CopyToClipboard
                  variant="icon"
                  textToCopy={JSON.stringify(parseFilter(selectedFilter.filter), null, 2)}
                  copyButtonText="Copy"
                  copySuccessText="Copied!"
                  copyErrorText="Failed to copy"
                />
              </SpaceBetween>
              <pre
                style={{
                  backgroundColor: '#1a1a2e',
                  color: '#e6e6e6',
                  padding: '12px',
                  borderRadius: '6px',
                  overflow: 'auto',
                  fontSize: '13px',
                  fontFamily: "'Fira Code', 'Monaco', monospace",
                  lineHeight: '1.5',
                  margin: '8px 0 0 0',
                }}
              >
                {JSON.stringify(parseFilter(selectedFilter.filter), null, 2)}
              </pre>
            </Box>
          </SpaceBetween>
        </Modal>
      )}
    </>
  );
};
