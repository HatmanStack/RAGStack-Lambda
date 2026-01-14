import React, { useState, useCallback } from 'react';
import {
  SpaceBetween,
  Tabs,
  ContentLayout,
  Header,
  Alert,
  ProgressBar,
  Box,
} from '@cloudscape-design/components';
import { UploadZone } from './UploadZone';
import { ImageUpload } from '../ImageUpload';
import { ZipUpload } from '../ImageUpload/ZipUpload';
import { useUpload } from '../../hooks/useUpload';
import { ApiDocs } from '../common/ApiDocs';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

// Document examples
const docGraphql = `mutation CreateUploadUrl($filename: String!) {
  createUploadUrl(filename: $filename) {
    uploadUrl, documentId, fields
  }
}`;

const docJsExample = `// 1. Get presigned URL
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({ query: CREATE_UPLOAD_URL, variables: { filename: 'doc.pdf' } })
});
const { uploadUrl, fields } = (await res.json()).data.createUploadUrl;

// 2. Upload to S3
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', file);
await fetch(uploadUrl, { method: 'POST', body: form });`;

const docCurlExample = `# Step 1: Get presigned URL
curl -X POST 'ENDPOINT' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: API_KEY' \\
  -d '{"query": "mutation { createUploadUrl(filename: \\"doc.pdf\\") { uploadUrl, documentId, fields } }"}'

# Step 2: Upload file using uploadUrl and fields from response`;

// Image examples (manual caption workflow)
const imgGraphql = `# Step 1: Get upload URL
mutation CreateImageUploadUrl($filename: String!) {
  createImageUploadUrl(filename: $filename) {
    uploadUrl, imageId, s3Uri, fields
  }
}

# Step 2: Generate AI caption (optional)
mutation GenerateCaption($imageS3Uri: String!) {
  generateCaption(imageS3Uri: $imageS3Uri) { caption }
}

# Step 3: Submit with caption
mutation SubmitImage($input: SubmitImageInput!) {
  submitImage(input: $input) { imageId, filename, status }
}`;

const imgJsExample = `// 1. Get presigned URL
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({ query: CREATE_IMAGE_UPLOAD_URL, variables: { filename: 'photo.jpg' } })
});
const { uploadUrl, imageId, s3Uri, fields } = (await res.json()).data.createImageUploadUrl;

// 2. Upload to S3
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', imageFile);
await fetch(uploadUrl, { method: 'POST', body: form });

// 3. Generate AI caption (optional - or provide your own)
const captionRes = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({ query: GENERATE_CAPTION, variables: { imageS3Uri: s3Uri } })
});
const aiCaption = (await captionRes.json()).data.generateCaption.caption;

// 4. Submit with caption (triggers processing)
await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: SUBMIT_IMAGE,
    variables: { input: { imageId, userCaption: 'My description', aiCaption } }
  })
});`;

const imgCurlExample = `# Step 1: Get upload URL
curl -X POST 'ENDPOINT' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: API_KEY' \\
  -d '{"query": "mutation { createImageUploadUrl(filename: \\"photo.jpg\\") { uploadUrl, imageId, s3Uri, fields } }"}'

# Step 2: Upload file, then call generateCaption and submitImage`;

// ZIP archive examples
const zipGraphql = `mutation CreateZipUploadUrl($generateCaptions: Boolean) {
  createZipUploadUrl(generateCaptions: $generateCaptions) {
    uploadUrl, uploadId, fields
  }
}`;

const zipJsExample = `// 1. Get presigned URL (with optional AI caption generation)
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: CREATE_ZIP_UPLOAD_URL,
    variables: { generateCaptions: true }  // Set to true for AI-generated captions
  })
});
const { uploadUrl, uploadId, fields } = (await res.json()).data.createZipUploadUrl;

// 2. Upload ZIP to S3
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', zipFile);
await fetch(uploadUrl, { method: 'POST', body: form });

// Images are extracted and processed automatically`;

const zipCurlExample = `curl -X POST 'ENDPOINT' \\
  -H 'Content-Type: application/json' \\
  -H 'x-api-key: API_KEY' \\
  -d '{"query": "mutation { createZipUploadUrl(generateCaptions: true) { uploadUrl, uploadId, fields } }"}'

# Then upload ZIP file using uploadUrl and fields from response`;

