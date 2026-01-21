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

// Media extensions that go to content/ for EventBridge → ProcessMedia flow
const MEDIA_EXTENSIONS = new Set(['.mp4', '.webm', '.mp3', '.wav', '.m4a', '.ogg']);

export interface UploadProgress {
  filename: string;
  progress: number; // 0-100
  status: 'pending' | 'uploading' | 'complete' | 'error';
  error?: string;
}

export const useUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentUpload, setCurrentUpload] = useState<UploadProgress | null>(null);
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
    setCurrentUpload({ filename: file.name, progress: 0, status: 'pending' });

    try {
      // Get presigned URL
      setCurrentUpload({ filename: file.name, progress: 5, status: 'uploading' });
      const response = await client.graphql({
        query: CREATE_UPLOAD_URL as unknown as string,
        variables: { filename: file.name }
      }) as GqlResponse;

      const uploadResult = response.data?.createUploadUrl as { documentId?: string } | undefined;
      const { documentId } = uploadResult || {};

      // Upload to S3 using Amplify Storage with progress tracking
      // Media files go to content/ (processed by EventBridge → ProcessMedia)
      // Documents go to input/ (processed by Step Functions)
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      const isMedia = MEDIA_EXTENSIONS.has(ext);
      const uploadPath = isMedia
        ? `content/${documentId}/${file.name}`
        : `input/${documentId}/${file.name}`;

      setCurrentUpload({ filename: file.name, progress: 10, status: 'uploading' });
      const operation = uploadData({
        path: uploadPath,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            if (totalBytes) {
              // Scale progress from 10-95% (5% for URL, 5% for completion)
              const uploadProgress = Math.round((transferredBytes / totalBytes) * 85) + 10;
              setCurrentUpload({ filename: file.name, progress: uploadProgress, status: 'uploading' });
            }
          }
        }
      });

      await operation.result;
      setCurrentUpload({ filename: file.name, progress: 100, status: 'complete' });
      pendingUploads.current.delete(uploadId);

      // Clear after brief delay to show completion
      setTimeout(() => setCurrentUpload(null), 1500);

    } catch (err) {
      console.error('Upload failed:', err);
      let errorMsg = 'Upload failed';

      if (err instanceof Error) {
        errorMsg = err.message;
      }

      // Check for GraphQL errors which may contain demo mode quota messages
      const gqlError = err as { errors?: Array<{ message: string }> };
      if (gqlError?.errors?.length) {
        const firstError = gqlError.errors[0].message;
        // Check for demo mode upload quota error
        if (firstError.toLowerCase().includes('demo mode') &&
            firstError.toLowerCase().includes('upload limit')) {
          errorMsg = 'Daily upload limit reached in Demo Mode. Please try again tomorrow.';
        } else {
          errorMsg = firstError;
        }
      }

      setError(errorMsg);
      setCurrentUpload({ filename: file.name, progress: 0, status: 'error', error: errorMsg });
      throw err;
    } finally {
      setUploading(false);
    }
  }, []);

  const clearUploadProgress = useCallback(() => {
    setCurrentUpload(null);
  }, []);

  return {
    uploading,
    error,
    currentUpload,
    addUpload,
    uploadFile,
    clearUploadProgress
  };
};
