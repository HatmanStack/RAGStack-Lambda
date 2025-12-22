import React, { useCallback } from 'react';
import { Box, Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';

export const UploadZone = ({ onFilesSelected, disabled }) => {
  const [dragActive, setDragActive] = React.useState(false);

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
      onFilesSelected(Array.from(e.dataTransfer.files));
    }
  }, [onFilesSelected]);

  const handleFileInput = useCallback((e) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(Array.from(e.target.files));
    }
  }, [onFilesSelected]);

  return (
    <Container>
      <SpaceBetween size="l">
        <Header variant="h2">Upload Documents</Header>

        <Alert type="info">
          Supported formats: PDF, JPG, PNG, TIFF, DOCX, XLSX, TXT, CSV, MD, EPUB
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
            accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.docx,.xlsx,.txt,.csv,.md,.epub"
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
