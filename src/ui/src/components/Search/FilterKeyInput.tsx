import React, { useMemo } from 'react';
import { Multiselect } from '@cloudscape-design/components';
import type { MultiselectProps } from '@cloudscape-design/components';
import { useKeyLibrary } from '../../hooks/useKeyLibrary';

interface FilterKeyInputProps {
  value: string[];
  onChange: (keys: string[]) => void;
  disabled?: boolean;
}

export function FilterKeyInput({ value, onChange, disabled }: FilterKeyInputProps) {
  const { keys: libraryKeys, loading } = useKeyLibrary();

  // Build options from active library keys only (no create option)
  const options = useMemo(() => {
    // Filter to only active keys
    const activeKeys = libraryKeys.filter(key => key.status === 'active');

    return activeKeys.map((key) => ({
      label: key.keyName,
      value: key.keyName,
      description: `${key.occurrenceCount} occurrences · ${key.dataType}`,
    }));
  }, [libraryKeys]);

  // Convert selected values to Multiselect format
  const selectedOptions = useMemo(() => {
    return value.map((v) => {
      const existing = options.find((o) => o.value === v);
      return existing || { label: v, value: v };
    });
  }, [value, options]);

  const handleChange: MultiselectProps['onChange'] = ({ detail }) => {
    const selectedValues = detail.selectedOptions.map((opt) => opt.value || '');
    onChange(selectedValues);
  };

  return (
    <Multiselect
      selectedOptions={selectedOptions}
      onChange={handleChange}
      options={options}
      placeholder="Select keys to use for filter generation"
      filteringType="auto"
      filteringPlaceholder="Search keys..."
      disabled={disabled}
      statusType={loading ? 'loading' : 'finished'}
      loadingText="Loading keys..."
      tokenLimit={5}
      hideTokens={false}
      expandToViewport
      deselectAriaLabel={(option) => `Remove ${option.label}`}
    />
  );
}
