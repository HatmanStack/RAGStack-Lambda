import React, { useCallback, useState, useEffect, useMemo } from 'react';
import {
  ExpandableSection,
  SpaceBetween,
  Box,
  Alert,
  Popover,
  Icon,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { useMetadataStats, useFilterExamples } from '../../hooks/useMetadata';
import { MetadataMetrics } from './MetadataMetrics';
import { FilterExamples } from './FilterExamples';
import { AnalyzeButton } from './AnalyzeButton';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import type { GqlResponse } from '../../types/graphql';

const client = generateClient();

export const MetadataPanel: React.FC = () => {
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

  // Track DISABLED examples (inverted: all enabled by default, store only disabled)
  const [disabledExamples, setDisabledExamples] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Load disabled examples from configuration
  useEffect(() => {
    const loadDisabled = async () => {
      try {
        const response = await client.graphql({ query: getConfiguration }) as GqlResponse;
        const config = response.data?.getConfiguration as { Custom?: string } | undefined;
        if (config?.Custom) {
          const custom = JSON.parse(config.Custom);
          if (Array.isArray(custom.metadata_filter_examples_disabled)) {
            setDisabledExamples(custom.metadata_filter_examples_disabled);
          }
        }
      } catch (err) {
        console.error('Failed to load disabled examples:', err);
      } finally {
        setLoaded(true);
      }
    };
    loadDisabled();
  }, []);

  // Compute enabled list from examples minus disabled (memoized)
  const enabledExamples = useMemo(
    () => examples.map(e => e.name).filter(name => !disabledExamples.includes(name)),
    [examples, disabledExamples]
  );

  const handleToggleExample = useCallback((name: string, enabled: boolean) => {
    // Update local state immediately
    setDisabledExamples(prev => {
      const newDisabled = enabled
        ? prev.filter(n => n !== name) // Remove from disabled
        : [...prev, name]; // Add to disabled

      // Save to configuration asynchronously (don't block UI)
      (async () => {
        try {
          await client.graphql({
            query: updateConfiguration,
            variables: {
              customConfig: JSON.stringify({
                metadata_filter_examples_disabled: newDisabled,
              }),
            },
          });
        } catch (err) {
          console.error('Failed to save disabled examples:', err);
        }
      })();

      return newDisabled;
    });
  }, []);

  const handleAnalysisComplete = useCallback(() => {
    // Refetch stats and examples, clear local disabled list (backend cleared it)
    refetchStats();
    refetchExamples();
    setDisabledExamples([]); // Backend clears disabled after replacement
  }, [refetchStats, refetchExamples]);

  // Show nothing if both have errors (service not configured)
  const serviceNotConfigured =
    statsError?.includes('not configured') && examplesError?.includes('not configured');

  if (serviceNotConfigured) {
    return null;
  }

  return (
    <ExpandableSection
      variant="container"
      headerText="Metadata Analysis"
      headerInfo={
        <Popover
          header="About Metadata Analysis"
          content={
            <SpaceBetween size="s">
              <Box>
                <strong>What it does:</strong> Samples vectors from your Knowledge Base to discover
                metadata fields and generate filter examples for improved search.
              </Box>
              <Box>
                <strong>Key Statistics:</strong> Shows which metadata keys exist in your documents,
                their data types, and how often they appear.
              </Box>
              <Box>
                <strong>Filter Examples:</strong> AI-generated filter patterns based on your actual
                metadata. When multi-slice retrieval is enabled, these examples are fed to the LLM
                after each user query to generate targeted metadata filters, creating parallel search
                vectors that improve recall by searching both filtered and unfiltered results.
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
      headerDescription="Discover metadata fields and filter patterns in your documents"
      headerActions={<AnalyzeButton onComplete={handleAnalysisComplete} />}
      defaultExpanded={false}
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
          <SpaceBetween size="xl">
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
              enabledExamples={enabledExamples || []}
              onToggleExample={handleToggleExample}
              error={examplesError}
            />
          </SpaceBetween>
        )}
      </SpaceBetween>
    </ExpandableSection>
  );
};
