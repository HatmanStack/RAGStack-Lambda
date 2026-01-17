import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Box,
  SpaceBetween,
  ColumnLayout,
  Container,
  Header,
  StatusIndicator,
  Alert,
  Spinner,
  Button
} from '@cloudscape-design/components';
// Note: SpaceBetween and Button kept for content sections
import { useImage } from '../../hooks/useImage';
import type { ImageDetailProps, ImageDetailData, StatusConfig } from './types';

type StatusIndicatorType = 'pending' | 'in-progress' | 'success' | 'error' | 'info';

const STATUS_MAP: Record<string, StatusConfig> = {
  'PENDING': { type: 'pending', label: 'Pending' },
  'PROCESSING': { type: 'in-progress', label: 'Processing' },
  'INDEXED': { type: 'success', label: 'Indexed' },
  'FAILED': { type: 'error', label: 'Failed' }
};

export const ImageDetail = ({ imageId, visible, onDismiss }: ImageDetailProps) => {
  const { getImage } = useImage();
  const [image, setImage] = useState<ImageDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const loadImage = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPreviewContent(null);
    setPreviewError(null);

    try {
      const img = await getImage(imageId) as ImageDetailData;
      setImage(img);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load image');
    } finally {
      setLoading(false);
    }
  }, [getImage, imageId]);

  const loadPreview = useCallback(async () => {
    if (!image?.captionUrl) return;

    setPreviewLoading(true);
    setPreviewError(null);

    try {
      const response = await fetch(image.captionUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch preview: ${response.status}`);
      }
      const text = await response.text();
      setPreviewContent(text.length > 50000 ? text.slice(0, 50000) + '\n\n... (truncated)' : text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Failed to load preview');
    } finally {
      setPreviewLoading(false);
    }
  }, [image?.captionUrl]);

  useEffect(() => {
    if (visible && imageId) {
      loadImage();
    }
  }, [visible, imageId, loadImage]);

  if (!visible) return null;

  const getStatusConfig = (status: string): StatusConfig => {
    return STATUS_MAP[status] || { type: 'info', label: status };
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header="Image Details"
      size="large"
    >
      {loading && (
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
        </Box>
      )}

      {error && (
        <Alert type="error" header="Error">
          {error}
        </Alert>
      )}

      {image && (
        <SpaceBetween size="l">
          {/* Image Preview */}
          <Container header={<Header variant="h2">Preview</Header>}>
            <Box textAlign="center" padding="m">
              {image.thumbnailUrl ? (
                <img
                  src={image.thumbnailUrl}
                  alt={image.filename}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '400px',
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
                    display: 'inline-block',
                    padding: '40px'
                  }}
                >
                  <Box fontSize="display-l">🖼️</Box>
                  <Box color="text-body-secondary">No preview available</Box>
                </div>
              )}
            </Box>
          </Container>

          {/* Caption */}
          {image.caption && (
            <Container header={<Header variant="h2">Caption</Header>}>
              <Box>{image.caption}</Box>
              {(image.userCaption || image.aiCaption) && (
                <Box padding={{ top: 'm' }}>
                  <ColumnLayout columns={2} variant="text-grid">
                    {image.userCaption && (
                      <div>
                        <Box variant="awsui-key-label">User Caption</Box>
                        <div>{image.userCaption}</div>
                      </div>
                    )}
                    {image.aiCaption && (
                      <div>
                        <Box variant="awsui-key-label">AI Caption</Box>
                        <div>{image.aiCaption}</div>
                      </div>
                    )}
                  </ColumnLayout>
                </Box>
              )}
            </Container>
          )}

          {/* General Information */}
          <Container header={<Header variant="h2">General Information</Header>}>
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="awsui-key-label">Image ID</Box>
                <div style={{ fontFamily: 'monospace', fontSize: '12px' }}>{image.imageId}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Filename</Box>
                <div>{image.filename}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Status</Box>
                <div>
                  <StatusIndicator type={getStatusConfig(image.status).type as StatusIndicatorType}>
                    {getStatusConfig(image.status).label}
                  </StatusIndicator>
                </div>
              </div>
              <div>
                <Box variant="awsui-key-label">Content Type</Box>
                <div>{image.contentType || 'N/A'}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">File Size</Box>
                <div>{formatFileSize(image.fileSize)}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Created</Box>
                <div>{image.createdAt ? new Date(image.createdAt).toLocaleString() : 'N/A'}</div>
              </div>
            </ColumnLayout>
          </Container>

          {/* S3 Location */}
          <Container header={<Header variant="h2">S3 Location</Header>}>
            <Box variant="awsui-key-label">S3 URI</Box>
            <div style={{ fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all' }}>
              {image.s3Uri}
            </div>
          </Container>

          {/* Extracted Text */}
          {(image.extractedText || image.captionUrl) && (
            <Container
              header={
                <Header
                  variant="h2"
                  actions={
                    image.captionUrl && !previewContent && !previewLoading && (
                      <Button onClick={loadPreview} loading={previewLoading}>
                        Load Full Caption
                      </Button>
                    )
                  }
                >
                  Extracted Text
                </Header>
              }
            >
              {image.extractedText && (
                <Box>
                  <pre style={{
                    fontSize: '12px',
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordWrap: 'break-word',
                    maxHeight: '300px',
                    backgroundColor: '#f8f9fa',
                    padding: '12px',
                    borderRadius: '4px',
                    border: '1px solid #e9ecef'
                  }}>
                    {image.extractedText}
                  </pre>
                </Box>
              )}
              {previewLoading && (
                <Box textAlign="center" padding="l">
                  <Spinner /> Loading full caption...
                </Box>
              )}
              {previewError && (
                <Alert type="error">{previewError}</Alert>
              )}
              {previewContent && (
                <Box padding={{ top: 'm' }}>
                  <Box variant="awsui-key-label">Full Caption</Box>
                  <pre style={{
                    fontSize: '12px',
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordWrap: 'break-word',
                    maxHeight: '300px',
                    backgroundColor: '#f8f9fa',
                    padding: '12px',
                    borderRadius: '4px',
                    border: '1px solid #e9ecef'
                  }}>
                    {previewContent}
                  </pre>
                </Box>
              )}
            </Container>
          )}

          {/* Extracted Metadata */}
          {image.extractedMetadata && (() => {
            const formatLabel = (key: string) =>
              key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

            const formatValue = (value: unknown): string => {
              if (typeof value === 'string') return value;
              if (Array.isArray(value)) return value.join(', ');
              return String(value);
            };

            try {
              const parsed = typeof image.extractedMetadata === 'string'
                ? JSON.parse(image.extractedMetadata)
                : image.extractedMetadata;

              if (!parsed || typeof parsed !== 'object') return null;

              const fields = Object.entries(parsed).sort(([a], [b]) => a.localeCompare(b));
              if (fields.length === 0) return null;

              return (
                <Container header={<Header variant="h2">Extracted Metadata</Header>}>
                  <ColumnLayout columns={2} variant="text-grid">
                    {fields.map(([key, value]) => (
                      <div key={key}>
                        <Box variant="awsui-key-label">{formatLabel(key)}</Box>
                        <div>{formatValue(value)}</div>
                      </div>
                    ))}
                  </ColumnLayout>
                </Container>
              );
            } catch {
              return null;
            }
          })()}

          {/* Error Message */}
          {image.errorMessage && (
            <Alert type="error" header="Processing Error">
              {image.errorMessage}
            </Alert>
          )}
        </SpaceBetween>
      )}
    </Modal>
  );
};
