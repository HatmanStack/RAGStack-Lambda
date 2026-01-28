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
import { useMetadataStats, useFilterExamples, useRegenerateFilterExamples } from '../../hooks/useMetadata';
import { MetadataMetrics } from './MetadataMetrics';
import { FilterExamples } from './FilterExamples';
import { AnalyzeButton } from './AnalyzeButton';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import type { GqlResponse } from '../../types/graphql';

export const MetadataPanel: React.FC = () => {
  // Generate GraphQL client (memoized to avoid recreating on re-renders)
  const client = useMemo(() => generateClient(), []);
  const [expanded, setExpanded] = useState(false);
  const {
    stats,
    totalKeys,
    lastAnalyzed,
    loading: statsLoading,
    error: statsError,
    refetch: refetchStats,
    deleteKey,
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

  // Track filter keys (allowlist for filter generation)
  const [filterKeys, setFilterKeys] = useState<string[]>([]);

  // Regenerate filter examples hook
  const { regenerate, loading: regenerating } = useRegenerateFilterExamples();

  // Load disabled examples and filter keys from configuration
  useEffect(() => {
    const loadConfig = async () => {
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
          if (Array.isArray(custom.metadata_filter_keys)) {
            setFilterKeys(custom.metadata_filter_keys);
          }
        }
      } catch (err) {
        console.error('Failed to load configuration:', err);
      }
    };
    loadConfig();
  }, [client]);

  // Compute enabled list from examples minus disabled (memoized)
  const enabledExamples = useMemo(
    () => examples.map(e => e.name).filter(name => !disabledExamples.includes(name)),
    [examples, disabledExamples]
  );

  const handleToggleExample = useCallback((name: string, enabled: boolean) => {
    // Capture previous state for rollback on failure
    const previousDisabled = [...disabledExamples];

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
          // Rollback optimistic update on error
          setDisabledExamples(previousDisabled);
        }
      } catch (err: unknown) {
        console.error('Failed to save disabled examples:', err);
        // Rollback optimistic update on error
        setDisabledExamples(previousDisabled);
      }
    })();
  }, [client, disabledExamples]);

  const handleAnalysisComplete = useCallback(() => {
    // Refetch stats and examples, clear local disabled list (backend cleared it)
    refetchStats();
    refetchExamples();
    setDisabledExamples([]); // Backend clears disabled after replacement
  }, [refetchStats, refetchExamples]);

  const handleFilterKeysChange = useCallback(async (keys: string[]) => {
    const previousKeys = [...filterKeys];
    setFilterKeys(keys);

    try {
      const response = await client.graphql({
        query: updateConfiguration,
        variables: {
          customConfig: JSON.stringify({
            metadata_filter_keys: keys,
          }),
        },
      }) as GqlResponse;
      if (response.errors?.length) {
        console.error('Failed to save filter keys:', response.errors);
        setFilterKeys(previousKeys);
      }
    } catch (err) {
      console.error('Failed to save filter keys:', err);
      setFilterKeys(previousKeys);
    }
  }, [client, filterKeys]);

  const handleRegenerateExamples = useCallback(async () => {
    const result = await regenerate();
    if (result?.success) {
      refetchExamples();
    }
  }, [regenerate, refetchExamples]);

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
          content="Samples vectors from your Knowledge Base to discover metadata fields and generate filter examples for improved search."
          dismissButton={false}
          position="right"
          size="medium"
        >
          <span style={{ position: 'relative', top: '-2px' }}>
            <Button variant="inline-icon" iconName="status-info" ariaLabel="About Metadata Analysis" />
          </span>
        </Popover>
      }
      headerActions={expanded ? <AnalyzeButton onComplete={handleAnalysisComplete} /> : undefined}
      expanded={expanded}
      onChange={({ detail }) => setExpanded(detail.expanded)}
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
              onDeleteKey={deleteKey}
            />

            <FilterExamples
              examples={examples}
              totalExamples={totalExamples}
              lastGenerated={lastGenerated}
              loading={examplesLoading}
              enabledExamples={enabledExamples || []}
              onToggleExample={handleToggleExample}
              error={examplesError}
              filterKeys={filterKeys}
              onFilterKeysChange={handleFilterKeysChange}
              onRegenerateExamples={handleRegenerateExamples}
              regenerating={regenerating}
            />
          </SpaceBetween>
        )}
      </SpaceBetween>
    </ExpandableSection>
  );
};
