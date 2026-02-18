/**
 * Polymarket Edge Finder
 * Main application component.
 */

import { useState, useEffect, useCallback } from 'react';
import { StatCard, MarketCard, OpportunityCard, PredictionCard, TradingTab } from './components';
import * as api from './api/client';

// Tab options
const TABS = {
  MARKETS: 'markets',
  OPPORTUNITIES: 'opportunities',
  PREDICTIONS: 'predictions',
  TRADING: 'trading',
};

export default function App() {
  // State
  const [activeTab, setActiveTab] = useState(TABS.MARKETS);
  const [stats, setStats] = useState(null);
  const [markets, setMarkets] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState('');
  const [error, setError] = useState(null);

  // Trading state
  const [tradingStatus, setTradingStatus] = useState(null);
  const [tradingSignals, setTradingSignals] = useState([]);
  const [scanning, setScanning] = useState(false);

  // Fetch trading data
  const fetchTradingData = useCallback(async () => {
    try {
      const [status, signals] = await Promise.all([
        api.getTradingStatus(),
        api.getTradingSignals(),
      ]);
      setTradingStatus(status);
      setTradingSignals(signals);
    } catch (err) {
      console.error('[fetchTradingData] Error:', err);
    }
  }, []);

  // Handle scan trigger
  const handleScan = async () => {
    try {
      setScanning(true);
      setError(null);
      await api.triggerScan();
      await fetchTradingData();
    } catch (err) {
      console.error('[handleScan] Error:', err);
      setError(err.message);
    } finally {
      setScanning(false);
    }
  };

  // Fetch all data
  const fetchData = useCallback(async () => {
    console.log('[fetchData] Starting data fetch...');
    try {
      setLoading(true);
      setError(null);
      
      const [statsData, marketsData, oppsData, predsData] = await Promise.all([
        api.getStats(),
        api.getMarkets({ limit: 50 }),
        api.getOpportunities({ limit: 50 }),
        api.getPredictions({ limit: 50 }),
      ]);
      
      console.log('[fetchData] Results:', {
        stats: statsData,
        markets: marketsData.length,
        opportunities: oppsData.length,
        predictions: predsData.length
      });
      
      setStats(statsData);
      setMarkets(marketsData);
      setOpportunities(oppsData);
      setPredictions(predsData);
    } catch (err) {
      console.error('[fetchData] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData();
    fetchTradingData();
  }, [fetchData, fetchTradingData]);

  // Load demo data
  const handleLoadDemo = async () => {
    console.log('[handleLoadDemo] Loading demo data...');
    try {
      setLoading(true);
      setError(null);
      const result = await api.loadDemoData();
      console.log('[handleLoadDemo] Result:', result);
      await fetchData();
    } catch (err) {
      console.error('[handleLoadDemo] Error:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  // Refresh from Polymarket
  const handleRefresh = async () => {
    console.log('[handleRefresh] Starting refresh...');
    try {
      setRefreshing(true);
      setRefreshStatus('Starting refresh...');
      setError(null);
      
      const result = await api.refreshData({ maxMarkets: 100, minVolume: 1000 });
      console.log('[handleRefresh] Refresh started:', result);
      setRefreshStatus('Fetching markets from Polymarket...');
      
      // Poll for completion
      let pollCount = 0;
      const maxPolls = 60; // 2 minutes max
      
      const pollInterval = setInterval(async () => {
        pollCount++;
        try {
          const status = await api.getStatus();
          console.log(`[handleRefresh] Poll ${pollCount}:`, status);
          
          if (status.markets_loaded > 0) {
            setRefreshStatus(`Processing ${status.markets_loaded} markets...`);
          }
          
          if (!status.is_loading) {
            console.log('[handleRefresh] Refresh complete');
            clearInterval(pollInterval);
            setRefreshing(false);
            setRefreshStatus('');
            await fetchData();
          } else if (pollCount >= maxPolls) {
            console.warn('[handleRefresh] Polling timeout');
            clearInterval(pollInterval);
            setRefreshing(false);
            setRefreshStatus('');
            setError('Refresh timed out. Check server logs.');
            await fetchData();
          }
        } catch (err) {
          console.error('[handleRefresh] Poll error:', err);
          clearInterval(pollInterval);
          setRefreshing(false);
          setRefreshStatus('');
          setError(err.message);
        }
      }, 2000);
    } catch (err) {
      console.error('[handleRefresh] Error:', err);
      setRefreshing(false);
      setRefreshStatus('');
      setError(err.message);
    }
  };

  // Format last updated time
  const formatTime = (dateStr) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleTimeString();
  };

  // Check if we have data
  const hasData = markets.length > 0 || opportunities.length > 0 || predictions.length > 0;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>Polymarket Edge Finder</h1>
        <div className="flex gap-sm">
          <button 
            className="btn btn-secondary" 
            onClick={handleLoadDemo}
            disabled={loading || refreshing}
          >
            Load Demo
          </button>
          <button 
            className="btn btn-primary" 
            onClick={handleRefresh}
            disabled={loading || refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh Data'}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="main">
        {/* Error Banner */}
        {error && (
          <div style={{ 
            background: 'rgba(239, 68, 68, 0.1)', 
            border: '1px solid var(--accent-red)',
            padding: 'var(--spacing-md)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--spacing-md)',
            color: 'var(--accent-red)'
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Refresh Status Banner */}
        {refreshing && refreshStatus && (
          <div style={{ 
            background: 'rgba(59, 130, 246, 0.1)', 
            border: '1px solid var(--accent-blue)',
            padding: 'var(--spacing-md)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--spacing-md)',
            color: 'var(--accent-blue)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--spacing-sm)'
          }}>
            <div className="spinner" style={{ width: 16, height: 16 }} />
            {refreshStatus}
          </div>
        )}

        {/* Stats Grid */}
        <div className="stats-grid">
          <StatCard 
            label="Total Markets" 
            value={stats?.total_markets || 0} 
            color="blue" 
          />
          <StatCard 
            label="Opportunities" 
            value={stats?.total_opportunities || 0} 
            color="green" 
          />
          <StatCard 
            label="High Confidence" 
            value={stats?.high_confidence_opps || 0} 
            color="yellow" 
          />
          <StatCard 
            label="Predictions" 
            value={stats?.total_predictions || 0} 
            color="purple" 
          />
        </div>

        {/* Last Updated */}
        {stats?.last_updated && (
          <div className="text-muted mb-md" style={{ fontSize: '0.875rem' }}>
            Last updated: {formatTime(stats.last_updated)}
          </div>
        )}

        {/* Tabs */}
        <div className="tabs">
          <button 
            className={`tab ${activeTab === TABS.MARKETS ? 'active' : ''}`}
            onClick={() => setActiveTab(TABS.MARKETS)}
          >
            Markets ({markets.length})
          </button>
          <button 
            className={`tab ${activeTab === TABS.OPPORTUNITIES ? 'active' : ''}`}
            onClick={() => setActiveTab(TABS.OPPORTUNITIES)}
          >
            Opportunities ({opportunities.length})
          </button>
          <button
            className={`tab ${activeTab === TABS.PREDICTIONS ? 'active' : ''}`}
            onClick={() => setActiveTab(TABS.PREDICTIONS)}
          >
            Predictions ({predictions.length})
          </button>
          <button
            className={`tab ${activeTab === TABS.TRADING ? 'active' : ''}`}
            onClick={() => { setActiveTab(TABS.TRADING); fetchTradingData(); }}
          >
            Trading
          </button>
        </div>

        {/* Loading State */}
        {loading && !refreshing && (
          <div className="loading">
            <div className="spinner" />
            Loading data...
          </div>
        )}

        {/* Content */}
        {!loading && (
          <>
            {/* Empty State - No Data At All */}
            {!hasData && !error && (
              <div className="empty-state">
                <h3 style={{ marginBottom: 'var(--spacing-sm)' }}>No data loaded</h3>
                <p style={{ marginBottom: 'var(--spacing-md)', color: 'var(--text-secondary)' }}>
                  Click "Refresh Data" to fetch live markets from Polymarket, or "Load Demo" to test the interface.
                </p>
                <div className="flex gap-sm" style={{ justifyContent: 'center' }}>
                  <button className="btn btn-secondary" onClick={handleLoadDemo}>
                    Load Demo
                  </button>
                  <button className="btn btn-primary" onClick={handleRefresh}>
                    Refresh Data
                  </button>
                </div>
              </div>
            )}

            {/* Markets Tab */}
            {hasData && activeTab === TABS.MARKETS && (
              <div>
                {markets.length === 0 ? (
                  <div className="empty-state">
                    <p>No markets found.</p>
                    <p className="text-muted">Try adjusting filters or refreshing data.</p>
                  </div>
                ) : (
                  markets.map(market => (
                    <MarketCard key={market.market_id} market={market} />
                  ))
                )}
              </div>
            )}

            {/* Opportunities Tab */}
            {hasData && activeTab === TABS.OPPORTUNITIES && (
              <div>
                {opportunities.length === 0 ? (
                  <div className="empty-state">
                    <p>No opportunities detected.</p>
                    <p className="text-muted">Edge detection runs automatically when data is refreshed.</p>
                  </div>
                ) : (
                  opportunities.map(opp => (
                    <OpportunityCard key={opp.id} opportunity={opp} />
                  ))
                )}
              </div>
            )}

            {/* Predictions Tab */}
            {hasData && activeTab === TABS.PREDICTIONS && (
              <div>
                {predictions.length === 0 ? (
                  <div className="empty-state">
                    <p>No predictions generated.</p>
                    <p className="text-muted">Research agents analyze top markets during refresh.</p>
                  </div>
                ) : (
                  predictions.map(pred => (
                    <PredictionCard key={pred.market_id} prediction={pred} />
                  ))
                )}
              </div>
            )}

            {/* Trading Tab */}
            {activeTab === TABS.TRADING && (
              <TradingTab
                status={tradingStatus}
                signals={tradingSignals}
                scanning={scanning}
                onScan={handleScan}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}