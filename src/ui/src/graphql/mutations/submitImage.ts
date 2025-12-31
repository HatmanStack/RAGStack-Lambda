import gql from 'graphql-tag';

export const submitImage = gql`
  mutation SubmitImage($input: SubmitImageInput!) {
    submitImage(input: $input) {
      imageId
      filename
      caption
      userCaption
      aiCaption
      status
      s3Uri
      thumbnailUrl
      contentType
      fileSize
      errorMessage
      createdAt
      updatedAt
    }
  }
`;
