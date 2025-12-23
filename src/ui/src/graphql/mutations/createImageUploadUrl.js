import gql from 'graphql-tag';

export const createImageUploadUrl = gql`
  mutation CreateImageUploadUrl($filename: String!, $autoProcess: Boolean, $userCaption: String) {
    createImageUploadUrl(filename: $filename, autoProcess: $autoProcess, userCaption: $userCaption) {
      uploadUrl
      imageId
      s3Uri
      fields
    }
  }
`;
