import React, { useState, useCallback, DragEvent, ChangeEvent } from 'react';
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
  Popover,
} from '@cloudscape-design/components';
import { useImage } from '../../hooks/useImage';

type UploadStatus = 'idle' | 'uploading' | 'complete' | 'error';

interface UploadResult {
  uploadId: string;
}

export const ZipUpload = () => {
  const { uploading, error, clearError, uploadZip } = useImage();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [generateCaptions, setGenerateCaptions] = useState(true);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);

  const validateFile = useCallback((file: File): string | null => {
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

  const handleFileSelect = useCallback((file: File) => {
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

  const handleDrag = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  const handleFileInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
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
      const result = await uploadZip(selectedFile, generateCaptions, (progress: number) => {
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
      setLocalError(err instanceof Error ? err.message : 'Failed to upload ZIP archive');
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

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  const displayError = localError || error;
  const canUpload = selectedFile && uploadStatus === 'idle' && !uploading;

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">
          Upload Image Archive{' '}
          <Popover
            header="How to use"
            content={
              <Box variant="small">
                Upload a ZIP file containing images (max 100 MB).
                <br /><br />
                <strong>Optional captions.json:</strong>
                <pre style={{ margin: '4px 0', fontSize: '11px', background: '#f5f5f5', padding: '4px', borderRadius: '2px' }}>
{`{
  "photo.jpg": "Description here"
}`}
                </pre>
                Images without captions use AI-generated captions if enabled.
              </Box>
            }
            triggerType="custom"
            size="large"
          >
            <Button variant="inline-icon" iconName="status-info" ariaLabel="How to use" />
          </Popover>
        </Header>

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

      </SpaceBetween>
    </Container>
  );
};
