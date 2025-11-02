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
    console.log('uploadFile called with ID:', uploadId);

    // Use functional setState to get current uploads without stale closure
    let upload = null;
    setUploads(prev => {
      upload = prev.find(u => u.id === uploadId);
      return prev; // Don't modify state here
    });

    if (!upload) {
      console.error('Upload not found for ID:', uploadId);
      return;
    }

    console.log('Found upload:', upload);
    setUploading(true);

    try {
      // Update status
      setUploads(prev => prev.map(u =>
        u.id === uploadId ? { ...u, status: 'uploading', progress: 10 } : u
      ));

      // Get presigned URL
      console.log('Requesting presigned URL for:', upload.file.name);
      const { data } = await client.graphql({
        query: CREATE_UPLOAD_URL,
        variables: { filename: upload.file.name }
      });

      console.log('Received presigned URL response:', data.createUploadUrl);
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

      const result = await operation.result;
      console.log('Upload to S3 complete:', result);

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
  }, []); // Empty dependency array - no stale closures!

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
