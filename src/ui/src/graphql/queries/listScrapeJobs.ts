import gql from 'graphql-tag';

export const listScrapeJobs = gql`
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
