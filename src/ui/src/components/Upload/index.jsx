import React, { useState, useCallback } from 'react';
import {
  SpaceBetween,
  Tabs,
  ContentLayout,
  Header,
  Container,
  Box,
  CopyToClipboard,
  ExpandableSection,
} from '@cloudscape-design/components';
import { UploadZone } from './UploadZone';
import { UploadQueue } from './UploadQueue';
import { ImageUpload } from '../ImageUpload';
import { ZipUpload } from '../ImageUpload/ZipUpload';
import { useUpload } from '../../hooks/useUpload';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';
const s3Bucket = import.meta.env.VITE_DATA_BUCKET || '';

const documentUploadMutation = `mutation CreateUploadUrl($filename: String!) {
  createUploadUrl(filename: $filename) {
    uploadUrl
    documentId
    fields
  }
}`;

const imageUploadMutation = `mutation CreateImageUploadUrl($filename: String!) {
  createImageUploadUrl(filename: $filename) {
    uploadUrl
    imageId
    s3Uri
    fields
  }
}`;

const submitImageMutation = `mutation SubmitImage($input: SubmitImageInput!) {
  submitImage(input: $input) {
    imageId
    filename
    status
  }
}`;

const jsDocumentExample = graphqlEndpoint && s3Bucket
  ? `// Step 1: Get presigned upload URL
const response = await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'  // or 'Authorization': 'Bearer COGNITO_TOKEN'
  },
  body: JSON.stringify({
    query: \`${documentUploadMutation}\`,
    variables: { filename: 'document.pdf' }
  })
});
const { data } = await response.json();
const { documentId, fields } = data.createUploadUrl;

// Step 2: Upload file to S3 using presigned POST
const formData = new FormData();
Object.entries(JSON.parse(fields)).forEach(([key, value]) => {
  formData.append(key, value);
});
formData.append('file', file);

await fetch('https://${s3Bucket}.s3.amazonaws.com', {
  method: 'POST',
  body: formData
});

// Document will be automatically processed by the pipeline`
  : '';

const jsImageExample = graphqlEndpoint
  ? `// Step 1: Get presigned upload URL for image
const response = await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'  // or 'Authorization': 'Bearer COGNITO_TOKEN'
  },
  body: JSON.stringify({
    query: \`${imageUploadMutation}\`,
    variables: { filename: 'photo.jpg' }
  })
});
const { data } = await response.json();
const { imageId, uploadUrl, fields } = data.createImageUploadUrl;

// Step 2: Upload image to S3
const formData = new FormData();
Object.entries(JSON.parse(fields)).forEach(([key, value]) => {
  formData.append(key, value);
});
formData.append('file', imageFile);
await fetch(uploadUrl, { method: 'POST', body: formData });

// Step 3: Submit image with caption to trigger processing
await fetch('${graphqlEndpoint}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'YOUR_API_KEY'  // or 'Authorization': 'Bearer COGNITO_TOKEN'
  },
  body: JSON.stringify({
    query: \`${submitImageMutation}\`,
    variables: {
      input: {
        imageId,
        caption: 'Description of the image',
        userCaption: 'User-provided caption',
        aiCaption: 'AI-generated caption'
      }
    }
  })
});`
  : '';

const DocumentUploadContent = () => {
  const {
    uploads,
    uploading,
    addUpload,
    uploadFile,
    removeUpload,
    clearCompleted
  } = useUpload();

  const handleFilesSelected = useCallback((files) => {
    files.forEach(file => {
      const uploadId = addUpload(file);
      // Auto-start upload
      setTimeout(() => {
        uploadFile(uploadId);
      }, 100);
    });
  }, [addUpload, uploadFile]);

  const handleRetry = useCallback((uploadId) => {
    uploadFile(uploadId);
  }, [uploadFile]);

  return (
    <SpaceBetween size="l">
      <UploadZone
        onFilesSelected={handleFilesSelected}
        disabled={uploading}
      />
      {uploads.length > 0 && (
        <UploadQueue
          uploads={uploads}
          onRetry={handleRetry}
          onRemove={removeUpload}
          onClearCompleted={clearCompleted}
        />
      )}
    </SpaceBetween>
  );
};

