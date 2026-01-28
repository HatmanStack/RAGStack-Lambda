import gql from 'graphql-tag';

export const deleteMetadataKey = gql`
  mutation DeleteMetadataKey($keyName: String!) {
    deleteMetadataKey(keyName: $keyName) {
      success
      keyName
      error
    }
  }
`;
