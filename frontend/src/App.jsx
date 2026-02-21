/**
 * Polymarket Trading Platform
 * Main application component.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { StatCard, DashboardTab, ScannerTab, ResearchTab } from './components';
import * as api from './api/client';

const TABS = {
  DASHBOARD: 'dashboard',
  SCANNER: 'scanner',
  RESEARCH: 'research',
};

const EXCHANGES = [
  { id: 'polymarket', name: 'Polymarket' },
  { id: 'kalshi', name: 'Kalshi' },
];

export default function App() {
  // State
  const [activeTab, setActiveTab] = useState(TABS.DASHBOARD);
  const [activeExchange, setActiveExchange] = useState('polymarket');
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

  // Modals
  const [showWhitePaper, setShowWhitePaper] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState('polymarket');
  const [polyConfig, setPolyConfig] = useState(null);
  const [kalshiConfigState, setKalshiConfigState] = useState(null);

  // Auto-refresh interval ref
  const autoRefreshRef = useRef(null);

  const addToast = useCallback((message, type = 'info') => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  // Fetch trading data for the active exchange
  const fetchTradingData = useCallback(async (exchange) => {
    const ex = exchange || activeExchange;
    try {
      const [status, signals, config] = await Promise.all([
        api.getTradingStatus(ex),
        api.getTradingSignals(ex),
        api.getTradingConfig(ex),
      ]);
      setTradingStatus(status);
      setTradingSignals(signals);
      setTradingConfig(config);
      setAutoScanning(status?.auto_scan || false);
    } catch (err) {
      console.error('[fetchTradingData] Error:', err);
    }
  }, [activeExchange]);

  // Handle exchange switch
  const handleExchangeSwitch = useCallback((exchangeId) => {
    setActiveExchange(exchangeId);
    setTradingStatus(null);
    setTradingSignals([]);
    setTradingConfig(null);
    fetchTradingData(exchangeId);
  }, [fetchTradingData]);

  // Re-fetch core data when exchange changes
  useEffect(() => {
    fetchData();
  }, [activeExchange]);

  // Handle config change from Trading settings
  const handleConfigChange = async (updates) => {
    try {
      const updated = await api.updateTradingConfig(updates, activeExchange);
      setTradingConfig(updated);
      const status = await api.getTradingStatus(activeExchange);
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
      await api.triggerScan(activeExchange);
      await fetchTradingData();
      addToast(`${activeExchange === 'kalshi' ? 'Kalshi' : 'Polymarket'} scan complete`, 'success');
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
      await api.resetBalance(activeExchange);
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
        await api.stopAutoScan(activeExchange);
        setAutoScanning(false);
        addToast('Auto-scan stopped', 'info');
      } else {
        await api.startAutoScan(activeExchange);
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
        api.getStats(activeExchange),
        api.getOpportunities({ limit: 200, exchange: activeExchange }),
        api.getPredictions({ limit: 200, exchange: activeExchange }),
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
  }, [activeExchange]);

  // Initial load
  useEffect(() => {
    fetchData();
    fetchTradingData();
  }, [fetchData, fetchTradingData]);

  // Auto-refresh every 15 seconds on Dashboard tab
  useEffect(() => {
    if (activeTab === TABS.DASHBOARD) {
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

  // Open settings modal — fetch both exchange configs
  const openSettings = async () => {
    setShowSettings(true);
    try {
      const [pc, kc] = await Promise.all([
        api.getTradingConfig('polymarket'),
        api.getTradingConfig('kalshi'),
      ]);
      setPolyConfig(pc);
      setKalshiConfigState(kc);
    } catch (err) {
      console.error('[openSettings] Error:', err);
    }
  };

  // Update config for a specific exchange from the settings modal
  const handleSettingsConfigChange = async (exchange, updates) => {
    try {
      const updated = await api.updateTradingConfig(updates, exchange);
      if (exchange === 'polymarket') setPolyConfig(updated);
      else setKalshiConfigState(updated);
      // If this is the active exchange, sync to dashboard state too
      if (exchange === activeExchange) setTradingConfig(updated);
      addToast(`${exchange === 'kalshi' ? 'Kalshi' : 'Polymarket'} settings saved`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
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
          <button
            className="btn whitepaper-btn"
            onClick={() => setShowWhitePaper(true)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            White Paper
          </button>
          <button
            className="btn header-settings-btn"
            onClick={openSettings}
            title="Bot Settings"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            Settings
          </button>
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
            <span className="text-muted" style={{ fontSize: 10 }}>
              Last: {formatTime(stats.last_updated)}
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
            background: 'rgba(248, 113, 113, 0.08)',
            border: '1px solid rgba(248, 113, 113, 0.2)',
            borderRadius: 8,
            padding: '10px 14px',
            marginBottom: 14,
            color: '#f87171',
            fontSize: 13,
          }}>
            {error}
          </div>
        )}

        {/* Refresh Status Banner */}
        {refreshing && refreshStatus && (
          <div style={{
            background: 'rgba(96, 165, 250, 0.08)',
            border: '1px solid rgba(96, 165, 250, 0.2)',
            borderRadius: 8,
            padding: '10px 14px',
            marginBottom: 14,
            color: '#60a5fa',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
          }}>
            <div className="spinner" style={{ width: 14, height: 14 }} />
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

        {/* Exchange Selector + Tabs */}
        <div className="tabs-row">
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
              className={`tab ${activeTab === TABS.RESEARCH ? 'active' : ''}`}
              onClick={() => setActiveTab(TABS.RESEARCH)}
            >
              Research
            </button>
          </div>

          <div className="exchange-selector">
            {EXCHANGES.map(ex => (
              <button
                key={ex.id}
                className={`exchange-btn ${activeExchange === ex.id ? 'active' : ''}`}
                onClick={() => handleExchangeSwitch(ex.id)}
              >
                {ex.name}
              </button>
            ))}
          </div>
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
                scanning={scanning}
                onScan={handleScan}
                config={tradingConfig}
                onReset={handleReset}
                autoScanning={autoScanning}
                onAutoScanToggle={handleAutoScanToggle}
              />
            )}

            {/* Scanner Tab */}
            {activeTab === TABS.SCANNER && (
              <ScannerTab
                opportunities={opportunities}
                predictions={predictions}
                exchange={activeExchange}
              />
            )}

            {/* Research Tab */}
            {activeTab === TABS.RESEARCH && (
              <ResearchTab exchange={activeExchange} />
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

      {/* Settings Modal */}
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal-content settings-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Bot Settings</h2>
              <button className="modal-close" onClick={() => setShowSettings(false)}>
                &times;
              </button>
            </div>
            <div className="settings-exchange-tabs">
              <button
                className={`settings-exchange-tab ${settingsTab === 'polymarket' ? 'active' : ''}`}
                onClick={() => setSettingsTab('polymarket')}
              >
                Polymarket Bot
              </button>
              <button
                className={`settings-exchange-tab ${settingsTab === 'kalshi' ? 'active' : ''}`}
                onClick={() => setSettingsTab('kalshi')}
              >
                Kalshi Bot
              </button>
            </div>
            <div className="modal-body">
              {settingsTab === 'polymarket' && polyConfig && (
                <SettingsPanel
                  config={polyConfig}
                  exchange="polymarket"
                  onConfigChange={(updates) => handleSettingsConfigChange('polymarket', updates)}
                />
              )}
              {settingsTab === 'kalshi' && kalshiConfigState && (
                <SettingsPanel
                  config={kalshiConfigState}
                  exchange="kalshi"
                  onConfigChange={(updates) => handleSettingsConfigChange('kalshi', updates)}
                />
              )}
              {((settingsTab === 'polymarket' && !polyConfig) || (settingsTab === 'kalshi' && !kalshiConfigState)) && (
                <div className="loading" style={{ padding: 'var(--spacing-lg)' }}>
                  <div className="spinner" />
                  Loading config...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* White Paper Modal */}
      {showWhitePaper && (
        <div className="modal-overlay" onClick={() => setShowWhitePaper(false)}>
          <div className="modal-content whitepaper-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>White Paper</h2>
              <button className="modal-close" onClick={() => setShowWhitePaper(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <section className="wp-section">
                <h3>Overview</h3>
                <p>
                  The Polymarket Trading Platform is an automated edge detection and paper trading
                  system for prediction markets. It continuously ingests live market data from
                  <strong> Polymarket</strong> and <strong>Kalshi</strong>, identifies pricing
                  inefficiencies, and executes simulated trades based on quantitative signals.
                </p>
              </section>

              <section className="wp-section">
                <h3>How It Works</h3>
                <div className="wp-pipeline">
                  <div className="wp-pipeline-step">
                    <span className="wp-step-num">1</span>
                    <div>
                      <strong>Market Ingestion</strong>
                      <p>Fetches active markets from Polymarket's CLOB API and Kalshi's public events API. Filters by volume, liquidity, and market status.</p>
                    </div>
                  </div>
                  <div className="wp-pipeline-step">
                    <span className="wp-step-num">2</span>
                    <div>
                      <strong>Research Agents</strong>
                      <p>Specialized AI agents (Politics, Sports, Crypto, Economics, General) analyze each market using cross-referenced data sources including news, Kalshi pricing, and historical patterns to generate probability predictions.</p>
                    </div>
                  </div>
                  <div className="wp-pipeline-step">
                    <span className="wp-step-num">3</span>
                    <div>
                      <strong>Edge Detection</strong>
                      <p>A multi-strategy detection engine scans for 9 types of pricing edges across all ingested markets, comparing agent predictions against current prices.</p>
                    </div>
                  </div>
                  <div className="wp-pipeline-step">
                    <span className="wp-step-num">4</span>
                    <div>
                      <strong>Signal Generation & Execution</strong>
                      <p>The trading bot converts high-confidence edges into trade signals, passes them through a risk management layer, and executes paper trades in dry-run mode.</p>
                    </div>
                  </div>
                </div>
              </section>

              <section className="wp-section">
                <h3>Edge Types Detected</h3>
                <div className="wp-edge-grid">
                  <div className="wp-edge-item">
                    <span className="badge green">Arbitrage</span>
                    <p>Cross-market pricing discrepancies between related markets or temporal mispricings (e.g., "by 2025" vs "by 2030").</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge yellow">Mispricing</span>
                    <p>Markets where the current price deviates from the combined fair value implied by token pair probabilities.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge purple">Volume Signal</span>
                    <p>Unusual volume-to-liquidity ratios that indicate large informed flow or momentum.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge blue">Liquidity Gap</span>
                    <p>Wide bid-ask spreads offering market-making opportunities by providing tighter liquidity.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge blue">Sentiment</span>
                    <p>Divergence between news/social sentiment and current market pricing.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge purple">Correlation</span>
                    <p>Correlated markets that have temporarily decoupled from their historical relationship.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge red">Deadline</span>
                    <p>Time-decay effects as markets approach resolution, creating urgency-based mispricings.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge yellow">Consensus</span>
                    <p>Research agent predictions that diverge significantly from current market prices.</p>
                  </div>
                  <div className="wp-edge-item">
                    <span className="badge green">Momentum</span>
                    <p>Category-wide trends where related markets move together, signaling sector shifts.</p>
                  </div>
                </div>
              </section>

              <section className="wp-section">
                <h3>Risk Management</h3>
                <p>Every trade signal passes through a 4-layer risk management system:</p>
                <ul className="wp-list">
                  <li><strong>Position Limits</strong> &mdash; Maximum size per trade (default $50 Polymarket, $50 Kalshi)</li>
                  <li><strong>Daily Loss Limit</strong> &mdash; Auto-halts trading if daily P&L exceeds threshold</li>
                  <li><strong>Open Order Cap</strong> &mdash; Limits concurrent exposure across all markets</li>
                  <li><strong>Total Exposure</strong> &mdash; Maximum portfolio-wide capital at risk</li>
                </ul>
              </section>

              <section className="wp-section">
                <h3>Supported Exchanges</h3>
                <div className="wp-exchanges">
                  <div className="wp-exchange-card">
                    <strong>Polymarket</strong>
                    <p>Ethereum-based prediction market using USDC. Supports CLOB (Central Limit Order Book) for precise limit orders. Markets cover politics, sports, crypto, economics, and more.</p>
                  </div>
                  <div className="wp-exchange-card">
                    <strong>Kalshi</strong>
                    <p>CFTC-regulated prediction exchange with event contracts priced in cents (1-99). Covers similar categories with additional structured financial events. Supports RSA-authenticated API trading.</p>
                  </div>
                </div>
              </section>

              <section className="wp-section">
                <h3>Platform Tabs</h3>
                <ul className="wp-list">
                  <li><strong>Dashboard</strong> &mdash; Real-time portfolio view, trade signals, paper trading controls, risk meters, and auto-scan toggle. Shows independent bot state per exchange.</li>
                  <li><strong>Scanner</strong> &mdash; Filterable market browser across all ingested markets. Click any market to see detected edges and research predictions inline.</li>
                  <li><strong>Research</strong> &mdash; Agent status dashboard showing prediction accuracy, activity feed, and all generated probability predictions with reasoning.</li>
                </ul>
              </section>

              <section className="wp-section">
                <h3>Architecture</h3>
                <div className="wp-arch">
                  <code>
{`Frontend (React + Vite)  -->  Backend (FastAPI + Python)
     Port 3000                      Port 8001
                                        |
                    +-------------------+-------------------+
                    |                   |                   |
              Polymarket Bot      Kalshi Bot          Data Pipeline
              (paper trade)     (paper trade)      (ingest + detect)
                    |                   |                   |
                    +-------------------+-------------------+
                                        |
                                   SQLite DB
                            (markets, opportunities,
                          predictions, trade history)`}
                  </code>
                </div>
              </section>

              <section className="wp-section wp-disclaimer">
                <h3>Disclaimer</h3>
                <p>
                  This platform operates in <strong>paper trading mode</strong> by default. No real
                  money is at risk. All balances, positions, and P&L are simulated. The edge
                  detection algorithms are probabilistic and not financial advice. Past simulated
                  performance does not guarantee future results.
                </p>
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Settings Panel (used inside Settings modal) ─── */

const SETTINGS_UNLIMITED = 999999;

const ALL_EDGE_TYPES = [
  { value: 'arbitrage', label: 'Arbitrage', color: 'green' },
  { value: 'mispricing', label: 'Mispricing', color: 'yellow' },
  { value: 'volume_signal', label: 'Volume Signal', color: 'purple' },
  { value: 'liquidity_gap', label: 'Liquidity Gap', color: 'blue' },
  { value: 'sentiment', label: 'Sentiment', color: 'blue' },
  { value: 'correlation', label: 'Correlation', color: 'purple' },
  { value: 'deadline_urgency', label: 'Deadline', color: 'red' },
  { value: 'consensus_divergence', label: 'Consensus', color: 'yellow' },
  { value: 'category_momentum', label: 'Momentum', color: 'green' },
];

const ALL_RISK_LEVELS = [
  { value: 'low', label: 'Low', color: 'green' },
  { value: 'medium', label: 'Medium', color: 'yellow' },
  { value: 'high', label: 'High', color: 'red' },
];

function SettingsPanel({ config, exchange, onConfigChange }) {
  const handleModeToggle = () => {
    if (config?.dry_run) {
      if (window.confirm(`Switch ${exchange === 'kalshi' ? 'Kalshi' : 'Polymarket'} to LIVE trading? Real money will be used.`)) {
        onConfigChange({ dry_run: false });
      }
    } else {
      onConfigChange({ dry_run: true });
    }
  };

  const toggleEdgeType = (edgeType) => {
    const current = config.enabled_edge_types || ALL_EDGE_TYPES.map(e => e.value);
    const updated = current.includes(edgeType)
      ? current.filter(e => e !== edgeType)
      : [...current, edgeType];
    if (updated.length > 0) onConfigChange({ enabled_edge_types: updated });
  };

  const toggleRiskLevel = (level) => {
    const current = config.allowed_risk_levels || ['low', 'medium', 'high'];
    const updated = current.includes(level)
      ? current.filter(l => l !== level)
      : [...current, level];
    if (updated.length > 0) onConfigChange({ allowed_risk_levels: updated });
  };

  const enabledEdges = config.enabled_edge_types || ALL_EDGE_TYPES.map(e => e.value);
  const allowedRisk = config.allowed_risk_levels || ['low', 'medium', 'high'];

  return (
    <div className="settings-panel">
      {/* Trading Mode */}
      <div className="settings-section-header">Trading Mode</div>
      <div className="setting-row">
        <span className="setting-label">Mode</span>
        <div className="setting-input-group">
          <button
            className={`btn ${config.dry_run ? 'btn-secondary' : 'btn-danger'}`}
            onClick={handleModeToggle}
            style={{ minWidth: 120 }}
          >
            {config.dry_run ? 'Paper Mode' : 'LIVE MODE'}
          </button>
        </div>
      </div>

      {/* Execution Controls */}
      <div className="settings-section-header">Execution</div>

      <div className="setting-row">
        <span className="setting-label">Edge Types</span>
        <div className="setting-toggle-grid">
          {ALL_EDGE_TYPES.map(et => (
            <button
              key={et.value}
              className={`setting-toggle-chip ${enabledEdges.includes(et.value) ? `active ${et.color}` : ''}`}
              onClick={() => toggleEdgeType(et.value)}
            >
              {et.label}
            </button>
          ))}
        </div>
      </div>

      <div className="setting-row">
        <span className="setting-label">Risk Levels</span>
        <div className="setting-toggle-grid">
          {ALL_RISK_LEVELS.map(rl => (
            <button
              key={rl.value}
              className={`setting-toggle-chip ${allowedRisk.includes(rl.value) ? `active ${rl.color}` : ''}`}
              onClick={() => toggleRiskLevel(rl.value)}
            >
              {rl.label}
            </button>
          ))}
        </div>
      </div>

      <div className="setting-row">
        <span className="setting-label">Sizing Mode</span>
        <div className="setting-input-group">
          <button
            className={`btn btn-sm ${config.sizing_mode === 'confidence' ? 'btn-active' : 'btn-secondary'}`}
            onClick={() => onConfigChange({ sizing_mode: 'confidence' })}
          >
            Confidence Scaled
          </button>
          <button
            className={`btn btn-sm ${config.sizing_mode === 'fixed' ? 'btn-active' : 'btn-secondary'}`}
            onClick={() => onConfigChange({ sizing_mode: 'fixed' })}
          >
            Fixed Max
          </button>
        </div>
      </div>

      <ModalSettingInput label="Price Aggression" value={Math.round((config.price_aggressiveness || 0.99) * 100)} min={95} max={100} step={1} suffix="%" onChange={v => onConfigChange({ price_aggressiveness: v / 100 })} />
      <ModalSettingInput label="Min Price" value={Math.round((config.min_price || 0.05) * 100)} min={1} max={50} step={1} suffix="%" onChange={v => onConfigChange({ min_price: v / 100 })} />
      <ModalSettingInput label="Max Price" value={Math.round((config.max_price || 0.95) * 100)} min={50} max={99} step={1} suffix="%" onChange={v => onConfigChange({ max_price: v / 100 })} />

      {/* Risk Limits */}
      <div className="settings-section-header">Risk Limits</div>
      <ModalSettingInput label="Max Position" value={config.max_position_size} min={10} step={10} prefix="$" onChange={v => onConfigChange({ max_position_size: v })} />
      <ModalSettingInput label="Max Daily Loss" value={config.max_daily_loss} min={5} step={5} prefix="$" unlimited onChange={v => onConfigChange({ max_daily_loss: v })} />
      <ModalSettingInput label="Max Exposure" value={config.max_total_exposure} min={50} step={25} prefix="$" onChange={v => onConfigChange({ max_total_exposure: v })} />
      <ModalSettingInput label="Max Open Positions" value={config.max_open_orders} min={1} step={1} onChange={v => onConfigChange({ max_open_orders: v })} />

      {/* Scan Filters */}
      <div className="settings-section-header">Scan Filters</div>
      <ModalSettingInput label="Min Confidence" value={config.min_confidence} min={10} step={5} suffix="%" onChange={v => onConfigChange({ min_confidence: v })} />
      <ModalSettingInput label="Min Expected Return" value={config.min_expected_return} min={0.5} step={0.5} suffix="%" onChange={v => onConfigChange({ min_expected_return: v })} />
      <ModalSettingInput label="Min Liquidity" value={config.min_liquidity} min={0} step={1000} prefix="$" onChange={v => onConfigChange({ min_liquidity: v })} />
      <ModalSettingInput label="Scan Interval" value={config.scan_interval} min={10} step={10} suffix="s" onChange={v => onConfigChange({ scan_interval: v })} />
    </div>
  );
}

function ModalSettingInput({ label, value, min, step, prefix, suffix, unlimited, onChange }) {
  const [local, setLocal] = useState(value);
  const [isUnlimited, setIsUnlimited] = useState(value >= SETTINGS_UNLIMITED);

  useEffect(() => {
    setLocal(value);
    setIsUnlimited(value >= SETTINGS_UNLIMITED);
  }, [value]);

  const commit = (val) => {
    const clamped = Math.max(min, val);
    setLocal(clamped);
    onChange(clamped);
  };

  const handleBlur = () => {
    if (isUnlimited) return;
    commit(local);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') e.target.blur();
  };

  const toggleUnlimited = () => {
    if (isUnlimited) {
      const defaultVal = min * 5;
      setIsUnlimited(false);
      setLocal(defaultVal);
      onChange(defaultVal);
    } else {
      setIsUnlimited(true);
      setLocal(SETTINGS_UNLIMITED);
      onChange(SETTINGS_UNLIMITED);
    }
  };

  return (
    <div className="setting-row">
      <span className="setting-label">{label}</span>
      <div className="setting-input-group">
        {isUnlimited ? (
          <span className="setting-value-display">Unlimited</span>
        ) : (
          <div className="setting-number-wrap">
            {prefix && <span className="setting-affix">{prefix}</span>}
            <input
              type="number"
              className="setting-number"
              value={local}
              min={min}
              step={step}
              onChange={e => setLocal(Number(e.target.value))}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
            />
            {suffix && <span className="setting-affix">{suffix}</span>}
          </div>
        )}
        {unlimited && (
          <button
            className={`btn btn-sm ${isUnlimited ? 'btn-active' : 'btn-secondary'}`}
            onClick={toggleUnlimited}
          >
            {isUnlimited ? 'Set Limit' : 'No Limit'}
          </button>
        )}
      </div>
    </div>
  );
}
