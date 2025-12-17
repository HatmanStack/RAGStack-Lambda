import gql from 'graphql-tag';

export const listImages = gql`
  query ListImages($limit: Int, $nextToken: String) {
    listImages(limit: $limit, nextToken: $nextToken) {
      items {
        imageId
        filename
        caption
        status
        s3Uri
        thumbnailUrl
        contentType
        fileSize
        createdAt
        updatedAt
      }
      nextToken
    }
  }
`;
