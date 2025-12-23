import gql from 'graphql-tag';

export const createImageUploadUrl = gql`
  mutation CreateImageUploadUrl($filename: String!, $autoProcess: Boolean, $caption: String) {
    createImageUploadUrl(filename: $filename, autoProcess: $autoProcess, caption: $caption) {
      uploadUrl
      imageId
      s3Uri
      fields
    }
  }
`;
