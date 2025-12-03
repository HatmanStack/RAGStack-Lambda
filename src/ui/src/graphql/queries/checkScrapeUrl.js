export const checkScrapeUrl = /* GraphQL */ `
  query CheckScrapeUrl($url: String!) {
    checkScrapeUrl(url: $url) {
      exists
      lastScrapedAt
      jobId
      title
    }
  }
`;
