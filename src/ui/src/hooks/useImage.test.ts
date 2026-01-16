import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Create mock functions that can be referenced in the hoisted mock
const mockGraphqlFn = vi.fn();
const mockUploadDataFn = vi.fn();

// Mock aws-amplify/api - use factory that returns object with the mock fn
vi.mock('aws-amplify/api', () => {
  return {
    generateClient: () => ({
      graphql: (...args: unknown[]) => mockGraphqlFn(...args)
    })
  };
});

// Mock aws-amplify/storage
vi.mock('aws-amplify/storage', () => {
  return {
    uploadData: (...args: unknown[]) => mockUploadDataFn(...args)
  };
});

// Import after mocks are set up
import { useImage } from './useImage';

describe('useImage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGraphqlFn.mockReset();
    mockUploadDataFn.mockReset();
  });

  describe('createUploadUrl', () => {
    it('returns upload URL and imageId on success', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          createImageUploadUrl: {
            uploadUrl: 'https://s3.example.com/presigned',
            imageId: 'img-123',
            fields: null
          }
        }
      });

      const { result } = renderHook(() => useImage());

      let response;
      await act(async () => {
        response = await result.current.createUploadUrl('test.png');
      });

      expect(response).toEqual({
        uploadUrl: 'https://s3.example.com/presigned',
        imageId: 'img-123',
        fields: null
      });
      expect(result.current.error).toBeNull();
    });

    it('sets error on failure', async () => {
      mockGraphqlFn.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useImage());

      await act(async () => {
        try {
          await result.current.createUploadUrl('test.png');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).toBe('Network error');
    });
  });

  describe('generateCaption', () => {
    it('returns caption on success', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          generateCaption: {
            caption: 'A beautiful sunset over mountains',
            error: null
          }
        }
      });

      const { result } = renderHook(() => useImage());

      let caption;
      await act(async () => {
        caption = await result.current.generateCaption('s3://bucket/images/img-123/test.png');
      });

      expect(caption).toBe('A beautiful sunset over mountains');
      expect(result.current.generating).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('sets generating state during API call', async () => {
      let resolvePromise: ((value: unknown) => void) | undefined;
      const promise = new Promise(resolve => {
        resolvePromise = resolve;
      });
      mockGraphqlFn.mockReturnValueOnce(promise);

      const { result } = renderHook(() => useImage());

      act(() => {
        result.current.generateCaption('s3://bucket/images/img-123/test.png');
      });

      expect(result.current.generating).toBe(true);

      await act(async () => {
        resolvePromise?.({
          data: {
            generateCaption: { caption: 'Test caption', error: null }
          }
        });
      });

      expect(result.current.generating).toBe(false);
    });

    it('sets error when API returns error field', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          generateCaption: {
            caption: null,
            error: 'Model not available'
          }
        }
      });

      const { result } = renderHook(() => useImage());

      await act(async () => {
        try {
          await result.current.generateCaption('s3://bucket/images/img-123/test.png');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).toBe('Model not available');
    });
  });

  describe('submitImage', () => {
    it('submits image with combined caption', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          submitImage: {
            imageId: 'img-123',
            filename: 'test.png',
            caption: 'User caption. AI generated description.',
            userCaption: 'User caption',
            aiCaption: 'AI generated description.',
            status: 'PENDING',
            s3Uri: 's3://bucket/images/img-123/test.png'
          }
        }
      });

      const { result } = renderHook(() => useImage());

      let response: Record<string, unknown> | undefined;
      await act(async () => {
        response = await result.current.submitImage(
          'img-123',
          'User caption. AI generated description.',
          'User caption',
          'AI generated description.'
        );
      });

      expect(response?.imageId).toBe('img-123');
      expect(response?.caption).toBe('User caption. AI generated description.');
      expect(mockGraphqlFn).toHaveBeenCalledWith({
        query: expect.anything(),
        variables: {
          input: {
            imageId: 'img-123',
            caption: 'User caption. AI generated description.',
            userCaption: 'User caption',
            aiCaption: 'AI generated description.',
            extractText: false
          }
        }
      });
    });

    it('sets error on failure', async () => {
      mockGraphqlFn.mockRejectedValueOnce(new Error('Submit failed'));

      const { result } = renderHook(() => useImage());

      await act(async () => {
        try {
          await result.current.submitImage('img-123', 'caption', 'user', 'ai');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).toBe('Submit failed');
    });
  });

  describe('deleteImage', () => {
    it('deletes image successfully', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          deleteImage: true
        }
      });

      const { result } = renderHook(() => useImage());

      let success;
      await act(async () => {
        success = await result.current.deleteImage('img-123');
      });

      expect(success).toBe(true);
      expect(result.current.error).toBeNull();
    });

    it('returns false when deletion fails', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          deleteImage: false
        }
      });

      const { result } = renderHook(() => useImage());

      let success;
      await act(async () => {
        success = await result.current.deleteImage('img-123');
      });

      expect(success).toBe(false);
    });
  });

  describe('getImage', () => {
    it('fetches image by ID', async () => {
      const mockImage = {
        imageId: 'img-123',
        filename: 'test.png',
        caption: 'Test caption',
        status: 'INDEXED',
        s3Uri: 's3://bucket/images/img-123/test.png',
        thumbnailUrl: 'https://example.com/thumb.png'
      };

      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          getImage: mockImage
        }
      });

      const { result } = renderHook(() => useImage());

      let image;
      await act(async () => {
        image = await result.current.getImage('img-123');
      });

      expect(image).toEqual(mockImage);
    });
  });

  describe('state management', () => {
    it('clears error with clearError', async () => {
      mockGraphqlFn.mockRejectedValueOnce(new Error('Test error'));

      const { result } = renderHook(() => useImage());

      await act(async () => {
        try {
          await result.current.createUploadUrl('test.png');
        } catch {
          // Expected
        }
      });

      expect(result.current.error).toBe('Test error');

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });

    it('removes image from local state', () => {
      const { result } = renderHook(() => useImage());

      act(() => {
        result.current.clearImages();
      });

      expect(result.current.images).toEqual([]);
    });

    it('clears all images with clearImages', () => {
      const { result } = renderHook(() => useImage());

      act(() => {
        result.current.clearImages();
      });

      expect(result.current.images).toEqual([]);
    });
  });

  describe('uploadImage', () => {
    it('uploads image to S3 and tracks progress', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          createImageUploadUrl: {
            uploadUrl: 'https://s3.example.com/presigned',
            imageId: 'img-456',
            fields: null
          }
        }
      });

      mockUploadDataFn.mockImplementation(({ options }) => {
        // Simulate progress callback
        if (options?.onProgress) {
          options.onProgress({ transferredBytes: 50, totalBytes: 100 });
        }
        return {
          result: Promise.resolve({})
        };
      });

      const { result } = renderHook(() => useImage());

      const mockFile = new File(['test'], 'test.png', { type: 'image/png' });
      const onProgress = vi.fn();

      let uploadResult;
      await act(async () => {
        uploadResult = await result.current.uploadImage(mockFile, onProgress);
      });

      expect(uploadResult).toEqual({
        imageId: 'img-456',
        filename: 'test.png'
      });

      expect(mockUploadDataFn).toHaveBeenCalledWith({
        path: 'content/img-456/test.png',
        data: mockFile,
        options: expect.objectContaining({
          onProgress: expect.any(Function)
        })
      });
    });

    it('sets uploading state during upload', async () => {
      mockGraphqlFn.mockResolvedValueOnce({
        data: {
          createImageUploadUrl: {
            uploadUrl: 'https://s3.example.com/presigned',
            imageId: 'img-789',
            fields: null
          }
        }
      });

      let resolveUpload: ((value: unknown) => void) | undefined;
      mockUploadDataFn.mockImplementation(() => ({
        result: new Promise(resolve => {
          resolveUpload = resolve;
        })
      }));

      const { result } = renderHook(() => useImage());
      const mockFile = new File(['test'], 'test.png', { type: 'image/png' });

      act(() => {
        result.current.uploadImage(mockFile);
      });

      // Wait for the graphql call to complete and uploading state to be set
      await waitFor(() => {
        expect(result.current.uploading).toBe(true);
      });

      await act(async () => {
        resolveUpload?.({});
      });

      expect(result.current.uploading).toBe(false);
    });
  });
});
