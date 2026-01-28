import gql from 'graphql-tag';

export const regenerateFilterExamples = gql`
  mutation RegenerateFilterExamples {
    regenerateFilterExamples {
      success
      examplesGenerated
      executionTimeMs
      error
    }
  }
`;
