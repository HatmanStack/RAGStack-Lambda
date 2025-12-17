import gql from 'graphql-tag';

export const getImage = gql`
  query GetImage($imageId: ID!) {
    getImage(imageId: $imageId) {
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
