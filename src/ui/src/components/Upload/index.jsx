import React, { useState, useCallback } from 'react';
import {
  SpaceBetween,
  Tabs,
  ContentLayout,
  Header,
} from '@cloudscape-design/components';
import { UploadZone } from './UploadZone';
import { UploadQueue } from './UploadQueue';
import { ImageUpload } from '../ImageUpload';
import { ZipUpload } from '../ImageUpload/ZipUpload';
import { useUpload } from '../../hooks/useUpload';
import { ApiDocs } from '../common/ApiDocs';

const graphqlEndpoint = import.meta.env.VITE_GRAPHQL_URL || '';

// Document mutations
const docMutation = `mutation CreateUploadUrl($filename: String!) {
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

// Image mutations (with captions)
const imgUrlMutation = `mutation CreateImageUploadUrl($filename: String!) {
  createImageUploadUrl(filename: $filename) {
    uploadUrl, imageId, s3Uri, fields
  }
}`;

const imgSubmitMutation = `mutation SubmitImage($input: SubmitImageInput!) {
  submitImage(input: $input) {
    imageId, filename, status
  }
}`;

const imgJsExample = `// 1. Get presigned URL
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({ query: CREATE_IMAGE_UPLOAD_URL, variables: { filename: 'photo.jpg' } })
});
const { uploadUrl, imageId, fields } = (await res.json()).data.createImageUploadUrl;

// 2. Upload to S3
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', imageFile);
await fetch(uploadUrl, { method: 'POST', body: form });

// 3. Submit with caption (triggers processing)
await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({
    query: SUBMIT_IMAGE,
    variables: { input: { imageId, caption: 'Description of the image' } }
  })
});`;

// ZIP archive mutations
const zipMutation = `mutation CreateZipUploadUrl($generateCaptions: Boolean) {
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

// Examples config per tab
const apiExamples = {
  documents: {
    title: 'Document Upload API',
    description: 'Get presigned URL, upload to S3. Supports PDF, DOCX, TXT, HTML, MD.',
    examples: [
      { id: 'mutation', label: 'GraphQL', code: docMutation },
      { id: 'js', label: 'JavaScript', code: docJsExample },
    ],
  },
  images: {
    title: 'Image Upload API',
    description: 'Upload image, then submit with caption. Supports JPG, PNG, GIF, WEBP.',
    examples: [
      { id: 'url', label: 'Get URL', code: imgUrlMutation },
      { id: 'submit', label: 'Submit', code: imgSubmitMutation },
      { id: 'js', label: 'JavaScript', code: imgJsExample },
    ],
  },
  archive: {
    title: 'Image Archive Upload API',
    description: 'Upload ZIP of images for batch processing. Optional AI caption generation.',
    examples: [
      { id: 'mutation', label: 'GraphQL', code: zipMutation },
      { id: 'js', label: 'JavaScript', code: zipJsExample },
    ],
  },
};

const DocumentUploadContent = () => {
  const { addUpload, uploadFile, uploading, uploads, removeUpload, clearCompleted } = useUpload();

  const handleFilesSelected = useCallback((files) => {
    files.forEach(file => {
      const uploadId = addUpload(file);
      uploadFile(uploadId);
    });
  }, [addUpload, uploadFile]);

  return (
    <SpaceBetween size="l">
      <UploadZone onFilesSelected={handleFilesSelected} disabled={uploading} />
      <UploadQueue
        uploads={uploads}
        onRemove={removeUpload}
        onClearCompleted={clearCompleted}
      />
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
