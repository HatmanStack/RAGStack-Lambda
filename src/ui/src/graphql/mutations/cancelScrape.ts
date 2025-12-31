export const cancelScrape = /* GraphQL */ `
  mutation CancelScrape($jobId: ID!) {
    cancelScrape(jobId: $jobId) {
      jobId
      status
    }
  }
`;
