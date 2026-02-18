/**
 * API Client
 * Handles all communication with the backend.
 */

// Use environment variable for API URL, fallback to /api for local dev with proxy
const API_BASE = import.meta.env.VITE_API_URL || '/api';

console.log('[API] Base URL:', API_BASE);

/**
 * Make a request to the API.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  console.log(`[API] ${options.method || 'GET'} ${url}`);
  
  const startTime = Date.now();
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    const elapsed = Date.now() - startTime;

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error(`[API] Error ${response.status} (${elapsed}ms):`, error);
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }

    const data = await response.json();
    console.log(`[API] Success (${elapsed}ms):`, typeof data === 'object' ? `${Array.isArray(data) ? data.length + ' items' : 'object'}` : data);
    return data;
  } catch (err) {
    console.error(`[API] Request failed:`, err);
    throw err;
  }
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
export async function getMarkets({ category, minScore, minVolume, sortBy, search, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (minScore) params.append('min_score', minScore);
  if (minVolume) params.append('min_volume', minVolume);
  if (sortBy) params.append('sort_by', sortBy);
  if (search) params.append('search', search);
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
 * Get edges (opportunities + predictions) for a specific market.
 */
export async function getMarketEdges(marketId) {
  return request(`/markets/${marketId}/edges`);
}

/**
 * Get trading bot status (balance, risk, mode).
 */
export async function getTradingStatus() {
  return request('/trading/status');
}

/**
 * Get recent trade signals.
 */
export async function getTradingSignals() {
  return request('/trading/signals');
}

/**
 * Trigger a manual scan cycle.
 */
export async function triggerScan() {
  return request('/trading/scan', { method: 'POST' });
}

/**
 * Get trading bot config (non-secret fields).
 */
export async function getTradingConfig() {
  return request('/trading/config');
}

/**
 * Update trading bot config (partial update).
 */
export async function updateTradingConfig(updates) {
  return request('/trading/config', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

/**
 * Reset paper account balance and clear all trading state.
 */
export async function resetBalance() {
  return request('/trading/reset', { method: 'POST' });
}

export async function startAutoScan() {
  return request('/trading/auto-scan/start', { method: 'POST' });
}

export async function stopAutoScan() {
  return request('/trading/auto-scan/stop', { method: 'POST' });
}

export async function getPerformance() {
  return request('/trading/performance');
}

export async function getTradeHistory() {
  return request('/trading/trades');
}