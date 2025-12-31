export const listScrapeJobs = /* GraphQL */ `
  query ListScrapeJobs($limit: Int, $nextToken: String) {
    listScrapeJobs(limit: $limit, nextToken: $nextToken) {
      items {
        jobId
        baseUrl
        title
        status
        totalUrls
        processedCount
        failedCount
        createdAt
      }
      nextToken
    }
  }
`;
