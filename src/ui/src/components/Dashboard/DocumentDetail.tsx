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
import { useDocuments } from '../../hooks/useDocuments';
import type { DocumentDetailProps, DocumentDetailData, StatusConfig } from './types';

const STATUS_MAP: Record<string, StatusConfig> = {
  'UPLOADED': { type: 'pending', label: 'Uploaded' },
  'PROCESSING': { type: 'in-progress', label: 'Processing' },
  'OCR_COMPLETE': { type: 'in-progress', label: 'OCR Complete' },
  'EMBEDDING_COMPLETE': { type: 'in-progress', label: 'Embedding Complete' },
  'INDEXED': { type: 'success', label: 'Indexed' },
  'FAILED': { type: 'error', label: 'Failed' }
};

export const DocumentDetail = ({ documentId, visible, onDismiss }: DocumentDetailProps) => {
  const { fetchDocument } = useDocuments();
  const [document, setDocument] = useState<DocumentDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const loadDocument = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPreviewContent(null);
    setPreviewError(null);

    try {
      const doc = await fetchDocument(documentId) as DocumentDetailData;
      setDocument(doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document');
    } finally {
      setLoading(false);
    }
  }, [fetchDocument, documentId]);

  const loadPreview = useCallback(async () => {
    if (!document?.previewUrl) return;

    setPreviewLoading(true);
    setPreviewError(null);

    try {
      const response = await fetch(document.previewUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch preview: ${response.status}`);
      }
      const text = await response.text();
      // Limit preview to first 50KB to avoid UI slowdown
      setPreviewContent(text.length > 50000 ? text.slice(0, 50000) + '\n\n... (truncated)' : text);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Failed to load preview');
    } finally {
      setPreviewLoading(false);
    }
  }, [document?.previewUrl]);

  useEffect(() => {
    if (visible && documentId) {
      loadDocument();
    }
  }, [visible, documentId, loadDocument]);

  if (!visible) return null;

  const getStatusConfig = (status: string): StatusConfig => {
    return STATUS_MAP[status] || { type: 'info', label: status };
  };

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header="Document Details"
      size="large"
    >
      {loading && (
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
        </Box>
      )}

      {error && (
        <Alert type="error" header="Failed to load document">
          {error}
        </Alert>
      )}

      {document && (
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">General Information</Header>}>
            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="awsui-key-label">Document ID</Box>
                <div>{document.documentId}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Filename</Box>
                <div>{document.filename}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Status</Box>
                <div>
                  <StatusIndicator type={getStatusConfig(document.status).type as 'pending' | 'in-progress' | 'success' | 'error' | 'info'}>
                    {getStatusConfig(document.status).label}
                  </StatusIndicator>
                </div>
              </div>
              <div>
                <Box variant="awsui-key-label">File Type</Box>
                <div>{document.fileType?.toUpperCase() || 'N/A'}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Total Pages</Box>
                <div>{document.totalPages || '-'}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Text Native PDF</Box>
                <div>{document.isTextNative ? 'Yes' : 'No'}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Created</Box>
                <div>{document.createdAt ? new Date(document.createdAt).toLocaleString() : '-'}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Updated</Box>
                <div>{document.updatedAt ? new Date(document.updatedAt).toLocaleString() : '-'}</div>
              </div>
            </ColumnLayout>
          </Container>

          {document.errorMessage && (
            <Alert type="error" header="Processing Error">
              {document.errorMessage}
            </Alert>
          )}

          <Container header={<Header variant="h2">S3 Locations</Header>}>
            <ColumnLayout columns={1} variant="text-grid">
              <div>
                <Box variant="awsui-key-label">Input</Box>
                <div style={{ fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all' }}>
                  {document.inputS3Uri}
                </div>
              </div>
              {document.outputS3Uri && (
                <div>
                  <Box variant="awsui-key-label">Output</Box>
                  <div style={{ fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all' }}>
                    {document.outputS3Uri}
                  </div>
                </div>
              )}
            </ColumnLayout>
          </Container>

          {document.previewUrl && (
            <Container
              header={
                <Header
                  variant="h2"
                  actions={
                    !previewContent && !previewLoading && (
                      <Button onClick={loadPreview} loading={previewLoading}>
                        Load Preview
                      </Button>
                    )
                  }
                >
                  Extracted Text
                </Header>
              }
            >
              {previewLoading && (
                <Box textAlign="center" padding="l">
                  <Spinner /> Loading preview...
                </Box>
              )}
              {previewError && (
                <Alert type="error">{previewError}</Alert>
              )}
              {previewContent && (
                <Box>
                  <pre style={{
                    fontSize: '12px',
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordWrap: 'break-word',
                    maxHeight: '400px',
                    backgroundColor: '#f8f9fa',
                    padding: '12px',
                    borderRadius: '4px',
                    border: '1px solid #e9ecef'
                  }}>
                    {previewContent}
                  </pre>
                </Box>
              )}
              {!previewContent && !previewLoading && !previewError && (
                <Box color="text-body-secondary">
                  Click "Load Preview" to view extracted text content.
                </Box>
              )}
            </Container>
          )}

          {document.metadata && (() => {
            const formatLabel = (key: string) =>
              key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

            const formatValue = (value: unknown): string => {
              if (typeof value === 'string') return value;
              if (Array.isArray(value)) return value.join(', ');
              return String(value);
            };

            try {
              // Handle both object (from AWSJSON) and string (legacy) formats
              const parsed = typeof document.metadata === 'string'
                ? JSON.parse(document.metadata)
                : document.metadata;

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
        </SpaceBetween>
      )}
    </Modal>
  );
};
