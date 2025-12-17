import gql from 'graphql-tag';

export const createImageUploadUrl = gql`
  mutation CreateImageUploadUrl($filename: String!) {
    createImageUploadUrl(filename: $filename) {
      uploadUrl
      imageId
      fields
    }
  }
`;
