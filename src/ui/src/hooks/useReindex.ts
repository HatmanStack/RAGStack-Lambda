import { useState, useEffect, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';
import { startReindex as startReindexMutation } from '../graphql/mutations/startReindex';
import type { ReindexStatus, ReindexProgress, ReindexJob, ReindexUpdate } from '../types/graphql';

// Type helper for GraphQL responses
type GqlResponse<T = Record<string, unknown>> = { data?: T; errors?: Array<{ message: string }> };

// Subscription for real-time reindex updates (defined inline per useDocuments.ts pattern)
const ON_REINDEX_UPDATE = gql`
  subscription OnReindexUpdate {
    onReindexUpdate {
      status
      totalDocuments
      processedCount
      currentDocument
      errorCount
      errorMessages
      newKnowledgeBaseId
      updatedAt
    }
  }
`;

const client = generateClient();

// Statuses that indicate reindex is in progress
const IN_PROGRESS_STATUSES: ReindexStatus[] = ['PENDING', 'CREATING_KB', 'PROCESSING', 'DELETING_OLD_KB'];

export function useReindex() {
  const [status, setStatus] = useState<ReindexStatus | null>(null);
  const [progress, setProgress] = useState<ReindexProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [newKnowledgeBaseId, setNewKnowledgeBaseId] = useState<string | null>(null);

  // Handle reindex update from subscription
  const handleReindexUpdate = useCallback((update: ReindexUpdate) => {
    setStatus(update.status);

    // Calculate progress percentage
    const percentComplete = update.totalDocuments > 0
      ? Math.round((update.processedCount / update.totalDocuments) * 100)
      : 0;

    setProgress({
      totalDocuments: update.totalDocuments,
      processedCount: update.processedCount,
      currentDocument: update.currentDocument,
      errorCount: update.errorCount,
      errorMessages: update.errorMessages,
      percentComplete,
    });

    // Handle error status
    if (update.status === 'FAILED' && update.errorMessages.length > 0) {
      setError(update.errorMessages[0]);
    }

    // Store new KB ID on completion
    if (update.newKnowledgeBaseId) {
      setNewKnowledgeBaseId(update.newKnowledgeBaseId);
    }
  }, []);

  // Start reindex operation
  const startReindex = useCallback(async (): Promise<ReindexJob | null> => {
    setIsStarting(true);
    setError(null);
    setProgress(null);

    try {
      const response = await client.graphql({
        query: startReindexMutation as unknown as string,
      }) as GqlResponse<{ startReindex: ReindexJob }>;

      if (response.errors?.length) {
        throw new Error(response.errors[0].message);
      }

      const job = response.data?.startReindex;
      if (job) {
        setStatus(job.status);
        return job;
      }

      return null;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start reindex';
      setError(message);
      console.error('[useReindex] Start reindex error:', err);
      return null;
    } finally {
      setIsStarting(false);
    }
  }, []);

  // Clear state (for dismissing completed/failed status)
  const clearState = useCallback(() => {
    setStatus(null);
    setProgress(null);
    setError(null);
    setNewKnowledgeBaseId(null);
  }, []);

  // Set up subscription listener
  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null;

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      subscription = (client.graphql({
        query: ON_REINDEX_UPDATE as unknown as string,
      }) as any).subscribe({
        next: ({ data }: { data?: { onReindexUpdate?: ReindexUpdate } }) => {
          if (data?.onReindexUpdate) {
            handleReindexUpdate(data.onReindexUpdate);
          }
        },
        error: (err: Error) => {
          console.error('[useReindex] Subscription error:', err);
        },
      });
    } catch (err) {
      console.error('[useReindex] Failed to set up subscription:', err);
    }

    // Cleanup subscription on unmount
    return () => {
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, [handleReindexUpdate]);

  // Compute isInProgress from status
  const isInProgress = status !== null && IN_PROGRESS_STATUSES.includes(status);

  return {
    status,
    progress,
    error,
    isStarting,
    isInProgress,
    newKnowledgeBaseId,
    startReindex,
    clearState,
  };
}
