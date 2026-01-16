/**
 * API Client
 * Handles all communication with the backend.
 */

// Use environment variable for API URL, fallback to /api for local dev with proxy
const API_BASE = import.meta.env.VITE_API_URL || '/api';

/**
 * Make a request to the API.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Get dashboard statistics.
 */
export async function getStats() {
  return request('/stats');
}

/**
 * Get current loading status.
 */
export async function getStatus() {
  return request('/status');
}

/**
 * Get markets with optional filters.
 */
export async function getMarkets({ category, minScore, minVolume, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (minScore) params.append('min_score', minScore);
  if (minVolume) params.append('min_volume', minVolume);
  if (limit) params.append('limit', limit);
  if (offset) params.append('offset', offset);
  
  const query = params.toString();
  return request(`/markets${query ? `?${query}` : ''}`);
}

/**
 * Get a single market by ID.
 */
export async function getMarket(marketId) {
  return request(`/markets/${marketId}`);
}

/**
 * Get edge opportunities with optional filters.
 */
export async function getOpportunities({ edgeType, minConfidence, riskLevel, limit } = {}) {
  const params = new URLSearchParams();
  if (edgeType) params.append('edge_type', edgeType);
  if (minConfidence) params.append('min_confidence', minConfidence);
  if (riskLevel) params.append('risk_level', riskLevel);
  if (limit) params.append('limit', limit);
  
  const query = params.toString();
  return request(`/opportunities${query ? `?${query}` : ''}`);
}

/**
 * Get research predictions.
 */
export async function getPredictions({ direction, minEdge, limit } = {}) {
  const params = new URLSearchParams();
  if (direction) params.append('direction', direction);
  if (minEdge) params.append('min_edge', minEdge);
  if (limit) params.append('limit', limit);
  
  const query = params.toString();
  return request(`/predictions${query ? `?${query}` : ''}`);
}

/**
 * Trigger a data refresh.
 */
export async function refreshData({ maxMarkets, minVolume, fetchOrderbooks } = {}) {
  const params = new URLSearchParams();
  if (maxMarkets) params.append('max_markets', maxMarkets);
  if (minVolume) params.append('min_volume', minVolume);
  if (fetchOrderbooks !== undefined) params.append('fetch_orderbooks', fetchOrderbooks);
  
  const query = params.toString();
  return request(`/refresh${query ? `?${query}` : ''}`, { method: 'POST' });
}

/**
 * Load demo data for testing.
 */
export async function loadDemoData() {
  return request('/load-demo', { method: 'POST' });
}
