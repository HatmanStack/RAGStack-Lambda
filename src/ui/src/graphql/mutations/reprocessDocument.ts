import gql from 'graphql-tag';

export const reprocessDocument = gql`
  mutation ReprocessDocument($documentId: ID!) {
    reprocessDocument(documentId: $documentId) {
      documentId
      type
      status
      executionArn
      error
    }
  }
`;
