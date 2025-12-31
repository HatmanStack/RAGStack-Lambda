import gql from 'graphql-tag';

export const deleteImage = gql`
  mutation DeleteImage($imageId: ID!) {
    deleteImage(imageId: $imageId)
  }
`;
