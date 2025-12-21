import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Button,
  Container,
  Header,
  SpaceBetween,
  Alert,
  ProgressBar,
  StatusIndicator
} from '@cloudscape-design/components';
import { ImagePreview } from './ImagePreview';
import { CaptionInput } from './CaptionInput';
import { useImage } from '../../hooks/useImage';

const SUPPORTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export const ImageUpload = () => {
  const {
    uploading,
    generating,
    error,
    clearError,
    uploadImage,
    generateCaption,
    submitImage
  } = useImage();

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [imageId, setImageId] = useState(null);
  const [imageS3Uri, setImageS3Uri] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, uploaded, submitting, complete, error
  const [userCaption, setUserCaption] = useState('');
  const [aiCaption, setAiCaption] = useState('');
  const [localError, setLocalError] = useState(null);
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

  const validateFile = useCallback((file) => {
    if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) {
      return 'Unsupported file type. Please select a PNG, JPG, GIF, or WebP image.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File is too large. Maximum size is 10 MB.';
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(async (file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setLocalError(validationError);
      return;
    }

    setLocalError(null);
    clearError();
    setSelectedFile(file);
    setUserCaption('');
    setAiCaption('');
    setUploadStatus('uploading');
    setUploadProgress(0);

    try {
      const result = await uploadImage(file, (progress) => {
        setUploadProgress(progress);
      });
      setImageId(result.imageId);
      setImageS3Uri(result.s3Uri);
      setUploadStatus('uploaded');
    } catch (err) {
      setUploadStatus('error');
      setLocalError(err.message || 'Failed to upload image');
    }
  }, [validateFile, clearError, uploadImage]);

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

  const handleGenerateCaption = useCallback(async () => {
    if (!imageS3Uri) return;

    try {
      setLocalError(null);
      const caption = await generateCaption(imageS3Uri);
      setAiCaption(caption);
    } catch (err) {
      setLocalError(err.message || 'Failed to generate caption');
    }
  }, [imageS3Uri, generateCaption]);

  const handleSubmit = useCallback(async () => {
    if (!imageId) return;

    setUploadStatus('submitting');
    const combinedCaption = [userCaption, aiCaption].filter(Boolean).join('. ');

    try {
      await submitImage(imageId, combinedCaption, userCaption, aiCaption);
      setUploadStatus('complete');

      // Reset form after short delay
      setTimeout(() => {
        setSelectedFile(null);
        setImageId(null);
        setImageS3Uri(null);
        setUserCaption('');
        setAiCaption('');
        setUploadStatus('idle');
        setUploadProgress(0);
      }, 2000);
    } catch (err) {
      setUploadStatus('error');
      setLocalError(err.message || 'Failed to submit image');
    }
  }, [imageId, userCaption, aiCaption, submitImage]);

  const handleRemoveImage = useCallback(() => {
    setSelectedFile(null);
    setImageId(null);
    setImageS3Uri(null);
    setUserCaption('');
    setAiCaption('');
    setUploadStatus('idle');
    setUploadProgress(0);
    setLocalError(null);
    clearError();
  }, [clearError]);

  const displayError = localError || error;
  const canSubmit = uploadStatus === 'uploaded' && (userCaption || aiCaption);
  const isDisabled = uploading || uploadStatus === 'submitting';

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">Upload Image</Header>

        <Alert type="info">
          <strong>How it works:</strong> Upload an image → Add a caption (type your own or generate with AI) → Submit to index in your knowledge base.
          Supported formats: PNG, JPG, GIF, WebP (max 10 MB).
        </Alert>

        {displayError && (
          <Alert type="error" dismissible onDismiss={() => { setLocalError(null); clearError(); }}>
            {displayError}
          </Alert>
        )}

        {uploadStatus === 'complete' && (
          <Alert type="success">
            Image uploaded and submitted successfully! It will be processed and indexed shortly.
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

            {uploadStatus === 'uploaded' && (
              <>
                <StatusIndicator type="success">Image uploaded</StatusIndicator>

                <CaptionInput
                  userCaption={userCaption}
                  aiCaption={aiCaption}
                  onUserCaptionChange={setUserCaption}
                  onGenerateCaption={handleGenerateCaption}
                  generating={generating}
                  error={null}
                />

                <Box>
                  <Button
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={!canSubmit || isDisabled}
                    loading={uploadStatus === 'submitting'}
                  >
                    {uploadStatus === 'submitting' ? 'Submitting...' : 'Submit Image'}
                  </Button>
                </Box>
              </>
            )}

            {uploadStatus === 'submitting' && (
              <StatusIndicator type="in-progress">Submitting image...</StatusIndicator>
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
