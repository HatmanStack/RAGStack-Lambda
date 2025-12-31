import { useState, useEffect, useCallback, useMemo } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import { listScrapeJobs } from '../graphql/queries/listScrapeJobs';
import { listImages } from '../graphql/queries/listImages';
import { deleteDocuments as deleteDocumentsMutation } from '../graphql/mutations/deleteDocuments';

// Type helper for GraphQL responses - Amplify returns a union type but we know queries return this shape
type GqlResponse<T = Record<string, unknown>> = { data?: T; errors?: Array<{ message: string }> };

const LIST_DOCUMENTS = gql`
  query ListDocuments {
    listDocuments {
      items {
        documentId
        filename
        status
        totalPages
        isTextNative
        fileType
        createdAt
        updatedAt
        errorMessage
      }
    }
  }
`;

const GET_DOCUMENT = gql`
  query GetDocument($documentId: ID!) {
    getDocument(documentId: $documentId) {
      documentId
      filename
      inputS3Uri
      outputS3Uri
      status
      fileType
      isTextNative
      totalPages
      errorMessage
      createdAt
      updatedAt
      metadata
      previewUrl
    }
  }
`;

// Subscription for real-time document updates
const ON_DOCUMENT_UPDATE = gql`
  subscription OnDocumentUpdate {
    onDocumentUpdate {
      documentId
      filename
      status
      totalPages
      errorMessage
      updatedAt
    }
  }
`;

// Subscription for real-time scrape job updates
const ON_SCRAPE_UPDATE = gql`
  subscription OnScrapeUpdate {
    onScrapeUpdate {
      jobId
      baseUrl
      title
      status
      totalUrls
      processedCount
      failedCount
      updatedAt
    }
  }
`;

// Subscription for real-time image updates
const ON_IMAGE_UPDATE = gql`
  subscription OnImageUpdate {
    onImageUpdate {
      imageId
      filename
      caption
      status
      s3Uri
      thumbnailUrl
      errorMessage
      updatedAt
    }
  }
`;

const client = generateClient();

