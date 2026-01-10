/**
 * Type helpers for AWS Amplify GraphQL responses.
 *
 * Amplify's client.graphql() returns a union type that includes subscriptions,
 * making it awkward to access .data and .errors on query/mutation responses.
 * These types provide cleaner access patterns.
 */

/**
 * Standard GraphQL response shape for queries and mutations.
 */
export type GqlResponse<T = Record<string, unknown>> = {
  data?: T;
  errors?: Array<{ message: string }>;
};

// Reindex status enum (matches backend schema)
export type ReindexStatus =
  | 'PENDING'
  | 'CREATING_KB'
  | 'PROCESSING'
  | 'DELETING_OLD_KB'
  | 'COMPLETED'
  | 'FAILED';

// Reindex progress from subscription
export interface ReindexUpdate {
  status: ReindexStatus;
  totalDocuments: number;
  processedCount: number;
  currentDocument: string | null;
  errorCount: number;
  errorMessages: string[];
  newKnowledgeBaseId: string | null;
  updatedAt: string;
}

// Reindex job response from mutation
export interface ReindexJob {
  executionArn: string;
  status: ReindexStatus;
  startedAt: string;
}

// Progress state for UI display
export interface ReindexProgress {
  totalDocuments: number;
  processedCount: number;
  currentDocument: string | null;
  errorCount: number;
  errorMessages: string[];
  percentComplete: number;
}
