import React, { useCallback, useState, useEffect } from 'react';
import {
  Container,
  Header,
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

  // Track which filter examples are enabled (null = not yet loaded)
  const [enabledExamples, setEnabledExamples] = useState<string[] | null>(null);

  // Load enabled examples from configuration
  useEffect(() => {
    const loadEnabled = async () => {
      try {
        const response = await client.graphql({ query: getConfiguration }) as GqlResponse;
        const config = response.data?.getConfiguration as { Custom?: string } | undefined;
        if (config?.Custom) {
          const custom = JSON.parse(config.Custom);
          if (Array.isArray(custom.metadata_filter_examples_enabled)) {
            setEnabledExamples(custom.metadata_filter_examples_enabled);
            return;
          }
        }
        // No saved preference - will default to all enabled when examples load
        setEnabledExamples(null);
      } catch (err) {
        console.error('Failed to load enabled examples:', err);
        setEnabledExamples(null);
      }
    };
    loadEnabled();
  }, []);

  // When examples load, if no saved preference exists, default all to enabled
  useEffect(() => {
    if (enabledExamples === null && examples.length > 0) {
      setEnabledExamples(examples.map(e => e.name));
    }
  }, [examples, enabledExamples]);

  const handleToggleExample = useCallback(async (name: string, enabled: boolean) => {
    const current = enabledExamples || [];
    const newEnabled = enabled
      ? [...current, name]
      : current.filter(n => n !== name);

    setEnabledExamples(newEnabled);

    // Save to configuration immediately
    try {
      await client.graphql({
        query: updateConfiguration,
        variables: {
          customConfig: JSON.stringify({
            metadata_filter_examples_enabled: newEnabled,
          }),
        },
      });
    } catch (err) {
      console.error('Failed to save enabled examples:', err);
      // Revert on failure
      setEnabledExamples(current);
    }
  }, [enabledExamples]);

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
    </Container>
  );
};
