import React, { useCallback } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Link,
  Alert,
} from '@cloudscape-design/components';
import { useMetadataStats, useFilterExamples } from '../../hooks/useMetadata';
import { MetadataMetrics } from './MetadataMetrics';
import { FilterExamples } from './FilterExamples';
import { AnalyzeButton } from './AnalyzeButton';

interface MetadataPanelProps {
  onApplyFilter?: (filter: string) => void;
}

export const MetadataPanel: React.FC<MetadataPanelProps> = ({ onApplyFilter }) => {
  const {
    stats,
    totalKeys,
    lastAnalyzed,
    loading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useMetadataStats();

  const {
    examples,
    totalExamples,
    lastGenerated,
    loading: examplesLoading,
    error: examplesError,
    refetch: refetchExamples,
  } = useFilterExamples();

  const handleAnalysisComplete = useCallback(() => {
    // Refetch both stats and examples after analysis
    refetchStats();
    refetchExamples();
  }, [refetchStats, refetchExamples]);

  // Show nothing if both have errors (service not configured)
  const serviceNotConfigured =
    statsError?.includes('not configured') && examplesError?.includes('not configured');

  if (serviceNotConfigured) {
    return null;
  }

  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Discover metadata fields and filter patterns in your documents"
          actions={<AnalyzeButton onComplete={handleAnalysisComplete} />}
          info={
            <Link external href="#" variant="info">
              Learn more
            </Link>
          }
        >
          Metadata Analysis
        </Header>
      }
    >
      <SpaceBetween size="l">
        {(totalKeys === 0 && totalExamples === 0 && !statsLoading && !examplesLoading) ? (
          <Alert type="info">
            <Box>
              <strong>No metadata analysis available</strong>
            </Box>
            <Box variant="p">
              Click "Analyze Metadata" to sample your Knowledge Base vectors, discover metadata
              fields, and generate filter examples. This process typically takes 1-2 minutes.
            </Box>
          </Alert>
        ) : (
          <>
            <MetadataMetrics
              stats={stats}
              totalKeys={totalKeys}
              lastAnalyzed={lastAnalyzed}
              loading={statsLoading}
              error={statsError}
            />

            <FilterExamples
              examples={examples}
              totalExamples={totalExamples}
              lastGenerated={lastGenerated}
              loading={examplesLoading}
              error={examplesError}
              onApplyFilter={onApplyFilter}
            />
          </>
        )}
      </SpaceBetween>
    </Container>
  );
};
