export const searchKnowledgeBase = /* GraphQL */ `
  query SearchKnowledgeBase($query: String!, $maxResults: Int) {
    searchKnowledgeBase(query: $query, maxResults: $maxResults) {
      query
      total
      error
      results {
        content
        source
        score
      }
    }
  }
`;
