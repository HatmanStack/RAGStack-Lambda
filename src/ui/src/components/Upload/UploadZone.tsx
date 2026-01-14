import React, { useCallback, DragEvent, ChangeEvent } from 'react';
import { Box, Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export const UploadZone = ({ onFilesSelected, disabled }: UploadZoneProps) => {
  const [dragActive, setDragActive] = React.useState(false);

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

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    // Don't process files when disabled
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesSelected(Array.from(e.dataTransfer.files));
    }
  }, [onFilesSelected, disabled]);

  const handleFileInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(Array.from(e.target.files));
    }
  }, [onFilesSelected]);

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">Upload Documents</Header>

        <Alert type="info">
          Supported formats: PDF, JPG, PNG, TIFF, DOCX, XLSX, TXT, CSV, MD, EPUB, MP4, WebM, MP3, WAV
        </Alert>

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
            accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.docx,.xlsx,.txt,.csv,.md,.epub,.mp4,.webm,.mp3,.wav,.m4a,.ogg"
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
