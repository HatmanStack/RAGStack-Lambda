import gql from 'graphql-tag';

export const reindexDocument = gql`
  mutation ReindexDocument($documentId: ID!) {
    reindexDocument(documentId: $documentId) {
      documentId
      type
      status
      executionArn
      error
    }
  }
`;
