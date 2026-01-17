import { useState, useEffect, useCallback, useMemo } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import { listScrapeJobs } from '../graphql/queries/listScrapeJobs';
import { listImages } from '../graphql/queries/listImages';
import { deleteDocuments as deleteDocumentsMutation } from '../graphql/mutations/deleteDocuments';
import { reprocessDocument as reprocessDocumentMutation } from '../graphql/mutations/reprocessDocument';
import { reindexDocument as reindexDocumentMutation } from '../graphql/mutations/reindexDocument';

// Type helper for GraphQL responses - Amplify returns a union type but we know queries return this shape
type GqlResponse<T = Record<string, unknown>> = { data?: T; errors?: Array<{ message: string }> };

// Document item type
export interface DocumentItem {
  documentId: string;
  filename: string;
  status: string;
  totalPages?: number;
  isTextNative?: boolean;
  fileType?: string;
  createdAt?: string;
  updatedAt?: string;
  errorMessage?: string;
  type: 'document' | 'scrape' | 'image' | 'media';
  // Scrape-specific
  processedCount?: number;
  failedCount?: number;
  baseUrl?: string;
  // Image-specific
  caption?: string;
  thumbnailUrl?: string;
  s3Uri?: string;
  // Media-specific (video/audio) - string to handle MIME types from backend
  mediaType?: string;
  durationSeconds?: number;
}

// Update event types
interface DocumentUpdateEvent {
  documentId: string;
  filename?: string;
  status?: string;
  totalPages?: number;
  errorMessage?: string;
  updatedAt?: string;
}

interface ScrapeUpdateEvent {
  jobId: string;
  baseUrl?: string;
  title?: string;
  status?: string;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  updatedAt?: string;
}

interface ImageUpdateEvent {
  imageId: string;
  filename?: string;
  caption?: string;
  status?: string;
  s3Uri?: string;
  thumbnailUrl?: string;
  errorMessage?: string;
  updatedAt?: string;
}

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
        type
        mediaType
        durationSeconds
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
      errorMessage
      updatedAt
    }
  }
