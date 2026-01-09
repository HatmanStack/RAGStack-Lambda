import React, { useState } from 'react';
import {
  Table,
  Header,
  Box,
  SpaceBetween,
  StatusIndicator,
  Button,
  Modal,
  Toggle,
  Popover,
  Icon,
  ExpandableSection,
} from '@cloudscape-design/components';
import type { FilterExample } from '../../hooks/useMetadata';

interface FilterExamplesProps {
  examples: FilterExample[];
  totalExamples: number;
  lastGenerated: string | null;
  loading: boolean;
  error: string | null;
  enabledExamples?: string[]; // Names of enabled examples
  onToggleExample?: (name: string, enabled: boolean) => void;
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
        <Box textAlign="center" color="inherit" padding="l">
          <b>No filter examples</b>
          <Box variant="p" color="inherit">
            Run the metadata analyzer to generate filter examples based on your documents.
          </Box>
        </Box>
      </ExpandableSection>
    );
  }

  const parseFilter = (filterJson: string): object => {
    try {
      return JSON.parse(filterJson);
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
            content={
              <SpaceBetween size="s">
                <Box>
                  <strong>Few-shot learning:</strong> Enabled examples are fed to the LLM as
                  reference patterns when generating metadata filters for your queries.
                </Box>
                <Box>
                  <strong>Control what the LLM sees:</strong> Toggle examples on/off to control
                  which patterns guide filter generation. Disable irrelevant examples to improve
                  filter accuracy for your use case.
                </Box>
                <Box>
                  <strong>Re-analysis:</strong> When you run "Analyze Metadata" again, your
                  enabled filter examples are preserved. New examples will be created to replace
                  the disabled examples.
                </Box>
                <Box>
                  <strong>Multi-slice retrieval:</strong> When enabled, each query generates
                  parallel searches with different metadata filters based on these examples.
                </Box>
              </SpaceBetween>
            }
            dismissButton={false}
            position="right"
            size="large"
          >
            <Box color="text-status-info" display="inline">
              <Icon name="status-info" />
            </Box>
          </Popover>
        }
        headerDescription={`${enabledCount}/${totalExamples} enabled • Last generated: ${formatDate(lastGenerated)}`}
        defaultExpanded={false}
      >
        <Table
          loading={loading}
          loadingText="Loading filter examples..."
          items={examples}
          wrapLines={false}
          stickyColumns={{ first: 2 }}
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
                Run the analyzer to generate filter examples.
              </Box>
            </Box>
          }
          variant="embedded"
          stripedRows
        />
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
              <Box variant="awsui-key-label">Filter JSON</Box>
              <pre
                style={{
                  backgroundColor: '#1d1f21',
                  color: '#c5c8c6',
                  padding: '12px',
                  borderRadius: '4px',
                  overflow: 'auto',
                  fontSize: '13px',
                  fontFamily: 'monospace',
                  margin: '8px 0 0 0',
                }}
              >
                <code>{JSON.stringify(parseFilter(selectedFilter.filter), null, 2)}</code>
              </pre>
            </Box>
          </SpaceBetween>
        </Modal>
      )}
    </>
  );
};
