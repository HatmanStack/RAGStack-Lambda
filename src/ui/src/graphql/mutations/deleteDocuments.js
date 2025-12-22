import gql from 'graphql-tag';

export const deleteDocuments = gql`
  mutation DeleteDocuments($documentIds: [ID!]!) {
    deleteDocuments(documentIds: $documentIds) {
      deletedCount
      failedIds
      errors
    }
  }
`;
