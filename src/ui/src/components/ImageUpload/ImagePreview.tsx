import React from 'react';
import { Box, Button, SpaceBetween } from '@cloudscape-design/components';

interface ImagePreviewProps {
  file: File;
  previewUrl: string | null;
  onRemove?: () => void;
}

export const ImagePreview = ({ file, previewUrl, onRemove }: ImagePreviewProps) => {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  return (
    <Box padding="s">
      <SpaceBetween size="s">
        <Box textAlign="center">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={file.name}
              style={{
                maxWidth: '300px',
                maxHeight: '200px',
                borderRadius: '8px',
                objectFit: 'contain',
                border: '1px solid #d1d5db'
              }}
            />
          ) : (
            <div
              style={{
                backgroundColor: '#f3f4f6',
                borderRadius: '8px',
                minHeight: '100px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '40px',
                textAlign: 'center'
              }}
            >
              <Box fontSize="display-l">🖼️</Box>
            </div>
          )}
        </Box>

        <Box variant="div">
          <SpaceBetween size="xxs">
            <Box variant="strong">{file.name}</Box>
            <Box variant="small" color="text-body-secondary">
              {formatFileSize(file.size)} • {file.type}
            </Box>
          </SpaceBetween>
        </Box>

        {onRemove && (
          <Button onClick={onRemove} variant="link">
            Remove image
          </Button>
        )}
      </SpaceBetween>
    </Box>
  );
};
