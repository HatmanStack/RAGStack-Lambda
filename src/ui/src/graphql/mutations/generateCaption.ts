import gql from 'graphql-tag';

export const generateCaption = gql`
  mutation GenerateCaption($imageS3Uri: String!) {
    generateCaption(imageS3Uri: $imageS3Uri) {
      caption
      error
    }
  }
`;
