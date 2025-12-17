import { useState, useEffect, useCallback, useRef } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import { listScrapeJobs } from '../graphql/queries/listScrapeJobs';
import { listImages } from '../graphql/queries/listImages';

const LIST_DOCUMENTS = gql`
  query ListDocuments($limit: Int, $nextToken: String) {
    listDocuments(limit: $limit, nextToken: $nextToken) {
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
      nextToken
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

const client = generateClient();

export const useDocuments = () => {
  const [documents, setDocuments] = useState([]);
  const [scrapeJobs, setScrapeJobs] = useState([]);
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nextToken, setNextToken] = useState(null);

  // Use ref to track the current nextToken without causing re-renders
  const nextTokenRef = useRef(null);

  // Update ref whenever nextToken changes
  useEffect(() => {
    nextTokenRef.current = nextToken;
  }, [nextToken]);

  const fetchImages = useCallback(async () => {
    try {
      const response = await client.graphql({
        query: listImages,
        variables: { limit: 50 }
      });

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors fetching images:', response.errors);
        return;
      }

      const { data } = response;
      const items = data?.listImages?.items || [];

      // Transform images to match document structure for unified display
      const transformedImages = items.map(img => ({
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
      const response = await client.graphql({
        query: listScrapeJobs,
        variables: { limit: 50 }
      });

      // Check for errors in response
      if (response.errors) {
        console.error('[useDocuments] GraphQL errors fetching scrape jobs:', response.errors);
        return;
      }

      const { data } = response;
      const items = data?.listScrapeJobs?.items || [];

      // Transform scrape jobs to match document structure for unified display
      const transformedJobs = items.map(job => ({
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

  const fetchDocuments = useCallback(async (reset = false) => {
    setLoading(true);
    setError(null);

    try {
      const response = await client.graphql({
        query: LIST_DOCUMENTS,
        variables: {
          limit: 50,
          nextToken: reset ? null : nextTokenRef.current
        }
      });

      if (response.errors) {
        console.error('[useDocuments] GraphQL errors fetching documents:', response.errors);
      }

      const { data } = response;
      const newDocs = (data?.listDocuments?.items || []).map(doc => ({
        ...doc,
        type: 'document'
      }));

      setDocuments(prev => reset ? newDocs : [...prev, ...newDocs]);
      setNextToken(data?.listDocuments?.nextToken);

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
    fetchDocuments(true);
  }, [fetchDocuments]);

  const fetchDocument = useCallback(async (documentId) => {
    try {
      const { data } = await client.graphql({
        query: GET_DOCUMENT,
        variables: { documentId }
      });

      return data.getDocument;
    } catch (err) {
      console.error('Failed to fetch document:', err);
      throw err;
    }
  }, []);

  // Handle real-time document update
  const handleDocumentUpdate = useCallback((update) => {
    console.log('[useDocuments] Document update received:', update);
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
    console.log('[useDocuments] Scrape update received:', update);
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

  useEffect(() => {
    // Initial fetch on mount
    fetchDocuments(true);

    // Set up subscriptions for real-time updates
    let docSubscription = null;
    let scrapeSubscription = null;

    try {
      // Subscribe to document updates
      docSubscription = client.graphql({
        query: ON_DOCUMENT_UPDATE
      }).subscribe({
        next: ({ data }) => {
          if (data?.onDocumentUpdate) {
            handleDocumentUpdate(data.onDocumentUpdate);
          }
        },
        error: (err) => {
          console.error('[useDocuments] Document subscription error:', err);
        }
      });

      // Subscribe to scrape updates
      scrapeSubscription = client.graphql({
        query: ON_SCRAPE_UPDATE
      }).subscribe({
        next: ({ data }) => {
          if (data?.onScrapeUpdate) {
            handleScrapeUpdate(data.onScrapeUpdate);
          }
        },
        error: (err) => {
          console.error('[useDocuments] Scrape subscription error:', err);
        }
      });

      console.log('[useDocuments] Subscriptions established');
    } catch (err) {
      console.error('[useDocuments] Failed to set up subscriptions:', err);
    }

    // Fallback: poll every 2 minutes in case subscriptions fail
    const interval = setInterval(() => {
      fetchDocuments(true);
    }, 120000);

    return () => {
      clearInterval(interval);
      if (docSubscription) docSubscription.unsubscribe();
      if (scrapeSubscription) scrapeSubscription.unsubscribe();
    };
  }, [fetchDocuments, handleDocumentUpdate, handleScrapeUpdate]);

  // Merge documents, scrape jobs, and images, sorted by createdAt (guard against missing dates)
  const allItems = [...documents, ...scrapeJobs, ...images].sort((a, b) => {
    const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
    const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
    return dateB - dateA;
  });

  return {
    documents: allItems,
    loading,
    error,
    hasMore: !!nextToken,
    fetchDocuments,
    refreshDocuments,
    fetchDocument
  };
};
