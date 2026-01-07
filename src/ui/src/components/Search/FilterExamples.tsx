import React, { useState } from 'react';
import {
  Container,
  Header,
  Cards,
  Badge,
  Box,
  SpaceBetween,
  StatusIndicator,
  Button,
  Modal,
  ExpandableSection,
} from '@cloudscape-design/components';
import type { FilterExample } from '../../hooks/useMetadata';

interface FilterExamplesProps {
  examples: FilterExample[];
  totalExamples: number;
  lastGenerated: string | null;
  loading: boolean;
  error: string | null;
  onApplyFilter?: (filter: string) => void;
}

const formatDate = (isoString: string | null): string => {
  if (!isoString) return 'Never';
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch (error) {
    console.warn('Failed to parse date:', isoString, error);
    return isoString;
  }
};

export const FilterExamples: React.FC<FilterExamplesProps> = ({
  examples,
  totalExamples,
  lastGenerated,
  loading,
  error,
  onApplyFilter,
}) => {
  const [selectedFilter, setSelectedFilter] = useState<FilterExample | null>(null);

  if (error) {
    return (
      <Container
        header={
          <Header variant="h2" description="AI-generated filter examples">
            Filter Examples
          </Header>
        }
      >
        <StatusIndicator type="error">{error}</StatusIndicator>
      </Container>
    );
  }

  if (examples.length === 0 && !loading) {
    return (
      <Container
        header={
          <Header variant="h2" description="AI-generated filter examples">
            Filter Examples
          </Header>
        }
      >
        <Box textAlign="center" color="inherit" padding="l">
          <b>No filter examples</b>
          <Box variant="p" color="inherit">
            Run the metadata analyzer to generate filter examples based on your documents.
          </Box>
        </Box>
      </Container>
    );
  }

  const parseFilter = (filterJson: string): object => {
    try {
      return JSON.parse(filterJson);
    } catch (error) {
      console.error('Failed to parse filter JSON:', filterJson, error);
      return {};
    }
  };

  return (
    <>
      <ExpandableSection
        variant="container"
        headerText="Filter Examples"
        headerDescription={`${totalExamples} examples • Last generated: ${formatDate(lastGenerated)}`}
        defaultExpanded={false}
      >
        <Cards
          loading={loading}
          loadingText="Loading filter examples..."
          items={examples}
          cardDefinition={{
            header: (item) => (
              <SpaceBetween direction="horizontal" size="xs">
                <span>{item.name}</span>
              </SpaceBetween>
            ),
            sections: [
              {
                id: 'description',
                content: (item) => (
                  <Box variant="p" color="text-body-secondary">
                    {item.description}
                  </Box>
                ),
              },
              {
                id: 'useCase',
                header: 'Use Case',
                content: (item) => <Badge>{item.useCase}</Badge>,
              },
              {
                id: 'actions',
                content: (item) => (
                  <SpaceBetween direction="horizontal" size="xs">
                    <Button
                      variant="link"
                      onClick={() => setSelectedFilter(item)}
                      iconName="script"
                    >
                      View Filter
                    </Button>
                    {onApplyFilter && (
                      <Button
                        variant="primary"
                        onClick={() => onApplyFilter(item.filter)}
                        iconName="check"
                      >
                        Apply
                      </Button>
                    )}
                  </SpaceBetween>
                ),
              },
            ],
          }}
          cardsPerRow={[{ cards: 1 }, { minWidth: 400, cards: 2 }, { minWidth: 800, cards: 3 }]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No filter examples</b>
              <Box variant="p" color="inherit">
                Run the analyzer to generate filter examples.
              </Box>
            </Box>
          }
        />
      </ExpandableSection>

      {selectedFilter && (
        <Modal
          visible={true}
          onDismiss={() => setSelectedFilter(null)}
          header={selectedFilter.name}
          footer={
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setSelectedFilter(null)}>
                Close
              </Button>
              {onApplyFilter && (
                <Button
                  variant="primary"
                  onClick={() => {
                    onApplyFilter(selectedFilter.filter);
                    setSelectedFilter(null);
                  }}
                >
                  Apply Filter
                </Button>
              )}
            </SpaceBetween>
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
