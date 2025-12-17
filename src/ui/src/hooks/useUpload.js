import { useState, useCallback, useRef } from 'react';
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
  const uploadsRef = useRef([]);

  // Keep ref in sync with state
  uploadsRef.current = uploads;

  const addUpload = useCallback((file) => {
    const uploadId = crypto.randomUUID();

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
    // Use ref to get current uploads without stale closure
    const upload = uploadsRef.current.find(u => u.id === uploadId);

    if (!upload) {
      console.error('Upload not found for ID:', uploadId);
      return;
    }

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

      // Upload to S3 using Amplify Storage (input/ prefix for DataBucket)
      const operation = uploadData({
        path: `input/${documentId}/${upload.file.name}`,
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
