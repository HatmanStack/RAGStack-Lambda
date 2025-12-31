import gql from 'graphql-tag';

export const createZipUploadUrl = gql`
  mutation CreateZipUploadUrl($generateCaptions: Boolean) {
    createZipUploadUrl(generateCaptions: $generateCaptions) {
      uploadUrl
      uploadId
      fields
    }
  }
`;
