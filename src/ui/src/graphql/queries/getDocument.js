export const getDocument = /* GraphQL */ `
  query GetDocument($documentId: ID!) {
    getDocument(documentId: $documentId) {
      documentId
      filename
      status
      outputS3Uri
      previewUrl
      totalPages
      errorMessage
    }
  }
`;
