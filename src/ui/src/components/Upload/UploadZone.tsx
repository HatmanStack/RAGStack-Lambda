import React, { useCallback, useState, DragEvent, ChangeEvent } from 'react';
import { Box, Container, Header, SpaceBetween, Alert, Popover, Button } from '@cloudscape-design/components';

// Image extensions that should be uploaded via Image Archive instead
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'];

const isImageFile = (filename: string): boolean => {
  const lower = filename.toLowerCase();
  return IMAGE_EXTENSIONS.some(ext => lower.endsWith(ext));
};

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export const UploadZone = ({ onFilesSelected, disabled }: UploadZoneProps) => {
  const [dragActive, setDragActive] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);

  const handleDrag = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Don't update drag state when disabled
    if (disabled) return;
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, [disabled]);

  const filterAndValidateFiles = useCallback((files: File[]): File[] => {
    const imageFiles = files.filter(f => isImageFile(f.name));
    const validFiles = files.filter(f => !isImageFile(f.name));

    if (imageFiles.length > 0) {
      const names = imageFiles.map(f => f.name).join(', ');
      setImageError(
        `Image files should be uploaded via Image Archive for visual search: ${names}`
      );
      // Clear error after 8 seconds
      setTimeout(() => setImageError(null), 8000);
    }

    return validFiles;
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    // Don't process files when disabled
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const validFiles = filterAndValidateFiles(Array.from(e.dataTransfer.files));
      if (validFiles.length > 0) {
        onFilesSelected(validFiles);
      }
    }
  }, [onFilesSelected, disabled, filterAndValidateFiles]);

  const handleFileInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const validFiles = filterAndValidateFiles(Array.from(e.target.files));
      if (validFiles.length > 0) {
        onFilesSelected(validFiles);
      }
    }
  }, [onFilesSelected, filterAndValidateFiles]);

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">
          Upload Documents{' '}
          <Popover
            header="Supported formats"
            content={
              <Box variant="small">
                <strong>Documents:</strong> PDF, DOCX, XLSX, TXT, CSV, MD, EPUB
                <br />
                <strong>Media:</strong> MP4, WebM, MP3, WAV
                <br />
                <strong>Images:</strong> Use Image Archive
              </Box>
            }
            triggerType="custom"
            dismissButton={false}
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="Supported formats" />
            </span>
          </Popover>
        </Header>

        {imageError && (
          <Alert type="warning" dismissible onDismiss={() => setImageError(null)}>
            {imageError}
          </Alert>
        )}

        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          style={{
            border: dragActive ? '2px dashed #0073bb' : '2px dashed #aaa',
            borderRadius: '8px',
            backgroundColor: dragActive ? '#f0f8ff' : '#fafafa',
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.6 : 1,
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
            multiple
            onChange={handleFileInput}
            style={{ display: 'none' }}
            id="file-upload-input"
            disabled={disabled}
            accept=".pdf,.docx,.xlsx,.txt,.csv,.md,.epub,.mp4,.webm,.mp3,.wav,.m4a,.ogg"
          />
          <label
            htmlFor="file-upload-input"
            style={{ cursor: disabled ? 'not-allowed' : 'pointer', width: '100%' }}
          >
            <SpaceBetween size="s">
              <Box fontSize="display-l">📁</Box>
              <Box fontSize="heading-m">
                {dragActive ? 'Drop files here' : 'Drag and drop files here'}
              </Box>
              <Box fontSize="body-m" color="text-body-secondary">
                or click to browse
              </Box>
            </SpaceBetween>
          </label>
        </div>
      </SpaceBetween>
    </Container>
  );
};