`;

const client = generateClient();

export const useDocuments = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [scrapeJobs, setScrapeJobs] = useState<DocumentItem[]>([]);
  const [images, setImages] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchImages = useCallback(async () => {
    try {
      let allItems: Record<string, unknown>[] = [];
      let nextToken: string | null = null;

      do {
        const response = await client.graphql({
          query: listImages as unknown as string,
          variables: { limit: 100, nextToken }
        }) as GqlResponse;

        if (response.errors) {
          console.error('[useDocuments] GraphQL errors fetching images:', response.errors);
          break;
        }

        const { data } = response;
        const listResult = data?.listImages as { items?: Record<string, unknown>[]; nextToken?: string } | undefined;
        const items = listResult?.items || [];
        allItems = [...allItems, ...items];
        nextToken = listResult?.nextToken || null;
      } while (nextToken);

      // Transform images to match document structure for unified display
      const transformedImages: DocumentItem[] = allItems.map(img => ({
        documentId: img.imageId as string,
        filename: img.filename as string,
        status: img.status as string,
        caption: img.caption as string | undefined,
        createdAt: img.createdAt as string | undefined,
        updatedAt: img.updatedAt as string | undefined,
        type: 'image',
        thumbnailUrl: img.thumbnailUrl as string | undefined,
        s3Uri: img.s3Uri as string | undefined
      }));
      setImages(transformedImages);
    } catch (err) {
      console.error('Failed to fetch images:', err);
    }
  }, []);

  const fetchScrapeJobs = useCallback(async () => {
    try {
      let allItems: Record<string, unknown>[] = [];
      let nextToken: string | null = null;

      do {
        const response = await client.graphql({
          query: listScrapeJobs as unknown as string,
          variables: { limit: 100, nextToken }
        }) as GqlResponse;

        if (response.errors) {
          console.error('[useDocuments] GraphQL errors fetching scrape jobs:', response.errors);
          break;
        }

        const { data } = response;
        const listResult = data?.listScrapeJobs as { items?: Record<string, unknown>[]; nextToken?: string } | undefined;
        const items = listResult?.items || [];
        allItems = [...allItems, ...items];
        nextToken = listResult?.nextToken || null;
      } while (nextToken);

      // Transform scrape jobs to match document structure for unified display
      // Note: ScrapeJob type doesn't have updatedAt, so we leave it undefined
      const transformedJobs: DocumentItem[] = allItems.map(job => ({
        documentId: job.jobId as string,
        filename: (job.title as string) || (job.baseUrl as string),
        status: job.status as string,
        totalPages: job.totalUrls as number | undefined,
        processedCount: job.processedCount as number | undefined,
        failedCount: job.failedCount as number | undefined,
        createdAt: job.createdAt as string | undefined,
        updatedAt: undefined,
        type: 'scrape',
        baseUrl: job.baseUrl as string | undefined
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
        query: LIST_DOCUMENTS as unknown as string
      }) as GqlResponse;

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors fetching documents:', response.errors);
      }

      const { data } = response;
      const listResult = data?.listDocuments as { items?: Record<string, unknown>[] } | undefined;
      const newDocs: DocumentItem[] = (listResult?.items || []).map(doc => {
        const item = doc as Record<string, unknown>;
        // Use backend type with fallback to 'document'
        const backendType = item.type as string | undefined;
        const docType = (backendType === 'media' || backendType === 'image' || backendType === 'scrape')
          ? backendType
          : 'document';
        return {
          ...(item as unknown as DocumentItem),
          type: docType as 'document' | 'scrape' | 'image' | 'media',
        };
      });

      setDocuments(newDocs);

      // Also fetch scrape jobs and images
      await Promise.all([fetchScrapeJobs(), fetchImages()]);

    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
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
        query: GET_DOCUMENT as unknown as string,
        variables: { documentId }
      }) as GqlResponse;

      return response.data?.getDocument;
    } catch (err) {
      console.error('Failed to fetch document:', err);
      throw err;
    }
  }, []);

  // Handle real-time document update
  const handleDocumentUpdate = useCallback((update: DocumentUpdateEvent) => {
    setDocuments(prev => {
      const idx = prev.findIndex(d => d.documentId === update.documentId);
      if (idx >= 0) {
        // Update existing document
        const updated = [...prev];
        updated[idx] = { ...updated[idx], ...update, type: 'document' };
        return updated;
      }
      // New document - add to list
      return [{ ...update, type: 'document' } as DocumentItem, ...prev];
    });
  }, []);

  // Handle real-time scrape update
  const handleScrapeUpdate = useCallback((update: ScrapeUpdateEvent) => {
    setScrapeJobs(prev => {
      const idx = prev.findIndex(j => j.documentId === update.jobId);
      if (idx >= 0) {
        // Update existing job
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          status: update.status || updated[idx].status,
          totalPages: update.totalUrls,
          processedCount: update.processedCount,
          failedCount: update.failedCount,
          filename: update.title || update.baseUrl || updated[idx].filename,
          updatedAt: update.updatedAt
        };
        return updated;
      }
      // New job - add to list
      return [{
        documentId: update.jobId,
        filename: update.title || update.baseUrl || '',
        status: update.status || '',
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
  const handleImageUpdate = useCallback((update: ImageUpdateEvent) => {
    setImages(prev => {
      const idx = prev.findIndex(img => img.documentId === update.imageId);
      if (idx >= 0) {
        // Update existing image
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          status: update.status || updated[idx].status,
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
        filename: update.filename || '',
        status: update.status || '',
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
        query: deleteDocumentsMutation as unknown as string,
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

  // Reprocess a document by ID
  const reprocessDocument = useCallback(async (documentId: string) => {
    try {
      const response = await client.graphql({
        query: reprocessDocumentMutation as unknown as string,
        variables: { documentId }
      }) as GqlResponse;

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors reprocessing document:', response.errors);
        throw new Error(response.errors[0]?.message || 'Failed to reprocess document');
      }

      const result = response.data?.reprocessDocument as {
        documentId: string;
        type: string;
        status: string;
        executionArn?: string;
        error?: string;
      };

      if (result?.error) {
        throw new Error(result.error);
      }

      // Update local state to show processing status
      if (result) {
        const updateStatus = (prev: DocumentItem[]) =>
          prev.map(d =>
            d.documentId === documentId
              ? { ...d, status: result.status || 'PROCESSING' }
              : d
          );
        setDocuments(updateStatus);
        setScrapeJobs(updateStatus);
        setImages(updateStatus);
      }

      return result;
    } catch (err) {
      console.error('Failed to reprocess document:', err);
      throw err;
    }
  }, []);

  // Reindex a document by ID (re-extract metadata, skip OCR)
  const reindexDocument = useCallback(async (documentId: string) => {
    try {
      const response = await client.graphql({
        query: reindexDocumentMutation as unknown as string,
        variables: { documentId }
      }) as GqlResponse;

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors reindexing document:', response.errors);
        throw new Error(response.errors[0]?.message || 'Failed to reindex document');
      }

      const result = response.data?.reindexDocument as {
        documentId: string;
        type: string;
        status: string;
        executionArn?: string;
        error?: string;
      };

      if (result?.error) {
        throw new Error(result.error);
      }

      // Update local state to show processing status
      if (result) {
        const updateStatus = (prev: DocumentItem[]) =>
          prev.map(d =>
            d.documentId === documentId
              ? { ...d, status: result.status || 'PROCESSING' }
              : d
          );
        setDocuments(updateStatus);
        setScrapeJobs(updateStatus);
        setImages(updateStatus);
      }

      return result;
    } catch (err) {
      console.error('Failed to reindex document:', err);
      throw err;
    }
  }, []);

  useEffect(() => {
    // Initial fetch on mount
    fetchDocuments();

    // Set up subscriptions for real-time updates
    let docSubscription: { unsubscribe: () => void } | null = null;
    let scrapeSubscription: { unsubscribe: () => void } | null = null;
    let imageSubscription: { unsubscribe: () => void } | null = null;

    try {
      // Subscribe to document updates
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      docSubscription = (client.graphql({
        query: ON_DOCUMENT_UPDATE as unknown as string
      }) as any).subscribe({
        next: ({ data }: { data?: { onDocumentUpdate?: DocumentUpdateEvent } }) => {
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
        query: ON_SCRAPE_UPDATE as unknown as string
      }) as any).subscribe({
        next: ({ data }: { data?: { onScrapeUpdate?: ScrapeUpdateEvent } }) => {
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
        query: ON_IMAGE_UPDATE as unknown as string
      }) as any).subscribe({
        next: ({ data }: { data?: { onImageUpdate?: ImageUpdateEvent } }) => {
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

  // Merge and deduplicate by documentId with type precedence: media > image > scrape > document
  // Later sources (images, scrapeJobs) take precedence over earlier (documents) for same type
  // This ensures subscription updates override stale data from initial fetch
  const allItems = useMemo(() => {
    const typePriority: Record<string, number> = { media: 4, image: 3, scrape: 2, document: 1 };
    const itemMap = new Map<string, DocumentItem>();

    [...documents, ...scrapeJobs, ...images].forEach(item => {
      const existing = itemMap.get(item.documentId);
      if (!existing || typePriority[item.type] >= typePriority[existing.type]) {
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
    deleteDocuments,
    reprocessDocument,
    reindexDocument
  };
};