export const useDocuments = () => {
  const [documents, setDocuments] = useState([]);
  const [scrapeJobs, setScrapeJobs] = useState([]);
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchImages = useCallback(async () => {
    try {
      let allItems = [];
      let nextToken = null;

      do {
        const response = await client.graphql({
          query: listImages as any,
          variables: { limit: 100, nextToken }
        }) as GqlResponse;

        if (response.errors) {
          console.error('[useDocuments] GraphQL errors fetching images:', response.errors);
          break;
        }

        const { data } = response;
        const listResult = data?.listImages as { items?: unknown[]; nextToken?: string } | undefined;
        const items = listResult?.items || [];
        allItems = [...allItems, ...items];
        nextToken = listResult?.nextToken;
      } while (nextToken);

      // Transform images to match document structure for unified display
      const transformedImages = allItems.map(img => ({
        documentId: img.imageId,
        filename: img.filename,
        status: img.status,
        caption: img.caption,
        createdAt: img.createdAt,
        updatedAt: img.updatedAt,
        type: 'image',
        thumbnailUrl: img.thumbnailUrl,
        s3Uri: img.s3Uri
      }));
      setImages(transformedImages);
    } catch (err) {
      console.error('Failed to fetch images:', err);
    }
  }, []);

  const fetchScrapeJobs = useCallback(async () => {
    try {
      let allItems = [];
      let nextToken = null;

      do {
        const response = await client.graphql({
          query: listScrapeJobs as any,
          variables: { limit: 100, nextToken }
        }) as GqlResponse;

        if (response.errors) {
          console.error('[useDocuments] GraphQL errors fetching scrape jobs:', response.errors);
          break;
        }

        const { data } = response;
        const listResult = data?.listScrapeJobs as { items?: unknown[]; nextToken?: string } | undefined;
        const items = listResult?.items || [];
        allItems = [...allItems, ...items];
        nextToken = listResult?.nextToken;
      } while (nextToken);

      // Transform scrape jobs to match document structure for unified display
      const transformedJobs = allItems.map(job => ({
        documentId: job.jobId,
        filename: job.title || job.baseUrl,
        status: job.status,
        totalPages: job.totalUrls,
        processedCount: job.processedCount,
        failedCount: job.failedCount,
        createdAt: job.createdAt,
        updatedAt: job.createdAt,
        type: 'scrape',
        baseUrl: job.baseUrl
      }));
      setScrapeJobs(transformedJobs);
    } catch (err) {
      console.error('Failed to fetch scrape jobs:', err);
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await client.graphql({
        query: LIST_DOCUMENTS as any
      }) as GqlResponse;

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors fetching documents:', response.errors);
      }

      const { data } = response;
      const listResult = data?.listDocuments as { items?: unknown[] } | undefined;
      const newDocs = (listResult?.items || []).map(doc => ({
        ...(doc as Record<string, unknown>),
        type: 'document'
      }));

      setDocuments(newDocs);

      // Also fetch scrape jobs and images
      await Promise.all([fetchScrapeJobs(), fetchImages()]);

    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchScrapeJobs, fetchImages]);

  const refreshDocuments = useCallback(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const fetchDocument = useCallback(async (documentId: string) => {
    try {
      const response = await client.graphql({
        query: GET_DOCUMENT as any,
        variables: { documentId }
      }) as GqlResponse;

      return response.data?.getDocument;
    } catch (err) {
      console.error('Failed to fetch document:', err);
      throw err;
    }
  }, []);

  // Handle real-time document update
  const handleDocumentUpdate = useCallback((update) => {
    setDocuments(prev => {
      const idx = prev.findIndex(d => d.documentId === update.documentId);
      if (idx >= 0) {
        // Update existing document
        const updated = [...prev];
        updated[idx] = { ...updated[idx], ...update, type: 'document' };
        return updated;
      }
      // New document - add to list
      return [{ ...update, type: 'document' }, ...prev];
    });
  }, []);

  // Handle real-time scrape update
  const handleScrapeUpdate = useCallback((update) => {
    setScrapeJobs(prev => {
      const idx = prev.findIndex(j => j.documentId === update.jobId);
      if (idx >= 0) {
        // Update existing job
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          status: update.status,
          totalPages: update.totalUrls,
          processedCount: update.processedCount,
          failedCount: update.failedCount,
          filename: update.title || update.baseUrl,
          updatedAt: update.updatedAt
        };
        return updated;
      }
      // New job - add to list
      return [{
        documentId: update.jobId,
        filename: update.title || update.baseUrl,
        status: update.status,
        totalPages: update.totalUrls,
        processedCount: update.processedCount,
        failedCount: update.failedCount,
        createdAt: update.updatedAt,
        updatedAt: update.updatedAt,
        type: 'scrape',
        baseUrl: update.baseUrl
      }, ...prev];
    });
  }, []);

  // Handle real-time image update
  const handleImageUpdate = useCallback((update) => {
    setImages(prev => {
      const idx = prev.findIndex(img => img.documentId === update.imageId);
      if (idx >= 0) {
        // Update existing image
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          status: update.status,
          caption: update.caption || updated[idx].caption,
          thumbnailUrl: update.thumbnailUrl || updated[idx].thumbnailUrl,
          errorMessage: update.errorMessage,
          updatedAt: update.updatedAt
        };
        return updated;
      }
      // New image - add to list
      return [{
        documentId: update.imageId,
        filename: update.filename,
        status: update.status,
        caption: update.caption,
        thumbnailUrl: update.thumbnailUrl,
        s3Uri: update.s3Uri,
        createdAt: update.updatedAt,
        updatedAt: update.updatedAt,
        type: 'image'
      }, ...prev];
    });
  }, []);

  // Delete documents by IDs
  const deleteDocuments = useCallback(async (documentIds: string[]) => {
    if (!documentIds || documentIds.length === 0) {
      return { deletedCount: 0, failedIds: [] as string[], errors: [] as string[] };
    }

    try {
      const response = await client.graphql({
        query: deleteDocumentsMutation as any,
        variables: { documentIds }
      }) as GqlResponse;

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors deleting documents:', response.errors);
        throw new Error(response.errors[0]?.message || 'Failed to delete documents');
      }

      const result = response.data?.deleteDocuments as { deletedCount: number; failedIds?: string[] } || { deletedCount: 0 };

      // Remove successfully deleted documents from local state
      if (result.deletedCount > 0) {
        const deletedSet = new Set(documentIds);
        const failedSet = new Set(result.failedIds || []);

        // Filter out successfully deleted items from all collections
        setDocuments(prev => prev.filter(d => !deletedSet.has(d.documentId) || failedSet.has(d.documentId)));
        setScrapeJobs(prev => prev.filter(j => !deletedSet.has(j.documentId) || failedSet.has(j.documentId)));
        setImages(prev => prev.filter(i => !deletedSet.has(i.documentId) || failedSet.has(i.documentId)));
      }

      return result;
    } catch (err) {
      console.error('Failed to delete documents:', err);
      throw err;
    }
  }, []);

  useEffect(() => {
    // Initial fetch on mount
    fetchDocuments();

    // Set up subscriptions for real-time updates
    let docSubscription = null;
    let scrapeSubscription = null;
    let imageSubscription = null;

    try {
      // Subscribe to document updates
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      docSubscription = (client.graphql({
        query: ON_DOCUMENT_UPDATE as any
      }) as any).subscribe({
        next: ({ data }: { data?: { onDocumentUpdate?: unknown } }) => {
          if (data?.onDocumentUpdate) {
            handleDocumentUpdate(data.onDocumentUpdate);
          }
        },
        error: (err: Error) => {
          console.error('[useDocuments] Document subscription error:', err);
        }
      });

      // Subscribe to scrape updates
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      scrapeSubscription = (client.graphql({
        query: ON_SCRAPE_UPDATE as any
      }) as any).subscribe({
        next: ({ data }: { data?: { onScrapeUpdate?: unknown } }) => {
          if (data?.onScrapeUpdate) {
            handleScrapeUpdate(data.onScrapeUpdate);
          }
        },
        error: (err: Error) => {
          console.error('[useDocuments] Scrape subscription error:', err);
        }
      });

      // Subscribe to image updates
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      imageSubscription = (client.graphql({
        query: ON_IMAGE_UPDATE as any
      }) as any).subscribe({
        next: ({ data }: { data?: { onImageUpdate?: unknown } }) => {
          if (data?.onImageUpdate) {
            handleImageUpdate(data.onImageUpdate);
          }
        },
        error: (err: Error) => {
          console.error('[useDocuments] Image subscription error:', err);
        }
      });

    } catch (err) {
      console.error('[useDocuments] Failed to set up subscriptions:', err);
    }

    // Cleanup subscriptions on unmount
    return () => {
      if (docSubscription) docSubscription.unsubscribe();
      if (imageSubscription) imageSubscription.unsubscribe();
      if (scrapeSubscription) scrapeSubscription.unsubscribe();
    };
  }, [fetchDocuments, handleDocumentUpdate, handleScrapeUpdate, handleImageUpdate]);

  // Merge and deduplicate by documentId with type precedence: image > scrape > document
  const allItems = useMemo(() => {
    const typePriority = { image: 3, scrape: 2, document: 1 };
    const itemMap = new Map();

    [...documents, ...scrapeJobs, ...images].forEach(item => {
      const existing = itemMap.get(item.documentId);
      if (!existing || typePriority[item.type] > typePriority[existing.type]) {
        itemMap.set(item.documentId, item);
      }
    });

    return Array.from(itemMap.values()).sort((a, b) => {
      const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
      const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
      return dateB - dateA;
    });
  }, [documents, scrapeJobs, images]);

  return {
    documents: allItems,
    loading,
    error,
    fetchDocuments,
    refreshDocuments,
    fetchDocument,
    deleteDocuments
  };
};
