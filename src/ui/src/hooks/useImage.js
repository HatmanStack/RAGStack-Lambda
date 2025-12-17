import { useState, useCallback, useRef } from 'react';
import { generateClient } from 'aws-amplify/api';
import { uploadData } from 'aws-amplify/storage';
import { createImageUploadUrl } from '../graphql/mutations/createImageUploadUrl';
import { generateCaption as generateCaptionMutation } from '../graphql/mutations/generateCaption';
import { submitImage as submitImageMutation } from '../graphql/mutations/submitImage';
import { deleteImage as deleteImageMutation } from '../graphql/mutations/deleteImage';
import { getImage as getImageQuery } from '../graphql/queries/getImage';

const client = generateClient();

export const useImage = () => {
  const [images, setImages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const imagesRef = useRef([]);

  // Keep ref in sync with state
  imagesRef.current = images;

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const createUploadUrl = useCallback(async (filename) => {
    setError(null);
    try {
      const { data } = await client.graphql({
        query: createImageUploadUrl,
        variables: { filename }
      });

      if (!data?.createImageUploadUrl) {
        throw new Error('Failed to create upload URL');
      }

      return data.createImageUploadUrl;
    } catch (err) {
      console.error('Failed to create upload URL:', err);
      setError(err.message || 'Failed to create upload URL');
      throw err;
    }
  }, []);

  const uploadImage = useCallback(async (file, onProgress) => {
    setUploading(true);
    setError(null);

    try {
      // Get presigned URL
      const { imageId } = await createUploadUrl(file.name);

      // Track this upload in state
      const uploadId = crypto.randomUUID();
      setImages(prev => [...prev, {
        id: uploadId,
        imageId,
        file,
        filename: file.name,
        status: 'uploading',
        progress: 0,
        error: null
      }]);

      // Upload to S3 using Amplify Storage (images/ prefix for DataBucket)
      const operation = uploadData({
        path: `images/${imageId}/${file.name}`,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            const progress = Math.round((transferredBytes / totalBytes) * 100);
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

      return { imageId, filename: file.name };

    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.message || 'Failed to upload image');
      throw err;
    } finally {
      setUploading(false);
    }
  }, [createUploadUrl]);

  const generateCaptionForImage = useCallback(async (imageS3Uri) => {
    setGenerating(true);
    setError(null);

    try {
      const { data } = await client.graphql({
        query: generateCaptionMutation,
        variables: { imageS3Uri }
      });

      if (data?.generateCaption?.error) {
        throw new Error(data.generateCaption.error);
      }

      return data?.generateCaption?.caption || '';
    } catch (err) {
      console.error('Caption generation failed:', err);
      setError(err.message || 'Failed to generate caption');
      throw err;
    } finally {
      setGenerating(false);
    }
  }, []);

  const submitImageWithCaption = useCallback(async (imageId, caption, userCaption, aiCaption) => {
    setError(null);

    try {
      const { data } = await client.graphql({
        query: submitImageMutation,
        variables: {
          input: {
            imageId,
            caption,
            userCaption,
            aiCaption
          }
        }
      });

      if (!data?.submitImage) {
        throw new Error('Failed to submit image');
      }

      // Update image in state
      setImages(prev => prev.map(img =>
        img.imageId === imageId
          ? { ...img, status: 'submitted', ...data.submitImage }
          : img
      ));

      return data.submitImage;
    } catch (err) {
      console.error('Submit failed:', err);
      setError(err.message || 'Failed to submit image');
      throw err;
    }
  }, []);

  const deleteImageById = useCallback(async (imageId) => {
    setError(null);

    try {
      const { data } = await client.graphql({
        query: deleteImageMutation,
        variables: { imageId }
      });

      if (data?.deleteImage) {
        // Remove from state
        setImages(prev => prev.filter(img => img.imageId !== imageId));
        return true;
      }

      return false;
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err.message || 'Failed to delete image');
      throw err;
    }
  }, []);

  const getImageById = useCallback(async (imageId) => {
    setError(null);

    try {
      const { data } = await client.graphql({
        query: getImageQuery,
        variables: { imageId }
      });

      return data?.getImage;
    } catch (err) {
      console.error('Failed to get image:', err);
      setError(err.message || 'Failed to get image');
      throw err;
    }
  }, []);

  const removeImage = useCallback((imageId) => {
    setImages(prev => prev.filter(img => img.imageId !== imageId));
  }, []);

  const clearImages = useCallback(() => {
    setImages([]);
  }, []);

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
    clearImages
  };
};
