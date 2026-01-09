import React from 'react';
import {
  Container,
  Header,
  Table,
  Badge,
  Box,
  ColumnLayout,
  StatusIndicator,
  SpaceBetween,
  ExpandableSection,
} from '@cloudscape-design/components';
import type { MetadataKeyStats } from '../../hooks/useMetadata';

interface MetadataMetricsProps {
  stats: MetadataKeyStats[];
  totalKeys: number;
  lastAnalyzed: string | null;
  loading: boolean;
  error: string | null;
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

const getDataTypeBadge = (dataType: string) => {
  const colorMap: Record<string, 'blue' | 'green' | 'grey' | 'red'> = {
    string: 'blue',
    number: 'green',
    boolean: 'grey',
    list: 'red',
  };
  return (
    <span style={{ whiteSpace: 'nowrap' }}>
      <Badge color={colorMap[dataType] || 'grey'}>{dataType}</Badge>
    </span>
  );
};

export const MetadataMetrics: React.FC<MetadataMetricsProps> = ({
  stats,
  totalKeys,
  lastAnalyzed,
  loading,
  error,
}) => {
  if (error) {
    return (
      <Container
        header={
          <Header variant="h2" description="Metadata key statistics from your documents">
            Metadata Keys
          </Header>
        }
      >
        <StatusIndicator type="error">{error}</StatusIndicator>
      </Container>
    );
  }

  return (
    <ExpandableSection
      variant="container"
      headerText="Metadata Key Statistics"
      headerDescription="Keys discovered in your indexed documents"
      defaultExpanded={false}
    >
      <SpaceBetween size="m">
        <ColumnLayout columns={3} variant="text-grid">
          <div>
            <Box variant="awsui-key-label">Total Keys</Box>
            <Box variant="awsui-value-large">{totalKeys}</Box>
          </div>
          <div>
            <Box variant="awsui-key-label">Last Analyzed</Box>
            <Box>{formatDate(lastAnalyzed)}</Box>
          </div>
          <div>
            <Box variant="awsui-key-label">Status</Box>
            <StatusIndicator type={stats.length > 0 ? 'success' : 'pending'}>
              {stats.length > 0 ? 'Ready' : 'Not analyzed'}
            </StatusIndicator>
          </div>
        </ColumnLayout>

        <Table
          loading={loading}
          loadingText="Loading metadata keys..."
          items={stats}
          wrapLines={false}
          stickyColumns={{ first: 1 }}
          columnDefinitions={[
            {
              id: 'keyName',
              header: 'Key Name',
              cell: (item) => <Box fontWeight="bold">{item.keyName}</Box>,
              minWidth: 140,
            },
            {
              id: 'dataType',
              header: 'Type',
              cell: (item) => getDataTypeBadge(item.dataType),
              minWidth: 120,
            },
            {
              id: 'occurrenceCount',
              header: 'Occurrences',
              cell: (item) => item.occurrenceCount.toLocaleString(),
              width: 110,  // Fixed: number display
            },
            {
              id: 'sampleValues',
              header: 'Sample Values',
              cell: (item) => (
                <Box color="text-body-secondary">
                  {item.sampleValues?.slice(0, 3).join(', ') || '-'}
                  {item.sampleValues?.length > 3 && ` +${item.sampleValues.length - 3} more`}
                </Box>
              ),
              minWidth: 200,  // Flex: takes remaining space
            },
            {
              id: 'status',
              header: 'Status',
              cell: (item) => (
                <StatusIndicator type={item.status === 'active' ? 'success' : 'stopped'}>
                  {item.status}
                </StatusIndicator>
              ),
              width: 100,  // Fixed: "active"/"inactive"
            },
          ]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No metadata keys</b>
              <Box variant="p" color="inherit">
                Run the analyzer to discover metadata keys from your documents.
              </Box>
            </Box>
          }
          variant="embedded"
          stripedRows
          sortingDisabled
        />
      </SpaceBetween>
    </ExpandableSection>
  );
};
