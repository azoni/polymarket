/**
 * Custom Hooks
 * Reusable hooks for data fetching and state management.
 */

import { useState, useEffect, useCallback } from 'react';
import * as api from '../api/client';

/**
 * Hook for fetching data with loading and error states.
 */
export function useFetch(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    refetch();
  }, deps);

  return { data, loading, error, refetch };
}

/**
 * Hook for dashboard stats.
 */
export function useStats() {
  return useFetch(api.getStats, []);
}

/**
 * Hook for markets with filters.
 */
export function useMarkets(filters = {}) {
  const fetchFn = useCallback(() => api.getMarkets(filters), [JSON.stringify(filters)]);
  return useFetch(fetchFn, [JSON.stringify(filters)]);
}

/**
 * Hook for opportunities with filters.
 */
export function useOpportunities(filters = {}) {
  const fetchFn = useCallback(() => api.getOpportunities(filters), [JSON.stringify(filters)]);
  return useFetch(fetchFn, [JSON.stringify(filters)]);
}

/**
 * Hook for predictions.
 */
export function usePredictions(filters = {}) {
  const fetchFn = useCallback(() => api.getPredictions(filters), [JSON.stringify(filters)]);
  return useFetch(fetchFn, [JSON.stringify(filters)]);
}

/**
 * Hook for polling status during refresh.
 */
export function useRefreshStatus(isRefreshing) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (!isRefreshing) return;

    const interval = setInterval(async () => {
      try {
        const result = await api.getStatus();
        setStatus(result);
        if (!result.is_loading) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Status check failed:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isRefreshing]);

  return status;
}
