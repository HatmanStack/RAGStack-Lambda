import React, { useState } from 'react';
import { Box, Link, SpaceBetween, Modal, Button } from '@cloudscape-design/components';

export const ImageSource = ({ source }) => {
  const [showFullImage, setShowFullImage] = useState(false);

  return (
    <>
      <Box padding={{ bottom: 's' }}>
        <SpaceBetween size="xs">
          {/* Thumbnail and caption */}
          <SpaceBetween direction="horizontal" size="s">
            {source.thumbnailUrl ? (
              <Box>
                <img
                  src={source.thumbnailUrl}
                  alt={source.caption || 'Image source'}
                  style={{
                    width: '80px',
                    height: '80px',
                    objectFit: 'cover',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: '1px solid #d1d5db'
                  }}
                  onClick={() => setShowFullImage(true)}
                />
              </Box>
            ) : (
              <div
                style={{
                  width: '80px',
                  height: '80px',
                  backgroundColor: '#f3f4f6',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #d1d5db'
                }}
              >
                <Box fontSize="heading-l">🖼️</Box>
              </div>
            )}

            <Box>
              {source.caption && (
                <Box variant="small" color="text-body-secondary">
                  {source.caption.length > 100
                    ? `${source.caption.slice(0, 100)}...`
                    : source.caption}
                </Box>
              )}
              {source.thumbnailUrl && (
                <Box padding={{ top: 'xs' }}>
                  <Link onFollow={() => setShowFullImage(true)}>
                    View full image
                  </Link>
                </Box>
              )}
            </Box>
          </SpaceBetween>
        </SpaceBetween>
      </Box>

      {/* Full image modal */}
      <Modal
        visible={showFullImage}
        onDismiss={() => setShowFullImage(false)}
        header="Image Source"
        size="large"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              {source.documentUrl && (
                <Button href={source.documentUrl} target="_blank" iconAlign="right" iconName="external">
                  Open in new tab
                </Button>
              )}
              <Button variant="primary" onClick={() => setShowFullImage(false)}>
                Close
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box textAlign="center">
            {source.thumbnailUrl ? (
              <img
                src={source.thumbnailUrl}
                alt={source.caption || 'Image source'}
                style={{
                  maxWidth: '100%',
                  maxHeight: '500px',
                  borderRadius: '8px',
                  objectFit: 'contain'
                }}
              />
            ) : (
              <div
                style={{
                  backgroundColor: '#f3f4f6',
                  borderRadius: '8px',
                  padding: '40px'
                }}
              >
                <Box fontSize="display-l">🖼️</Box>
                <Box color="text-body-secondary">No image preview available</Box>
              </div>
            )}
          </Box>

          {source.caption && (
            <Box>
              <Box variant="awsui-key-label">Caption</Box>
              <Box>{source.caption}</Box>
            </Box>
          )}
        </SpaceBetween>
      </Modal>
    </>
  );
};
