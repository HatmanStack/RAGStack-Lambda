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
  Spinner
} from '@cloudscape-design/components';
import { useDocuments } from '../../hooks/useDocuments';

export const DocumentDetail = ({ documentId, visible, onDismiss }) => {
  const { fetchDocument } = useDocuments();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadDocument = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const doc = await fetchDocument(documentId);
      setDocument(doc);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchDocument, documentId]);

  useEffect(() => {
    if (visible && documentId) {
      loadDocument();
    }
  }, [visible, documentId, loadDocument]);

  if (!visible) return null;

  const getStatusType = (status) => {
    if (status === 'INDEXED') return 'success';
    if (status === 'FAILED') return 'error';
    return 'in-progress';
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
                  <StatusIndicator type={getStatusType(document.status)}>
                    {document.status}
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
                <div>{new Date(document.createdAt).toLocaleString()}</div>
              </div>
              <div>
                <Box variant="awsui-key-label">Updated</Box>
                <div>{new Date(document.updatedAt).toLocaleString()}</div>
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

          {document.metadata && (
            <Container header={<Header variant="h2">Metadata</Header>}>
              <Box>
                <pre style={{ fontSize: '12px', overflow: 'auto', whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                  {(() => {
                    try {
                      return JSON.stringify(JSON.parse(document.metadata), null, 2);
                    } catch (err) {
                      return `Invalid JSON: ${document.metadata}`;
                    }
                  })()}
                </pre>
              </Box>
            </Container>
          )}
        </SpaceBetween>
      )}
    </Modal>
  );
};
