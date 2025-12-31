import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Checkbox,
  Container,
  Header,
  SpaceBetween,
  Alert,
  ProgressBar,
  StatusIndicator,
  ExpandableSection
} from '@cloudscape-design/components';
import { useImage } from '../../hooks/useImage';

export const ZipUpload = () => {
  const { uploading, error, clearError, uploadZip } = useImage();

  const [selectedFile, setSelectedFile] = useState(null);
  const [generateCaptions, setGenerateCaptions] = useState(true);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, complete, error
  const [localError, setLocalError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const validateFile = useCallback((file) => {
    const ext = file.name.toLowerCase().split('.').pop();
    if (ext !== 'zip') {
      return 'Only ZIP files are accepted. Please select a .zip archive.';
    }
    // Max 100MB for ZIP
    if (file.size > 100 * 1024 * 1024) {
      return 'File is too large. Maximum size is 100 MB.';
    }
    return null;
  }, []);

  const handleFileSelect = useCallback((file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setLocalError(validationError);
      return;
    }

    setLocalError(null);
    clearError();
    setSelectedFile(file);
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadResult(null);
  }, [validateFile, clearError]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  const handleFileInput = useCallback((e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  }, [handleFileSelect]);

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    setUploadStatus('uploading');
    setUploadProgress(0);
    setLocalError(null);

    try {
      const result = await uploadZip(selectedFile, generateCaptions, (progress) => {
        setUploadProgress(progress);
      });

      setUploadResult(result);
      setUploadStatus('complete');

      // Reset form after delay
      setTimeout(() => {
        setSelectedFile(null);
        setUploadStatus('idle');
        setUploadProgress(0);
      }, 5000);
    } catch (err) {
      setUploadStatus('error');
      setLocalError(err.message || 'Failed to upload ZIP archive');
    }
  }, [selectedFile, generateCaptions, uploadZip]);

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
    setUploadStatus('idle');
    setUploadProgress(0);
    setLocalError(null);
    setUploadResult(null);
    clearError();
  }, [clearError]);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  const displayError = localError || error;
  const canUpload = selectedFile && uploadStatus === 'idle' && !uploading;

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">Upload Image Archive</Header>

        <Alert type="info">
          Upload a ZIP file containing images. Optionally include a <code>captions.json</code> file
          to provide captions for your images.
        </Alert>

        {displayError && (
          <Alert type="error" dismissible onDismiss={() => { setLocalError(null); clearError(); }}>
            {displayError}
          </Alert>
        )}

        {uploadStatus === 'complete' && (
          <Alert type="success">
            ZIP archive uploaded successfully! Images are being processed and will appear in the Dashboard shortly.
            {uploadResult?.uploadId && (
              <Box variant="small" padding={{ top: 'xs' }}>
                Upload ID: {uploadResult.uploadId}
              </Box>
            )}
          </Alert>
        )}

        {!selectedFile ? (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            style={{
              border: dragActive ? '2px dashed #0073bb' : '2px dashed #aaa',
              borderRadius: '8px',
              backgroundColor: dragActive ? '#f0f8ff' : '#fafafa',
              cursor: 'pointer',
              minHeight: '200px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '32px',
              textAlign: 'center'
            }}
          >
            <input
              type="file"
              onChange={handleFileInput}
              style={{ display: 'none' }}
              id="zip-upload-input"
              accept=".zip"
            />
            <label htmlFor="zip-upload-input" style={{ cursor: 'pointer', width: '100%' }}>
              <SpaceBetween size="s">
                <Box fontSize="display-l">📦</Box>
                <Box fontSize="heading-m">
                  {dragActive ? 'Drop ZIP file here' : 'Drag and drop a ZIP file here'}
                </Box>
                <Box fontSize="body-m" color="text-body-secondary">
                  or click to browse
                </Box>
              </SpaceBetween>
            </label>
          </div>
        ) : (
          <SpaceBetween size="l">
            {/* File preview */}
            <div
              style={{
                backgroundColor: '#f5f5f5',
                borderRadius: '8px',
                border: '1px solid #d1d5db',
                padding: '16px'
              }}
            >
              <SpaceBetween direction="horizontal" size="m">
                <Box fontSize="heading-l">📦</Box>
                <Box>
                  <Box variant="strong">{selectedFile.name}</Box>
                  <Box variant="small" color="text-body-secondary">
                    {formatFileSize(selectedFile.size)}
                  </Box>
                </Box>
                {uploadStatus === 'idle' && (
                  <Box>
                    <Button onClick={handleRemoveFile} variant="link">
                      Remove
                    </Button>
                  </Box>
                )}
              </SpaceBetween>
            </div>

            {/* Generate captions checkbox */}
            {uploadStatus === 'idle' && (
              <Checkbox
                checked={generateCaptions}
                onChange={({ detail }) => setGenerateCaptions(detail.checked)}
              >
                Generate AI captions for images without captions in manifest
              </Checkbox>
            )}

            {/* Upload progress */}
            {uploadStatus === 'uploading' && (
              <Box>
                <ProgressBar
                  value={uploadProgress}
                  label="Uploading..."
                  description={`${uploadProgress}% complete`}
                />
              </Box>
            )}

            {/* Status indicators */}
            {uploadStatus === 'uploading' && (
              <StatusIndicator type="in-progress">Uploading archive...</StatusIndicator>
            )}

            {uploadStatus === 'complete' && (
              <StatusIndicator type="success">Upload complete - processing images</StatusIndicator>
            )}

            {uploadStatus === 'error' && (
              <StatusIndicator type="error">Upload failed</StatusIndicator>
            )}

            {/* Upload button */}
            {uploadStatus === 'idle' && (
              <Box>
                <Button
                  variant="primary"
                  onClick={handleUpload}
                  disabled={!canUpload}
                  loading={uploading}
                >
                  Upload Archive
                </Button>
              </Box>
            )}

            {uploadStatus === 'error' && (
              <Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Button onClick={handleRemoveFile}>Try Again</Button>
                </SpaceBetween>
              </Box>
            )}
          </SpaceBetween>
        )}

        {/* Help section */}
        <ExpandableSection headerText="How to use captions.json">
          <SpaceBetween size="s">
            <Box variant="p">
              Include a <code>captions.json</code> file in your ZIP archive to provide custom captions
              for your images. The file should be a JSON object mapping filenames to caption strings.
            </Box>

            <div style={{ backgroundColor: '#f5f5f5', borderRadius: '4px', padding: '8px' }}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
{`{
  "sunset.jpg": "A beautiful sunset over the mountains",
  "beach.png": "Sandy beach with crystal blue water",
  "city.jpeg": "Downtown skyline at night"
}`}
              </pre>
            </div>

            <Box variant="p">
              Images not listed in the manifest will either have no caption, or will have an
              AI-generated caption if you enable the "Generate AI captions" option.
            </Box>
          </SpaceBetween>
        </ExpandableSection>
      </SpaceBetween>
    </Container>
  );
};
