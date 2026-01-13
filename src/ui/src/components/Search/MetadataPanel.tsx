import React, { useCallback, useState, useEffect, useMemo } from 'react';
import {
  ExpandableSection,
  SpaceBetween,
  Box,
  Alert,
  Popover,
  Button,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { useMetadataStats, useFilterExamples } from '../../hooks/useMetadata';
import { MetadataMetrics } from './MetadataMetrics';
import { FilterExamples } from './FilterExamples';
import { AnalyzeButton } from './AnalyzeButton';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import type { GqlResponse } from '../../types/graphql';

export const MetadataPanel: React.FC = () => {
  // Generate GraphQL client (memoized to avoid recreating on re-renders)
  const client = useMemo(() => generateClient(), []);
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

  // Load disabled examples from configuration
  useEffect(() => {
    const loadDisabled = async () => {
      try {
        const response = await client.graphql({ query: getConfiguration }) as GqlResponse;
        if (response.errors?.length) {
          console.error('GraphQL errors loading configuration:', response.errors);
          return;
        }
        const config = response.data?.getConfiguration as { Custom?: string } | undefined;
        if (config?.Custom) {
          const custom = JSON.parse(config.Custom);
          if (Array.isArray(custom.metadata_filter_examples_disabled)) {
            setDisabledExamples(custom.metadata_filter_examples_disabled);
          }
        }
      } catch (err) {
        console.error('Failed to load disabled examples:', err);
      }
    };
    loadDisabled();
  }, [client]);

  // Compute enabled list from examples minus disabled (memoized)
  const enabledExamples = useMemo(
    () => examples.map(e => e.name).filter(name => !disabledExamples.includes(name)),
    [examples, disabledExamples]
  );

  const handleToggleExample = useCallback((name: string, enabled: boolean) => {
    // Optimistic update using functional form to avoid stale closures
    setDisabledExamples(prev => {
      if (enabled) {
        return prev.filter(n => n !== name);
      } else {
        return prev.includes(name) ? prev : [...prev, name];
      }
    });

    // Compute new value for API call (can't use state in async callback)
    const newDisabled = enabled
      ? disabledExamples.filter(n => n !== name)
      : disabledExamples.includes(name) ? disabledExamples : [...disabledExamples, name];

    // Save to configuration asynchronously
    (async () => {
      try {
        const response = await client.graphql({
          query: updateConfiguration,
          variables: {
            customConfig: JSON.stringify({
              metadata_filter_examples_disabled: newDisabled,
            }),
          },
        }) as GqlResponse;
        if (response.errors?.length) {
          console.error('Failed to save disabled examples:', response.errors);
        }
      } catch (err: unknown) {
        console.error('Failed to save disabled examples:', err);
      }
    })();
  }, [client, disabledExamples]);

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
          triggerType="custom"
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
          <Button
            variant="inline-icon"
            iconName="status-info"
            ariaLabel="About Metadata Analysis"
          />
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
