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

const docMutation = `mutation CreateUploadUrl($filename: String!) {
  createUploadUrl(filename: $filename) {
    uploadUrl, documentId, fields
  }
}`;

const imgMutation = `mutation CreateImageUploadUrl($filename: String!) {
  createImageUploadUrl(filename: $filename) {
    uploadUrl, imageId, s3Uri, fields
  }
}`;

const jsExample = `// 1. Get presigned URL
const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
  body: JSON.stringify({ query: \`${docMutation}\`, variables: { filename: 'doc.pdf' } })
});
const { uploadUrl, fields } = (await res.json()).data.createUploadUrl;

// 2. Upload to S3
const form = new FormData();
Object.entries(JSON.parse(fields)).forEach(([k, v]) => form.append(k, v));
form.append('file', file);
await fetch(uploadUrl, { method: 'POST', body: form });`;

const DocumentUploadContent = () => {
  const { uploadFile, uploading, queue, removeFromQueue, clearQueue } = useUpload();

  const handleFilesSelected = useCallback((files) => {
    files.forEach(file => uploadFile(file));
  }, [uploadFile]);

  return (
    <SpaceBetween size="l">
      <UploadZone onFilesSelected={handleFilesSelected} disabled={uploading} />
      <UploadQueue
        queue={queue}
        onRemove={removeFromQueue}
        onClear={clearQueue}
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

        {graphqlEndpoint && (
          <ApiDocs
            title="Upload API"
            description="Get presigned URL, then POST file to S3. Supports PDF, DOCX, TXT, images."
            endpoint={graphqlEndpoint}
            examples={[
              { id: 'doc', label: 'Document', code: docMutation },
              { id: 'img', label: 'Image', code: imgMutation },
              { id: 'js', label: 'JavaScript', code: jsExample },
            ]}
            footer="Files are automatically processed after upload."
          />
        )}
      </SpaceBetween>
    </ContentLayout>
  );
};
