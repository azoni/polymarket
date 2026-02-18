/**
 * Polymarket Trading Platform
 * Main application component.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { StatCard, TradingTab, DashboardTab, ScannerTab } from './components';
import * as api from './api/client';

const TABS = {
  DASHBOARD: 'dashboard',
  SCANNER: 'scanner',
  TRADING: 'trading',
};

export default function App() {
  // State
  const [activeTab, setActiveTab] = useState(TABS.DASHBOARD);
  const [stats, setStats] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState('');
  const [error, setError] = useState(null);

  // Trading state
  const [tradingStatus, setTradingStatus] = useState(null);
  const [tradingSignals, setTradingSignals] = useState([]);
  const [tradingConfig, setTradingConfig] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [autoScanning, setAutoScanning] = useState(false);

  // Toast notifications
  const [toasts, setToasts] = useState([]);
  const toastIdRef = useRef(0);

  // Auto-refresh interval ref
  const autoRefreshRef = useRef(null);

  const addToast = useCallback((message, type = 'info') => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  // Fetch trading data
  const fetchTradingData = useCallback(async () => {
    try {
      const [status, signals, config] = await Promise.all([
        api.getTradingStatus(),
        api.getTradingSignals(),
        api.getTradingConfig(),
      ]);
      setTradingStatus(status);
      setTradingSignals(signals);
      setTradingConfig(config);
      setAutoScanning(status?.auto_scan || false);
    } catch (err) {
      console.error('[fetchTradingData] Error:', err);
    }
  }, []);

  // Handle config change from Trading settings
  const handleConfigChange = async (updates) => {
    try {
      const updated = await api.updateTradingConfig(updates);
      setTradingConfig(updated);
      const status = await api.getTradingStatus();
      setTradingStatus(status);
      addToast('Settings saved', 'success');
    } catch (err) {
      console.error('[handleConfigChange] Error:', err);
      addToast(err.message, 'error');
    }
  };

  // Handle scan trigger
  const handleScan = async () => {
    try {
      setScanning(true);
      setError(null);
      await api.triggerScan();
      await fetchTradingData();
      addToast('Scan complete', 'success');
    } catch (err) {
      console.error('[handleScan] Error:', err);
      addToast(err.message, 'error');
    } finally {
      setScanning(false);
    }
  };

  // Handle balance reset
  const handleReset = async () => {
    try {
      setError(null);
      await api.resetBalance();
      await fetchTradingData();
      addToast('Balance reset to $10,000', 'info');
    } catch (err) {
      console.error('[handleReset] Error:', err);
      addToast(err.message, 'error');
    }
  };

  // Handle auto-scan toggle
  const handleAutoScanToggle = async () => {
    try {
      if (autoScanning) {
        await api.stopAutoScan();
        setAutoScanning(false);
        addToast('Auto-scan stopped', 'info');
      } else {
        await api.startAutoScan();
        setAutoScanning(true);
        addToast('Auto-scan started', 'success');
      }
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  // Fetch core data (stats, opportunities, predictions)
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [statsData, oppsData, predsData] = await Promise.all([
        api.getStats(),
        api.getOpportunities({ limit: 200 }),
        api.getPredictions({ limit: 200 }),
      ]);

      setStats(statsData);
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

  // Auto-refresh every 15 seconds on Dashboard or Trading tabs
  useEffect(() => {
    if (activeTab === TABS.DASHBOARD || activeTab === TABS.TRADING) {
      autoRefreshRef.current = setInterval(() => {
        fetchTradingData();
      }, 15000);
    }
    return () => {
      if (autoRefreshRef.current) {
        clearInterval(autoRefreshRef.current);
        autoRefreshRef.current = null;
      }
    };
  }, [activeTab, fetchTradingData]);

  // Refresh from Polymarket
  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      setRefreshStatus('Starting refresh...');
      setError(null);

      await api.refreshData({ maxMarkets: 100, minVolume: 1000 });
      setRefreshStatus('Fetching markets from Polymarket...');

      let pollCount = 0;
      const maxPolls = 60;

      const pollInterval = setInterval(async () => {
        pollCount++;
        try {
          const status = await api.getStatus();
          if (status.markets_loaded > 0) {
            setRefreshStatus(`Processing ${status.markets_loaded} markets...`);
          }
          if (!status.is_loading) {
            clearInterval(pollInterval);
            setRefreshing(false);
            setRefreshStatus('');
            await fetchData();
          } else if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
            setRefreshing(false);
            setRefreshStatus('');
            setError('Refresh timed out. Check server logs.');
            await fetchData();
          }
        } catch (err) {
          clearInterval(pollInterval);
          setRefreshing(false);
          setRefreshStatus('');
          setError(err.message);
        }
      }, 2000);
    } catch (err) {
      setRefreshing(false);
      setRefreshStatus('');
      setError(err.message);
    }
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleTimeString();
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>Polymarket Trading Platform</h1>
        <div className="flex gap-sm items-center">
          {tradingStatus?.wallet_balance?.balance != null && (
            <div className="header-wallet">
              <span className="header-wallet-label">Wallet</span>
              <span className="header-wallet-amount">
                ${tradingStatus.wallet_balance.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="header-wallet-currency">USDC</span>
            </div>
          )}
          {stats?.last_updated && (
            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
              Updated: {formatTime(stats.last_updated)}
            </span>
          )}
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
          <StatCard label="Markets" value={stats?.total_markets || 0} color="blue" />
          <StatCard label="Edges Found" value={stats?.total_opportunities || 0} color="green" />
          <StatCard label="High Confidence" value={stats?.high_confidence_opps || 0} color="yellow" />
          <StatCard label="Signals" value={tradingStatus?.signal_count || 0} color="purple" />
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === TABS.DASHBOARD ? 'active' : ''}`}
            onClick={() => { setActiveTab(TABS.DASHBOARD); fetchTradingData(); }}
          >
            Dashboard
          </button>
          <button
            className={`tab ${activeTab === TABS.SCANNER ? 'active' : ''}`}
            onClick={() => setActiveTab(TABS.SCANNER)}
          >
            Scanner
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
            {/* Dashboard Tab */}
            {activeTab === TABS.DASHBOARD && (
              <DashboardTab
                status={tradingStatus}
                signals={tradingSignals}
                stats={stats}
                onTabChange={(tab) => {
                  setActiveTab(tab);
                  if (tab === TABS.TRADING) fetchTradingData();
                }}
              />
            )}

            {/* Scanner Tab */}
            {activeTab === TABS.SCANNER && (
              <ScannerTab
                opportunities={opportunities}
                predictions={predictions}
              />
            )}

            {/* Trading Tab */}
            {activeTab === TABS.TRADING && (
              <TradingTab
                status={tradingStatus}
                signals={tradingSignals}
                scanning={scanning}
                onScan={handleScan}
                config={tradingConfig}
                onConfigChange={handleConfigChange}
                onReset={handleReset}
                autoScanning={autoScanning}
                onAutoScanToggle={handleAutoScanToggle}
              />
            )}
          </>
        )}
      </main>

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
