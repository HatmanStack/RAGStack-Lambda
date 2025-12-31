export const queryKnowledgeBase = /* GraphQL */ `
  query QueryKnowledgeBase($query: String!, $sessionId: String) {
    queryKnowledgeBase(query: $query, sessionId: $sessionId) {
      answer
      sessionId
      error
      sources {
        documentId
        pageNumber
        s3Uri
        snippet
        documentUrl
        documentAccessAllowed
      }
    }
  }
`;
