import React, { useState, useMemo, useCallback } from 'react';
import {
  Multiselect,
  FormField,
  Alert,
  SpaceBetween,
  Button,
  Box,
} from '@cloudscape-design/components';
import type { MultiselectProps } from '@cloudscape-design/components';
import { useKeyLibrary } from '../../hooks/useKeyLibrary';
import { findSimilarKeys } from '../../utils/similarity';

export interface MetadataKeyInputProps {
  value: string[];
  onChange: (keys: string[]) => void;
  disabled?: boolean;
}

interface SimilarityWarning {
  customKey: string;
  similarKey: string;
  similarity: number;
}

export function MetadataKeyInput({ value, onChange, disabled }: MetadataKeyInputProps) {
  const { keys: libraryKeys, loading } = useKeyLibrary();
  const [filteringText, setFilteringText] = useState('');
  const [similarityWarning, setSimilarityWarning] = useState<SimilarityWarning | null>(null);

  // Build options from library keys
  const options = useMemo(() => {
    return libraryKeys.map((key) => ({
      label: key.keyName,
      value: key.keyName,
      description: `${key.occurrenceCount} occurrences · ${key.dataType}`,
    }));
  }, [libraryKeys]);

  // Get existing key names for similarity check
  const existingKeyNames = useMemo(() => {
    return libraryKeys.map((k) => k.keyName);
  }, [libraryKeys]);

  // Convert selected values to Multiselect format
  const selectedOptions = useMemo(() => {
    return value.map((v) => {
      const existing = options.find((o) => o.value === v);
      return existing || { label: v, value: v };
    });
  }, [value, options]);

  // Check for similar keys when filtering text changes
  const handleFilteringChange = useCallback(
    (text: string) => {
      setFilteringText(text);

      if (text.length < 2) {
        setSimilarityWarning(null);
        return;
      }

      const normalizedText = text.toLowerCase().trim();

      // Don't warn if exact match exists
      if (existingKeyNames.some((k) => k.toLowerCase() === normalizedText)) {
        setSimilarityWarning(null);
        return;
      }

      // Check for similar keys
      const similar = findSimilarKeys(text, existingKeyNames, 0.7);
      if (similar.length > 0) {
        setSimilarityWarning({
          customKey: text,
          similarKey: similar[0].keyName,
          similarity: similar[0].similarity,
        });
      } else {
        setSimilarityWarning(null);
      }
    },
    [existingKeyNames]
  );

  const handleChange: MultiselectProps['onChange'] = ({ detail }) => {
    const selectedValues = detail.selectedOptions.map((opt) => opt.value || '');
    onChange(selectedValues);
    setSimilarityWarning(null);
  };

  const handleUseExisting = () => {
    if (similarityWarning) {
      // Add the existing key instead of the custom one
      if (!value.includes(similarityWarning.similarKey)) {
        onChange([...value, similarityWarning.similarKey]);
      }
      setFilteringText('');
      setSimilarityWarning(null);
    }
  };

  const handleKeepCustom = () => {
    if (similarityWarning) {
      // Add the custom key
      if (!value.includes(similarityWarning.customKey)) {
        onChange([...value, similarityWarning.customKey]);
      }
      setFilteringText('');
      setSimilarityWarning(null);
    }
  };

  return (
    <SpaceBetween size="xs">
      <Multiselect
        selectedOptions={selectedOptions}
        onChange={handleChange}
        options={options}
        placeholder="Select or type keys to extract"
        filteringType="auto"
        filteringPlaceholder="Search keys..."
        filteringText={filteringText}
        onFilteringChange={({ detail }) => handleFilteringChange(detail.filteringText)}
        disabled={disabled}
        statusType={loading ? 'loading' : 'finished'}
        loadingText="Loading keys..."
        tokenLimit={5}
        hideTokens={false}
        expandToViewport
        deselectAriaLabel={(option) => `Remove ${option.label}`}
      />

      {similarityWarning && (
        <Alert type="warning" header="Similar key exists">
          <SpaceBetween size="xs">
            <Box>
              "{similarityWarning.customKey}" is similar to existing key "
              {similarityWarning.similarKey}" ({Math.round(similarityWarning.similarity * 100)}%
              match).
            </Box>
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={handleUseExisting} variant="primary">
                Use Existing
              </Button>
              <Button onClick={handleKeepCustom}>Keep Custom</Button>
            </SpaceBetween>
          </SpaceBetween>
        </Alert>
      )}
    </SpaceBetween>
  );
}
