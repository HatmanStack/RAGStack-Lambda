import { useState, useCallback, useRef } from 'react';
import { generateClient } from 'aws-amplify/api';
import { uploadData } from 'aws-amplify/storage';
import { createImageUploadUrl } from '../graphql/mutations/createImageUploadUrl';
import { createZipUploadUrl as createZipUploadUrlMutation } from '../graphql/mutations/createZipUploadUrl';
import { generateCaption as generateCaptionMutation } from '../graphql/mutations/generateCaption';
import { submitImage as submitImageMutation } from '../graphql/mutations/submitImage';
import { deleteImage as deleteImageMutation } from '../graphql/mutations/deleteImage';
import { getImage as getImageQuery } from '../graphql/queries/getImage';
import type { GqlResponse } from '../types/graphql';

export interface ImageUpload {
  id: string;
  imageId: string;
  s3Uri: string;
  file: File;
  filename: string;
  status: 'uploading' | 'uploaded' | 'submitted' | 'error';
  progress: number;
  error: string | null;
  [key: string]: unknown;
}

const client = generateClient();

export const useImage = () => {
  const [images, setImages] = useState<ImageUpload[]>([]);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imagesRef = useRef<ImageUpload[]>([]);

  // Keep ref in sync with state
  imagesRef.current = images;

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const createUploadUrl = useCallback(async (filename: string) => {
    setError(null);
    try {
      const response = await client.graphql({
        query: createImageUploadUrl as unknown as string,
        variables: { filename }
      }) as GqlResponse;

      if (!response.data?.createImageUploadUrl) {
        throw new Error('Failed to create upload URL');
      }

      return response.data.createImageUploadUrl as { imageId: string; s3Uri: string };
    } catch (err) {
      console.error('Failed to create upload URL:', err);
      setError(err instanceof Error ? err.message : 'Failed to create upload URL');
      throw err;
    }
  }, []);

  const uploadImage = useCallback(async (file: File, onProgress?: (progress: number) => void) => {
    setUploading(true);
    setError(null);

    try {
      // Get presigned URL
      const { imageId, s3Uri } = await createUploadUrl(file.name);

      // Track this upload in state
      const uploadId = crypto.randomUUID();
      setImages(prev => [...prev, {
        id: uploadId,
        imageId,
        s3Uri,
        file,
        filename: file.name,
        status: 'uploading',
        progress: 0,
        error: null
      }]);

      // Upload to S3 using Amplify Storage (content/ prefix for DataBucket)
      const operation = uploadData({
        path: `content/${imageId}/${file.name}`,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            const progress = totalBytes ? Math.round((transferredBytes / totalBytes) * 100) : 0;
            setImages(prev => prev.map(img =>
              img.imageId === imageId ? { ...img, progress } : img
            ));
            if (onProgress) {
              onProgress(progress);
            }
          }
        }
      });

      await operation.result;

      // Update status to uploaded
      setImages(prev => prev.map(img =>
        img.imageId === imageId
          ? { ...img, status: 'uploaded', progress: 100 }
          : img
      ));

      return { imageId, s3Uri, filename: file.name };

    } catch (err) {
      console.error('Upload failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to upload image');
      throw err;
    } finally {
      setUploading(false);
    }
  }, [createUploadUrl]);

  const generateCaptionForImage = useCallback(async (imageS3Uri: string) => {
    setGenerating(true);
    setError(null);

    try {
      const response = await client.graphql({
        query: generateCaptionMutation as unknown as string,
        variables: { imageS3Uri }
      }) as GqlResponse;

      const captionResult = response.data?.generateCaption as { error?: string; caption?: string } | undefined;
      if (captionResult?.error) {
        throw new Error(captionResult.error);
      }

      return captionResult?.caption || '';
    } catch (err) {
      console.error('Caption generation failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to generate caption');
      throw err;
    } finally {
      setGenerating(false);
    }
  }, []);

  const submitImageWithCaption = useCallback(async (
    imageId: string,
    caption: string,
    userCaption?: string,
    aiCaption?: string,
    extractText?: boolean
  ) => {
    setError(null);

    try {
      const response = await client.graphql({
        query: submitImageMutation as unknown as string,
        variables: {
          input: {
            imageId,
            caption,
            userCaption,
            aiCaption,
            extractText: extractText || false
          }
        }
      }) as GqlResponse;

      const submitResult = response.data?.submitImage as Record<string, unknown> | undefined;
      if (!submitResult) {
        throw new Error('Failed to submit image');
      }

      // Update image in state
      setImages(prev => prev.map(img =>
        img.imageId === imageId
          ? { ...img, status: 'submitted', ...submitResult }
          : img
      ));

      return submitResult;
    } catch (err) {
      console.error('Submit failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to submit image');
      throw err;
    }
  }, []);

  const deleteImageById = useCallback(async (imageId: string) => {
    setError(null);

    try {
      const response = await client.graphql({
        query: deleteImageMutation as unknown as string,
        variables: { imageId }
      }) as GqlResponse;

      if (response.data?.deleteImage) {
        // Remove from state
        setImages(prev => prev.filter(img => img.imageId !== imageId));
        return true;
      }

      return false;
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete image');
      throw err;
    }
  }, []);

  const getImageById = useCallback(async (imageId: string) => {
    setError(null);

    try {
      const response = await client.graphql({
        query: getImageQuery as unknown as string,
        variables: { imageId }
      }) as GqlResponse;

      return response.data?.getImage;
    } catch (err) {
      console.error('Failed to get image:', err);
      setError(err instanceof Error ? err.message : 'Failed to get image');
      throw err;
    }
  }, []);

  const removeImage = useCallback((imageId: string) => {
    setImages(prev => prev.filter(img => img.imageId !== imageId));
  }, []);

  const clearImages = useCallback(() => {
    setImages([]);
  }, []);

  const createZipUploadUrl = useCallback(async (generateCaptions = false) => {
    setError(null);
    try {
      const response = await client.graphql({
        query: createZipUploadUrlMutation as unknown as string,
        variables: { generateCaptions }
      }) as GqlResponse;

      if (!response.data?.createZipUploadUrl) {
        throw new Error('Failed to create ZIP upload URL');
      }

      return response.data.createZipUploadUrl as { uploadId: string };
    } catch (err) {
      console.error('Failed to create ZIP upload URL:', err);
      setError(err instanceof Error ? err.message : 'Failed to create ZIP upload URL');
      throw err;
    }
  }, []);

  const uploadZip = useCallback(async (file: File, generateCaptions = false, onProgress?: (progress: number) => void) => {
    setUploading(true);
    setError(null);

    try {
      // Get presigned URL
      const { uploadId } = await createZipUploadUrl(generateCaptions);

      // Upload to S3 using Amplify Storage (uploads/ prefix)
      const operation = uploadData({
        path: `uploads/${uploadId}/archive.zip`,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            const progress = totalBytes ? Math.round((transferredBytes / totalBytes) * 100) : 0;
            if (onProgress) {
              onProgress(progress);
            }
          }
        }
      });

      await operation.result;

      return { uploadId };

    } catch (err) {
      console.error('ZIP upload failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to upload ZIP');
      throw err;
    } finally {
      setUploading(false);
    }
  }, [createZipUploadUrl]);

  return {
    images,
    uploading,
    generating,
    error,
    clearError,
    createUploadUrl,
    uploadImage,
    generateCaption: generateCaptionForImage,
    submitImage: submitImageWithCaption,
    deleteImage: deleteImageById,
    getImage: getImageById,
    removeImage,
    clearImages,
    createZipUploadUrl,
    uploadZip
  };
};
