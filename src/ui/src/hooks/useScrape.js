import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { startScrape as startScrapeMutation } from '../graphql/mutations/startScrape';
import { cancelScrape as cancelScrapeMutation } from '../graphql/mutations/cancelScrape';
import { getScrapeJob as getScrapeJobQuery } from '../graphql/queries/getScrapeJob';
import { listScrapeJobs as listScrapeJobsQuery } from '../graphql/queries/listScrapeJobs';
import { checkScrapeUrl as checkScrapeUrlQuery } from '../graphql/queries/checkScrapeUrl';

const client = generateClient();

export const useScrape = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);

  const startScrape = useCallback(async (input) => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.graphql({
        query: startScrapeMutation,
        variables: { input }
      });
      const job = response.data.startScrape;
      setJobs(prev => [job, ...prev]);
      return job;
    } catch (err) {
      setError(err.message || 'Failed to start scrape');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelScrape = useCallback(async (jobId) => {
    setLoading(true);
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
    try {
      const response = await client.graphql({
        query: listScrapeJobsQuery,
        variables: { limit }
      });
      setJobs(response.data.listScrapeJobs.items);
    } catch (err) {
      setError(err.message || 'Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchJobDetail = useCallback(async (jobId) => {
    setLoading(true);
    try {
      const response = await client.graphql({
        query: getScrapeJobQuery,
        variables: { jobId }
      });
      setSelectedJob(response.data.getScrapeJob);
      return response.data.getScrapeJob;
    } catch (err) {
      setError(err.message || 'Failed to fetch job detail');
    } finally {
      setLoading(false);
    }
  }, []);

  const checkDuplicate = useCallback(async (url) => {
    try {
      const response = await client.graphql({
        query: checkScrapeUrlQuery,
        variables: { url }
      });
      return response.data.checkScrapeUrl;
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
