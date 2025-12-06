export const getScrapeJob = /* GraphQL */ `
  query GetScrapeJob($jobId: ID!) {
    getScrapeJob(jobId: $jobId) {
      job {
        jobId
        baseUrl
        title
        status
        config {
          maxPages
          maxDepth
          scope
        }
        totalUrls
        processedCount
        failedCount
        failedUrls
        createdAt
        updatedAt
      }
      pages {
        url
        title
        status
        documentId
        error
        depth
      }
    }
  }
`;
