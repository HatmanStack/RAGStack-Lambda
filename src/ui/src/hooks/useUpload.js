import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { uploadData } from 'aws-amplify/storage';
import gql from 'graphql-tag';

const CREATE_UPLOAD_URL = gql`
  mutation CreateUploadUrl($filename: String!) {
    createUploadUrl(filename: $filename) {
      uploadUrl
      documentId
      fields
    }
  }
`;

const client = generateClient();

export const useUpload = () => {
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);

  const addUpload = useCallback((file) => {
    const uploadId = Date.now() + Math.random();

    setUploads(prev => [...prev, {
      id: uploadId,
      file,
      status: 'pending',
      progress: 0,
      error: null,
      documentId: null
    }]);

    return uploadId;
  }, []);

  const uploadFile = useCallback(async (uploadId) => {
    const upload = uploads.find(u => u.id === uploadId);
    if (!upload) return;

    setUploading(true);

    try {
      // Update status
      setUploads(prev => prev.map(u =>
        u.id === uploadId ? { ...u, status: 'uploading', progress: 10 } : u
      ));

      // Get presigned URL
      const { data } = await client.graphql({
        query: CREATE_UPLOAD_URL,
        variables: { filename: upload.file.name }
      });

      const { documentId } = data.createUploadUrl;

      // Upload to S3 using Amplify Storage
      const operation = uploadData({
        path: `${documentId}/${upload.file.name}`,
        data: upload.file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            const progress = Math.round((transferredBytes / totalBytes) * 100);
            setUploads(prev => prev.map(u =>
              u.id === uploadId ? { ...u, progress } : u
            ));
          }
        }
      });

      await operation.result;

      // Update status to complete
      setUploads(prev => prev.map(u =>
        u.id === uploadId
          ? { ...u, status: 'complete', progress: 100, documentId }
          : u
      ));

    } catch (error) {
      console.error('Upload failed:', error);
      setUploads(prev => prev.map(u =>
        u.id === uploadId
          ? { ...u, status: 'failed', error: error.message }
          : u
      ));
    } finally {
      setUploading(false);
    }
  }, [uploads]);

  const removeUpload = useCallback((uploadId) => {
    setUploads(prev => prev.filter(u => u.id !== uploadId));
  }, []);

  const clearCompleted = useCallback(() => {
    setUploads(prev => prev.filter(u => u.status !== 'complete'));
  }, []);

  return {
    uploads,
    uploading,
    addUpload,
    uploadFile,
    removeUpload,
    clearCompleted
  };
};
