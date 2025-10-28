export const getReEmbedJobStatus = `
  query GetReEmbedJobStatus {
    getReEmbedJobStatus {
      jobId
      status
      totalDocuments
      processedDocuments
      startTime
      completionTime
    }
  }
`;
