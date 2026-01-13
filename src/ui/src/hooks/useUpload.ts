import { useState, useCallback, useRef } from 'react';
import { generateClient } from 'aws-amplify/api';
import { uploadData } from 'aws-amplify/storage';
import gql from 'graphql-tag';
import type { GqlResponse } from '../types/graphql';

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
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pendingUploads = useRef(new Map<string, File>());

  const addUpload = useCallback((file: File) => {
    const uploadId = crypto.randomUUID();
    pendingUploads.current.set(uploadId, file);
    return uploadId;
  }, []);

  const uploadFile = useCallback(async (uploadId: string) => {
    const file = pendingUploads.current.get(uploadId);

    if (!file) {
      console.error('Upload not found for ID:', uploadId);
      throw new Error('Upload not found');
    }

    setUploading(true);
    setError(null);

    try {
      // Get presigned URL
      const response = await client.graphql({
        query: CREATE_UPLOAD_URL as ReturnType<typeof gql>,
        variables: { filename: file.name }
      }) as GqlResponse;

      const uploadResult = response.data?.createUploadUrl as { documentId?: string } | undefined;
      const { documentId } = uploadResult || {};

      // Upload to S3 using Amplify Storage (input/ prefix for DataBucket)
      const operation = uploadData({
        path: `input/${documentId}/${file.name}`,
        data: file
      });

      await operation.result;
      pendingUploads.current.delete(uploadId);

    } catch (err) {
      console.error('Upload failed:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
      throw err;
    } finally {
      setUploading(false);
    }
  }, []);

  return {
    uploading,
    error,
    addUpload,
    uploadFile
  };
};
