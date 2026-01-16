import React from 'react';
import {
  Box,
  Checkbox,
  FormField,
  SpaceBetween,
  Textarea,
  Alert
} from '@cloudscape-design/components';

interface CaptionInputProps {
  userCaption: string;
  extractText: boolean;
  onUserCaptionChange: (value: string) => void;
  onExtractTextChange: (checked: boolean) => void;
  error: string | null;
}

export const CaptionInput = ({
  userCaption,
  extractText,
  onUserCaptionChange,
  onExtractTextChange,
  error
}: CaptionInputProps) => {
  return (
    <SpaceBetween size="m">
      <FormField
        label="Caption (optional)"
        description="Describe the image with context only you know (names, dates, events). Visual search works without a caption."
      >
        <Textarea
          value={userCaption}
          onChange={({ detail }) => onUserCaptionChange(detail.value)}
          placeholder="e.g., Company retreat 2024, Team photo with Sarah and Mike..."
          rows={3}
        />
      </FormField>

      <Checkbox
        checked={extractText}
        onChange={({ detail }) => onExtractTextChange(detail.checked)}
      >
        <Box>
          <Box fontWeight="bold">Extract text from image (OCR)</Box>
          <Box variant="small" color="text-body-secondary">
            Use AI to extract visible text (signs, labels, memes, documents) for searchability
          </Box>
        </Box>
      </Checkbox>

      {error && (
        <Alert type="error" dismissible>
          {error}
        </Alert>
      )}

      {userCaption && (
        <FormField label="Caption preview">
          <div
            style={{
              backgroundColor: '#f5f5f5',
              borderRadius: '4px',
              border: '1px solid #d1d5db',
              padding: '8px'
            }}
          >
            {userCaption}
          </div>
        </FormField>
      )}
    </SpaceBetween>
  );
};
