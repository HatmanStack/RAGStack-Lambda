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
import { useImage } from '../../hooks/useImage';

export const ImageDetail = ({ imageId, visible, onDismiss, onDelete }) => {
  const { getImage, deleteImage } = useImage();
  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadImage = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const img = await getImage(imageId);
      setImage(img);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [getImage, imageId]);

  const handleDelete = useCallback(async () => {
    if (!window.confirm('Are you sure you want to delete this image? This cannot be undone.')) {
      return;
    }

    setDeleting(true);
    try {
      await deleteImage(imageId);
      if (onDelete) {
        onDelete(imageId);
      }
      onDismiss();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  }, [deleteImage, imageId, onDelete, onDismiss]);

  useEffect(() => {
    if (visible && imageId) {
      loadImage();
    }
  }, [visible, imageId, loadImage]);

  if (!visible) return null;

  const getStatusConfig = (status) => {
    const statusMap = {
      'PENDING': { type: 'pending', label: 'Pending' },
      'PROCESSING': { type: 'in-progress', label: 'Processing' },
      'INDEXED': { type: 'success', label: 'Indexed' },
      'FAILED': { type: 'error', label: 'Failed' }
    };
    return statusMap[status] || { type: 'info', label: status };
  };

  const formatFileSize = (bytes) => {
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
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onDismiss}>
              Close
            </Button>
            <Button
              variant="primary"
              onClick={handleDelete}
              loading={deleting}
              disabled={deleting}
            >
              Delete Image
            </Button>
          </SpaceBetween>
        </Box>
      }
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
                <Box
                  padding="xxl"
                  style={{
                    backgroundColor: '#f3f4f6',
                    borderRadius: '8px',
                    display: 'inline-block'
                  }}
                >
                  <Box fontSize="display-l">🖼️</Box>
                  <Box color="text-body-secondary">No preview available</Box>
                </Box>
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
                  <StatusIndicator type={getStatusConfig(image.status).type}>
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
                <div>{new Date(image.createdAt).toLocaleString()}</div>
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
