import gql from 'graphql-tag';

export const startReindex = gql`
  mutation StartReindex {
    startReindex {
      executionArn
      status
      startedAt
    }
  }
`;
