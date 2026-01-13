import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { startScrape as startScrapeMutation } from '../graphql/mutations/startScrape';
import { cancelScrape as cancelScrapeMutation } from '../graphql/mutations/cancelScrape';
import { getScrapeJob as getScrapeJobQuery } from '../graphql/queries/getScrapeJob';
import { listScrapeJobs as listScrapeJobsQuery } from '../graphql/queries/listScrapeJobs';
import { checkScrapeUrl as checkScrapeUrlQuery } from '../graphql/queries/checkScrapeUrl';
import type { GqlResponse } from '../types/graphql';

export interface ScrapeJob {
  jobId: string;
  baseUrl?: string;
  title?: string;
  status: string;
  totalUrls?: number;
  processedCount?: number;
  failedCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

const client = generateClient();

export const useScrape = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ScrapeJob | null>(null);

  const startScrape = useCallback(async (input: Record<string, unknown>) => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.graphql({
        query: startScrapeMutation,
        variables: { input }
      }) as GqlResponse;

      // Check for GraphQL errors in the response
      if (response.errors && response.errors.length > 0) {
        const errorDetails = response.errors.map(e => e.message).join('; ');
        console.error('[useScrape] GraphQL errors:', response.errors);
        throw new Error(errorDetails);
      }

      const job = response.data?.startScrape as ScrapeJob | undefined;
      if (!job) {
        console.error('[useScrape] No job returned in response');
        throw new Error('No job data returned from server');
      }

      setJobs(prev => [job, ...prev]);
      return job;
    } catch (err) {
      // Log full error details
      console.error('[useScrape] Error starting scrape:', err);
      const typedErr = err as { message?: string; errors?: Array<{ message: string }>; data?: unknown; stack?: string };
      console.error('[useScrape] Error details:', {
        message: typedErr.message,
        errors: typedErr.errors,
        data: typedErr.data,
        stack: typedErr.stack
      });

      // Extract the most useful error message
      let errorMessage = 'Failed to start scrape';
      if (typedErr.errors && typedErr.errors.length > 0) {
        errorMessage = typedErr.errors.map(e => e.message).join('; ');
      } else if (typedErr.message) {
        errorMessage = typedErr.message;
      }

      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelScrape = useCallback(async (jobId: string) => {
    setLoading(true);
    setError(null);
    try {
      await client.graphql({
        query: cancelScrapeMutation,
        variables: { jobId }
      });
      setJobs(prev => prev.map(j =>
        j.jobId === jobId ? { ...j, status: 'CANCELLED' } : j
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel scrape');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchJobs = useCallback(async (limit = 20) => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.graphql({
        query: listScrapeJobsQuery,
        variables: { limit }
      }) as GqlResponse;
      const listResult = response.data?.listScrapeJobs as { items?: ScrapeJob[] } | undefined;
      setJobs(listResult?.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchJobDetail = useCallback(async (jobId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.graphql({
        query: getScrapeJobQuery,
        variables: { jobId }
      }) as GqlResponse;
      const job = response.data?.getScrapeJob as ScrapeJob | undefined;
      setSelectedJob(job || null);
      return job;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job detail');
    } finally {
      setLoading(false);
    }
  }, []);

  const checkDuplicate = useCallback(async (url: string) => {
    try {
      const response = await client.graphql({
        query: checkScrapeUrlQuery,
        variables: { url }
      }) as GqlResponse;
      return response.data?.checkScrapeUrl;
    } catch {
      return null; // Ignore errors, proceed with scrape
    }
  }, []);

  return {
    loading,
    error,
    jobs,
    selectedJob,
    startScrape,
    cancelScrape,
    fetchJobs,
    fetchJobDetail,
    checkDuplicate,
    clearError: () => setError(null)
  };
};
