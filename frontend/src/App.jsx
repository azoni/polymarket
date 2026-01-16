/**
 * Polymarket Edge Finder
 * Main application component.
 */

import { useState, useEffect, useCallback } from 'react';
import { StatCard, MarketCard, OpportunityCard, PredictionCard } from './components';
import * as api from './api/client';

// Tab options
const TABS = {
  MARKETS: 'markets',
  OPPORTUNITIES: 'opportunities',
  PREDICTIONS: 'predictions',
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
  const [error, setError] = useState(null);

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [statsData, marketsData, oppsData, predsData] = await Promise.all([
        api.getStats(),
        api.getMarkets({ limit: 50 }),
        api.getOpportunities({ limit: 50 }),
        api.getPredictions({ limit: 50 }),
      ]);
      
      setStats(statsData);
      setMarkets(marketsData);
      setOpportunities(oppsData);
      setPredictions(predsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Load demo data
  const handleLoadDemo = async () => {
    try {
      setLoading(true);
      await api.loadDemoData();
      await fetchData();
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  // Refresh from Polymarket
  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      setError(null);
      await api.refreshData({ maxMarkets: 100, minVolume: 1000 });
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await api.getStatus();
          if (!status.is_loading) {
            clearInterval(pollInterval);
            setRefreshing(false);
            await fetchData();
          }
        } catch (err) {
          clearInterval(pollInterval);
          setRefreshing(false);
          setError(err.message);
        }
      }, 2000);
    } catch (err) {
      setRefreshing(false);
      setError(err.message);
    }
  };

  // Format last updated time
  const formatTime = (dateStr) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleTimeString();
  };

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
            {refreshing ? (
              <>
                <span className="spinner" style={{ width: 16, height: 16 }} />
                Refreshing...
              </>
            ) : (
              'Refresh Data'
            )}
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
            {error}
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
        </div>

        {/* Loading State */}
        {loading && (
          <div className="loading">
            <div className="spinner" />
            Loading...
          </div>
        )}

        {/* Content */}
        {!loading && (
          <>
            {/* Markets Tab */}
            {activeTab === TABS.MARKETS && (
              <div>
                {markets.length === 0 ? (
                  <div className="empty-state">
                    <p>No markets loaded yet.</p>
                    <button className="btn btn-primary" onClick={handleLoadDemo}>
                      Load Demo Data
                    </button>
                  </div>
                ) : (
                  markets.map(market => (
                    <MarketCard key={market.market_id} market={market} />
                  ))
                )}
              </div>
            )}

            {/* Opportunities Tab */}
            {activeTab === TABS.OPPORTUNITIES && (
              <div>
                {opportunities.length === 0 ? (
                  <div className="empty-state">
                    <p>No opportunities detected yet.</p>
                    <p className="text-muted">Load data to detect edges.</p>
                  </div>
                ) : (
                  opportunities.map(opp => (
                    <OpportunityCard key={opp.id} opportunity={opp} />
                  ))
                )}
              </div>
            )}

            {/* Predictions Tab */}
            {activeTab === TABS.PREDICTIONS && (
              <div>
                {predictions.length === 0 ? (
                  <div className="empty-state">
                    <p>No predictions generated yet.</p>
                    <p className="text-muted">Load data to run research agents.</p>
                  </div>
                ) : (
                  predictions.map(pred => (
                    <PredictionCard key={pred.market_id} prediction={pred} />
                  ))
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}