interface ApiExampleSet {
  title: string;
  description: string;
  examples: { id: string; label: string; code: string }[];
}

// Examples config per tab (consistent: GraphQL → JavaScript → cURL)
const apiExamples: Record<string, ApiExampleSet> = {
  documents: {
    title: 'Document Upload API',
    description: 'Get presigned URL, upload to S3. Supports PDF, DOCX, TXT, HTML, MD.',
    examples: [
      { id: 'graphql', label: 'GraphQL', code: docGraphql },
      { id: 'js', label: 'JavaScript', code: docJsExample },
      { id: 'curl', label: 'cURL', code: docCurlExample },
    ],
  },
  images: {
    title: 'Image Upload API',
    description: 'Upload image, generate AI caption, then submit. Supports JPG, PNG, GIF, WEBP.',
    examples: [
      { id: 'graphql', label: 'GraphQL', code: imgGraphql },
      { id: 'js', label: 'JavaScript', code: imgJsExample },
      { id: 'curl', label: 'cURL', code: imgCurlExample },
    ],
  },
  archive: {
    title: 'Image Archive Upload API',
    description: 'Upload ZIP of images for batch processing. Optional AI caption generation.',
    examples: [
      { id: 'graphql', label: 'GraphQL', code: zipGraphql },
      { id: 'js', label: 'JavaScript', code: zipJsExample },
      { id: 'curl', label: 'cURL', code: zipCurlExample },
    ],
  },
};

const DocumentUploadContent = () => {
  const { addUpload, uploadFile, uploading, error, currentUpload } = useUpload();
  const [successCount, setSuccessCount] = useState(0);

  const handleFilesSelected = useCallback(async (files: File[]) => {
    let completed = 0;
    for (const file of files) {
      const uploadId = addUpload(file);
      try {
        await uploadFile(uploadId);
        completed++;
      } catch (err) {
        console.error('Upload failed:', err);
      }
    }
    if (completed > 0) {
      setSuccessCount(prev => prev + completed);
      setTimeout(() => setSuccessCount(0), 3000);
    }
  }, [addUpload, uploadFile]);

  return (
    <SpaceBetween size="l">
      {successCount > 0 && (
        <Alert type="success" dismissible onDismiss={() => setSuccessCount(0)}>
          {successCount} document{successCount > 1 ? 's' : ''} uploaded successfully! Processing will begin shortly.
        </Alert>
      )}
      {error && (
        <Alert type="error">
          {error}
        </Alert>
      )}
      {currentUpload && (
        <Box padding="m">
          <SpaceBetween size="xs">
            <Box fontSize="body-s" color="text-body-secondary">
              {currentUpload.status === 'complete' ? 'Upload complete!' : `Uploading: ${currentUpload.filename}`}
            </Box>
            <ProgressBar
              value={currentUpload.progress}
              status={
                currentUpload.status === 'error' ? 'error' :
                currentUpload.status === 'complete' ? 'success' : 'in-progress'
              }
              additionalInfo={
                currentUpload.status === 'error' ? currentUpload.error :
                currentUpload.status === 'complete' ? 'Processing will begin shortly' :
                `${currentUpload.progress}%`
              }
            />
          </SpaceBetween>
        </Box>
      )}
      <UploadZone onFilesSelected={handleFilesSelected} disabled={uploading} />
    </SpaceBetween>
  );
};

export const Upload = () => {
  const [activeTabId, setActiveTabId] = useState('documents');

  const tabs = [
    { id: 'documents', label: 'Documents', content: <DocumentUploadContent /> },
    { id: 'images', label: 'Images', content: <ImageUpload /> },
    { id: 'archive', label: 'Image Archive', content: <ZipUpload /> },
  ];

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Upload documents and images to your knowledge base">
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

        <ApiDocs
          title={apiExamples[activeTabId].title}
          description={apiExamples[activeTabId].description}
          endpoint={graphqlEndpoint}
          examples={apiExamples[activeTabId].examples}
        />
      </SpaceBetween>
    </ContentLayout>
  );
};
