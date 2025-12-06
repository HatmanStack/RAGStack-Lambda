export const startScrape = /* GraphQL */ `
  mutation StartScrape($input: StartScrapeInput!) {
    startScrape(input: $input) {
      jobId
      baseUrl
      title
      status
      createdAt
    }
  }
`;
