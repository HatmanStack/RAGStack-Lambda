import { useState, useEffect, useCallback, useRef } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';

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
    }
  }
`;

const client = generateClient();

export const useDocuments = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nextToken, setNextToken] = useState(null);

  // Use ref to track the current nextToken without causing re-renders
  const nextTokenRef = useRef(null);

  // Update ref whenever nextToken changes
  useEffect(() => {
    nextTokenRef.current = nextToken;
  }, [nextToken]);

  const fetchDocuments = useCallback(async (reset = false) => {
    setLoading(true);
    setError(null);

    try {
      const { data } = await client.graphql({
        query: LIST_DOCUMENTS,
        variables: {
          limit: 50,
          nextToken: reset ? null : nextTokenRef.current
        }
      });

      const newDocs = data.listDocuments.items;

      setDocuments(prev => reset ? newDocs : [...prev, ...newDocs]);
      setNextToken(data.listDocuments.nextToken);

    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []); // Empty deps - uses ref for nextToken

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

  useEffect(() => {
    // Initial fetch on mount
    fetchDocuments(true);

    // Poll for updates every 30 seconds
    const interval = setInterval(() => {
      fetchDocuments(true);
    }, 30000);

    return () => clearInterval(interval);
    // Empty deps - only run once on mount, functions are stable
  }, []);

  return {
    documents,
    loading,
    error,
    hasMore: !!nextToken,
    fetchDocuments,
    refreshDocuments,
    fetchDocument
  };
};
