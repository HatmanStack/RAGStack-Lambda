import React, { useMemo, useCallback } from 'react';
import { Multiselect } from '@cloudscape-design/components';
import type { MultiselectProps } from '@cloudscape-design/components';
import { useKeyLibrary } from '../../hooks/useKeyLibrary';

interface FilterKeyInputProps {
  value: string[];
  onChange: (keys: string[]) => void;
  disabled?: boolean;
}

export function FilterKeyInput({ value, onChange, disabled }: FilterKeyInputProps) {
  const { keys: libraryKeys, loading, error, refetch } = useKeyLibrary();

  // Build options from active library keys only (no create option)
  // Filter out keys with empty/falsy keyName for safety
  const options = useMemo(() => {
    const activeKeys = libraryKeys.filter(
      (key) => key.status === 'active' && key.keyName
    );

    return activeKeys.map((key) => ({
      label: key.keyName,
      value: key.keyName,
      description: `${key.occurrenceCount} occurrences · ${key.dataType}`,
    }));
  }, [libraryKeys]);

  // Convert selected values to Multiselect format
  // Filter out empty values to prevent blank selections
  const selectedOptions = useMemo(() => {
    return value
      .filter((v) => v) // Filter out empty/falsy values
      .map((v) => {
        const existing = options.find((o) => o.value === v);
        return existing || { label: v, value: v };
      });
  }, [value, options]);

  const handleChange: MultiselectProps['onChange'] = ({ detail }) => {
    // Filter out empty values before propagating
    const selectedValues = detail.selectedOptions
      .map((opt) => opt.value || '')
      .filter((v) => v);
    onChange(selectedValues);
  };

  // Handle retry on error
  const handleLoadItems = useCallback(() => {
    if (error) {
      refetch();
    }
  }, [error, refetch]);

  // Determine status type based on loading/error state
  const statusType = error ? 'error' : loading ? 'loading' : 'finished';

  return (
    <Multiselect
      selectedOptions={selectedOptions}
      onChange={handleChange}
      options={options}
      placeholder="Select keys to use for filter generation"
      filteringType="auto"
      filteringPlaceholder="Search keys..."
      disabled={disabled}
      statusType={statusType}
      loadingText="Loading keys..."
      errorText={error || 'Failed to load keys'}
      recoveryText="Retry"
      onLoadItems={handleLoadItems}
      tokenLimit={5}
      hideTokens={false}
      expandToViewport
      deselectAriaLabel={(option) => `Remove ${option.label}`}
    />
  );
}