export const Upload = () => {
  const [activeTabId, setActiveTabId] = useState('documents');

  const tabs = [
    {
      id: 'documents',
      label: 'Documents',
      content: <DocumentUploadContent />
    },
    {
      id: 'images',
      label: 'Images',
      content: <ImageUpload />
    },
    {
      id: 'archive',
      label: 'Image Archive',
      content: <ZipUpload />
    }
  ];

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Upload documents and images to your knowledge base"
        >
          Upload
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Tabs
          tabs={tabs}
          activeTabId={activeTabId}
          onChange={({ detail }) => setActiveTabId(detail.activeTabId)}
        />

        {graphqlEndpoint && (
          <Container>
            <ExpandableSection
              headerText="Use Upload API in Your Application"
              variant="footer"
            >
              <SpaceBetween size="m">
                <Box variant="p">
                  Programmatically upload documents and images using the GraphQL API.
                  Authentication uses API key or Cognito tokens (same as chat and search).
                </Box>

                <Box variant="h4">GraphQL Endpoint</Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      padding: '8px 12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      wordBreak: 'break-all',
                    }}
                  >
                    {graphqlEndpoint}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={graphqlEndpoint}
                  copyButtonText="Copy Endpoint"
                  copySuccessText="Copied!"
                />

                <Box variant="h4">Document Upload (2 steps)</Box>
                <Box variant="small" color="text-body-secondary">
                  1. Get presigned URL via GraphQL → 2. Upload file to S3. Processing starts automatically.
                </Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                    }}
                  >
                    {documentUploadMutation}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={documentUploadMutation}
                  copyButtonText="Copy Mutation"
                  copySuccessText="Copied!"
                />

                {jsDocumentExample && (
                  <>
                    <Box variant="h4">Document Upload Example (JavaScript)</Box>
                    <Box>
                      <code
                        style={{
                          display: 'block',
                          whiteSpace: 'pre-wrap',
                          padding: '12px',
                          background: 'var(--color-background-container-content)',
                          border: '1px solid var(--color-border-divider-default)',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '13px',
                        }}
                      >
                        {jsDocumentExample}
                      </code>
                    </Box>
                    <CopyToClipboard
                      copyText={jsDocumentExample}
                      copyButtonText="Copy JavaScript"
                      copySuccessText="Copied!"
                    />
                  </>
                )}

                <Box variant="h4">Image Upload (3 steps)</Box>
                <Box variant="small" color="text-body-secondary">
                  1. Get presigned URL → 2. Upload to S3 → 3. Submit with caption to trigger processing.
                </Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                      fontSize: '13px',
                    }}
                  >
                    {imageUploadMutation}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={imageUploadMutation}
                  copyButtonText="Copy Image Mutation"
                  copySuccessText="Copied!"
                />

                {jsImageExample && (
                  <>
                    <Box variant="h4">Image Upload Example (JavaScript)</Box>
                    <Box>
                      <code
                        style={{
                          display: 'block',
                          whiteSpace: 'pre-wrap',
                          padding: '12px',
                          background: 'var(--color-background-container-content)',
                          border: '1px solid var(--color-border-divider-default)',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '13px',
                        }}
                      >
                        {jsImageExample}
                      </code>
                    </Box>
                    <CopyToClipboard
                      copyText={jsImageExample}
                      copyButtonText="Copy JavaScript"
                      copySuccessText="Copied!"
                    />
                  </>
                )}

                <Box variant="small" color="text-body-secondary">
                  Replace YOUR_API_KEY with your AppSync API key, or use Cognito tokens.
                  Supported document formats: PDF, DOCX, TXT, HTML, MD.
                  Supported image formats: JPG, PNG, GIF, WEBP.
                </Box>
              </SpaceBetween>
            </ExpandableSection>
          </Container>
        )}
      </SpaceBetween>
    </ContentLayout>
  );
};
