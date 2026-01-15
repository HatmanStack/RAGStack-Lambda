import React, { useState, useCallback, useEffect, DragEvent, ChangeEvent } from 'react';
import {
  Box,
  Button,
  Container,
  Header,
  SpaceBetween,
  Alert,
  ProgressBar,
  StatusIndicator,
  Popover,
} from '@cloudscape-design/components';
import { ImagePreview } from './ImagePreview';
import { CaptionInput } from './CaptionInput';
import { useImage } from '../../hooks/useImage';

type UploadStatus = 'idle' | 'uploading' | 'uploaded' | 'submitting' | 'complete' | 'error';

const SUPPORTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export const ImageUpload = () => {
  const {
    uploading,
    error,
    clearError,
    uploadImage,
    submitImage
  } = useImage();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageId, setImageId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [userCaption, setUserCaption] = useState('');
  const [extractText, setExtractText] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Create preview URL when file is selected
  useEffect(() => {
    if (selectedFile) {
      const url = URL.createObjectURL(selectedFile);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [selectedFile]);

  const validateFile = useCallback((file: File): string | null => {
    if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) {
      return 'Unsupported file type. Please select a PNG, JPG, GIF, or WebP image.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File is too large. Maximum size is 10 MB.';
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(async (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setLocalError(validationError);
      return;
    }

    setLocalError(null);
    clearError();
    setSelectedFile(file);
    setUserCaption('');
    setExtractText(false);
    setUploadStatus('uploading');
    setUploadProgress(0);

    try {
      const result = await uploadImage(file, (progress) => {
        setUploadProgress(progress);
      });
      setImageId(result.imageId);
      setUploadStatus('uploaded');
    } catch (err) {
      setUploadStatus('error');
      setLocalError(err instanceof Error ? err.message : 'Failed to upload image');
    }
  }, [validateFile, clearError, uploadImage]);

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

  const handleSubmit = useCallback(async () => {
    if (!imageId) return;

    setUploadStatus('submitting');

    try {
      await submitImage(imageId, userCaption, userCaption, '', extractText);
      setUploadStatus('complete');

      // Reset form after short delay
      setTimeout(() => {
        setSelectedFile(null);
        setImageId(null);
        setUserCaption('');
        setExtractText(false);
        setUploadStatus('idle');
        setUploadProgress(0);
      }, 2000);
    } catch (err) {
      setUploadStatus('error');
      setLocalError(err instanceof Error ? err.message : 'Failed to submit image');
    }
  }, [imageId, userCaption, extractText, submitImage]);

  const handleRemoveImage = useCallback(() => {
    setSelectedFile(null);
    setImageId(null);
    setUserCaption('');
    setExtractText(false);
    setUploadStatus('idle');
    setUploadProgress(0);
    setLocalError(null);
    clearError();
  }, [clearError]);

  const displayError = localError || error;
  const canSubmit = uploadStatus === 'uploaded';
  const isDisabled = uploading || uploadStatus === 'submitting';

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">
          Upload Image{' '}
          <Popover
            header="How it works"
            content={
              <Box variant="small">
                Upload an image, optionally add a caption for context (names, dates, events),
                and check &quot;Extract text&quot; if the image contains readable text.
                Visual search works automatically via AI embeddings.
                <br /><br />
                <strong>Supported formats:</strong> PNG, JPG, GIF, WebP (max 10 MB)
              </Box>
            }
            triggerType="custom"
            dismissButton={false}
            size="medium"
          >
            <Button variant="inline-icon" iconName="status-info" ariaLabel="How it works" />
          </Popover>
        </Header>

        {displayError && (
          <Alert type="error" dismissible onDismiss={() => { setLocalError(null); clearError(); }}>
            {displayError}
          </Alert>
        )}

        {uploadStatus === 'complete' && (
          <Alert type="success">
            Image uploaded successfully! It will be processed and indexed shortly.
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
              id="image-upload-input"
              accept="image/png,image/jpeg,image/gif,image/webp"
            />
            <label htmlFor="image-upload-input" style={{ cursor: 'pointer', width: '100%' }}>
              <SpaceBetween size="s">
                <Box fontSize="display-l">🖼️</Box>
                <Box fontSize="heading-m">
                  {dragActive ? 'Drop image here' : 'Drag and drop an image here'}
                </Box>
                <Box fontSize="body-m" color="text-body-secondary">
                  or click to browse
                </Box>
              </SpaceBetween>
            </label>
          </div>
        ) : (
          <SpaceBetween size="l">
            <ImagePreview
              file={selectedFile}
              previewUrl={previewUrl}
              onRemove={uploadStatus !== 'submitting' ? handleRemoveImage : undefined}
            />

            {(uploadStatus === 'uploading') && (
              <Box>
                <ProgressBar
                  value={uploadProgress}
                  label="Uploading..."
                  description={`${uploadProgress}% complete`}
                />
              </Box>
            )}

            {(uploadStatus === 'uploaded' || uploadStatus === 'submitting') && (
              <>
                <StatusIndicator type="success">Image uploaded</StatusIndicator>

                <CaptionInput
                  userCaption={userCaption}
                  extractText={extractText}
                  onUserCaptionChange={setUserCaption}
                  onExtractTextChange={setExtractText}
                  error={null}
                />

                <Box>
                  <Button
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={!canSubmit || isDisabled}
                    loading={uploadStatus === 'submitting'}
                  >
                    {uploadStatus === 'submitting' ? 'Processing...' : 'Submit Image'}
                  </Button>
                </Box>
              </>
            )}

            {uploadStatus === 'submitting' && (
              <StatusIndicator type="in-progress">
                {extractText ? 'Extracting text and processing...' : 'Processing image...'}
              </StatusIndicator>
            )}

            {uploadStatus === 'error' && (
              <Box>
                <SpaceBetween direction="horizontal" size="s">
                  <Button onClick={handleRemoveImage}>Try Again</Button>
                </SpaceBetween>
              </Box>
            )}
          </SpaceBetween>
        )}
      </SpaceBetween>
    </Container>
  );
};
