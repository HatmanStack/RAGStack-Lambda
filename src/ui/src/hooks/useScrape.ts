import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { startScrape as startScrapeMutation } from '../graphql/mutations/startScrape';
import { cancelScrape as cancelScrapeMutation } from '../graphql/mutations/cancelScrape';
import { getScrapeJob as getScrapeJobQuery } from '../graphql/queries/getScrapeJob';
import { listScrapeJobs as listScrapeJobsQuery } from '../graphql/queries/listScrapeJobs';
import { checkScrapeUrl as checkScrapeUrlQuery } from '../graphql/queries/checkScrapeUrl';
import type { GqlResponse } from '../types/graphql';

const client = generateClient();

export const useScrape = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);

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

      const job = response.data?.startScrape;
      if (!job) {
        console.error('[useScrape] No job returned in response');
        throw new Error('No job data returned from server');
      }

      setJobs(prev => [job, ...prev]);
      return job;
    } catch (err) {
      // Log full error details
      console.error('[useScrape] Error starting scrape:', err);
      console.error('[useScrape] Error details:', {
        message: err.message,
        errors: err.errors,
        data: err.data,
        stack: err.stack
      });

      // Extract the most useful error message
      let errorMessage = 'Failed to start scrape';
      if (err.errors && err.errors.length > 0) {
        errorMessage = err.errors.map(e => e.message).join('; ');
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelScrape = useCallback(async (jobId) => {
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
      setError(err.message || 'Failed to cancel scrape');
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
      const listResult = response.data?.listScrapeJobs as { items?: unknown[] } | undefined;
      setJobs(listResult?.items || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch jobs');
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
      setSelectedJob(response.data?.getScrapeJob);
      return response.data?.getScrapeJob;
    } catch (err) {
      setError(err.message || 'Failed to fetch job detail');
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
