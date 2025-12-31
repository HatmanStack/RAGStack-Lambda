import React from 'react';
import {
  Box,
  Button,
  FormField,
  SpaceBetween,
  Textarea,
  Alert
} from '@cloudscape-design/components';

export const CaptionInput = ({
  userCaption,
  aiCaption,
  onUserCaptionChange,
  onGenerateCaption,
  generating,
  error
}) => {
  const combinedCaption = [userCaption, aiCaption].filter(Boolean).join('. ');

  return (
    <SpaceBetween size="m">
      <FormField
        label="Your caption"
        description="Describe the image content. This helps with search and retrieval."
      >
        <Textarea
          value={userCaption}
          onChange={({ detail }) => onUserCaptionChange(detail.value)}
          placeholder="Enter a description for this image..."
          rows={3}
        />
      </FormField>

      <SpaceBetween direction="horizontal" size="s">
        <Button
          onClick={onGenerateCaption}
          loading={generating}
          disabled={generating}
          iconName="gen-ai"
        >
          {generating ? 'Generating...' : 'Generate AI Caption'}
        </Button>
      </SpaceBetween>

      {error && (
        <Alert type="error" dismissible>
          {error}
        </Alert>
      )}

      {aiCaption && (
        <FormField label="AI-generated caption">
          <div
            style={{
              backgroundColor: '#f0f9ff',
              borderRadius: '4px',
              border: '1px solid #bae6fd',
              padding: '8px'
            }}
          >
            <Box variant="small" color="text-body-secondary">
              {aiCaption}
            </Box>
          </div>
        </FormField>
      )}

      {combinedCaption && (
        <FormField label="Final caption (user + AI)">
          <div
            style={{
              backgroundColor: '#f5f5f5',
              borderRadius: '4px',
              border: '1px solid #d1d5db',
              padding: '8px'
            }}
          >
            {combinedCaption}
          </div>
        </FormField>
      )}
    </SpaceBetween>
  );
};
