/**
 * TradingTab — trading dashboard with settings, risk, and expandable signal details.
 */

import { useState, useEffect } from 'react';

const EDGE_TYPE_LABELS = {
  arbitrage: { label: 'Arbitrage', color: 'green' },
  mispricing: { label: 'Mispricing', color: 'yellow' },
  volume_signal: { label: 'Volume Signal', color: 'purple' },
  liquidity_gap: { label: 'Liquidity Gap', color: 'blue' },
};

const RISK_COLORS = {
  low: 'green',
  medium: 'yellow',
  high: 'red',
};

const UNLIMITED = 999999;

export function TradingTab({ status, signals, scanning, onScan, config, onConfigChange, onReset, autoScanning, onAutoScanToggle }) {
  const balance = status?.balance || { balance: 10000, starting_balance: 10000, pnl: 0 };
  const risk = status?.risk || {};
  const mode = status?.mode || 'paper';
  const pnl = balance.pnl || 0;
  const wallet = status?.wallet_balance || { available: false, balance: null };

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [expandedSignal, setExpandedSignal] = useState(null);

  const handleModeToggle = () => {
    if (config?.dry_run) {
      if (window.confirm('Switch to LIVE trading? Real money will be used.')) {
        onConfigChange({ dry_run: false });
      }
    } else {
      onConfigChange({ dry_run: true });
    }
  };

  const handleReset = () => {
    if (window.confirm('Reset paper account to $10,000? This clears all positions, signals, and P&L history.')) {
      onReset();
    }
  };

  const isUnlimitedVal = (val) => val >= UNLIMITED;

  return (
    <div className="trading-tab">
      {/* Top row: Account + Risk */}
      <div className="trading-grid">
        {/* Account Card */}
        <div className="card">
          <div className="card-header">
            <h3>Account</h3>
            <span className={`badge ${mode === 'paper' ? 'yellow' : 'red'}`}>
              {mode === 'paper' ? 'Paper' : 'LIVE'}
            </span>
          </div>
          <div className="card-body">
            <div className="account-balance">
              ${balance.balance?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="account-pnl">
              <span className={pnl >= 0 ? 'text-green' : 'text-red'}>
                {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} P&L
              </span>
              <span className="text-muted" style={{ marginLeft: 8 }}>
                from ${balance.starting_balance?.toLocaleString()}
              </span>
            </div>
            {wallet.balance != null && (
              <div className="wallet-balance">
                <span className="text-muted">Wallet:</span>
                <span className="wallet-amount">
                  ${wallet.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDC
                </span>
              </div>
            )}
            <div className="metrics mt-md">
              <div className="metric">
                <span className="label">Cycles</span>
                <span className="value">{status?.cycles || 0}</span>
              </div>
              <div className="metric">
                <span className="label">Signals</span>
                <span className="value">{status?.signal_count || 0}</span>
              </div>
              <div className="metric">
                <span className="label">Last Scan</span>
                <span className="value">
                  {status?.last_scan_at
                    ? new Date(status.last_scan_at).toLocaleTimeString()
                    : 'Never'}
                </span>
              </div>
            </div>
            <button
              className="btn btn-secondary mt-md"
              onClick={handleReset}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              Reset Balance
            </button>
          </div>
        </div>

        {/* Risk Card */}
        <div className="card">
          <div className="card-header">
            <h3>Risk</h3>
          </div>
          <div className="card-body">
            <div className="risk-row">
              <span className="risk-label">Daily P&L</span>
              <span className={risk.daily_pnl >= 0 ? 'text-green' : 'text-red'}>
                ${(risk.daily_pnl || 0).toFixed(2)}
              </span>
              <span className="text-muted">
                / {isUnlimitedVal(risk.daily_loss_limit) ? 'No limit' : `-$${risk.daily_loss_limit || 25}`}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-label">Exposure</span>
              <div className="progress-bar-container">
                <div
                  className="progress-bar"
                  style={{
                    width: `${Math.min(100, ((risk.total_exposure || 0) / (risk.max_exposure || 200)) * 100)}%`,
                  }}
                />
              </div>
              <span className="text-secondary">
                ${(risk.total_exposure || 0).toFixed(0)} / ${risk.max_exposure || 200}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-label">Positions</span>
              <div className="progress-bar-container">
                <div
                  className="progress-bar green"
                  style={{
                    width: `${Math.min(100, ((risk.open_positions || 0) / (risk.max_positions || 5)) * 100)}%`,
                  }}
                />
              </div>
              <span className="text-secondary">
                {risk.open_positions || 0} / {risk.max_positions || 5}
              </span>
            </div>
            <div className="risk-row mt-sm">
              <span className="risk-label">Trades Today</span>
              <span className="value">{risk.trades_today || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      <div className="card settings-card">
        <div
          className="card-header"
          style={{ cursor: 'pointer' }}
          onClick={() => setSettingsOpen(!settingsOpen)}
        >
          <h3>Settings</h3>
          <span className="text-muted" style={{ fontSize: '0.875rem' }}>
            {settingsOpen ? 'Collapse' : 'Expand'}
          </span>
        </div>
        {settingsOpen && config && (
          <div className="card-body">
            {/* Mode Toggle */}
            <div className="setting-row">
              <span className="setting-label">Trading Mode</span>
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

            {/* Settings with number inputs */}
            <SettingInput
              label="Max Position"
              value={config.max_position_size}
              min={10} step={10}
              prefix="$"
              onChange={v => onConfigChange({ max_position_size: v })}
            />
            <SettingInput
              label="Max Daily Loss"
              value={config.max_daily_loss}
              min={5} step={5}
              prefix="$"
              unlimited
              onChange={v => onConfigChange({ max_daily_loss: v })}
            />
            <SettingInput
              label="Max Exposure"
              value={config.max_total_exposure}
              min={50} step={25}
              prefix="$"
              onChange={v => onConfigChange({ max_total_exposure: v })}
            />
            <SettingInput
              label="Max Open Positions"
              value={config.max_open_orders}
              min={1} step={1}
              onChange={v => onConfigChange({ max_open_orders: v })}
            />
            <SettingInput
              label="Min Confidence"
              value={config.min_confidence}
              min={10} step={5}
              suffix="%"
              onChange={v => onConfigChange({ min_confidence: v })}
            />
            <SettingInput
              label="Min Expected Return"
              value={config.min_expected_return}
              min={0.5} step={0.5}
              suffix="%"
              onChange={v => onConfigChange({ min_expected_return: v })}
            />
            <SettingInput
              label="Min Liquidity"
              value={config.min_liquidity}
              min={0} step={1000}
              prefix="$"
              onChange={v => onConfigChange({ min_liquidity: v })}
            />
            <SettingInput
              label="Scan Interval"
              value={config.scan_interval}
              min={10} step={10}
              suffix="s"
              onChange={v => onConfigChange({ scan_interval: v })}
            />
          </div>
        )}
      </div>

      {/* Scan Controls */}
      <div className="scan-controls mb-md">
        <button
          className="btn btn-primary"
          onClick={onScan}
          disabled={scanning || autoScanning}
          style={{ flex: 1, justifyContent: 'center', padding: '12px' }}
        >
          {scanning ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16 }} />
              Scanning...
            </>
          ) : (
            'Run Scan'
          )}
        </button>
        <button
          className={`btn ${autoScanning ? 'btn-danger' : 'btn-secondary'}`}
          onClick={onAutoScanToggle}
          style={{ minWidth: 150, justifyContent: 'center', padding: '12px' }}
        >
          {autoScanning ? 'Stop Auto-Scan' : 'Start Auto-Scan'}
        </button>
      </div>
      {autoScanning && (
        <div className="auto-scan-banner mb-md">
          <span className="spinner" style={{ width: 14, height: 14 }} />
          Auto-scanning every {config?.scan_interval || 120}s
        </div>
      )}

      {/* Signals table */}
      <div className="card">
        <div className="card-header">
          <h3>Recent Signals</h3>
          <span className="text-muted">{signals.length} total</span>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {signals.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--spacing-lg)' }}>
              <p className="text-muted">No signals yet. Click "Run Scan" to find opportunities.</p>
            </div>
          ) : (
            <div className="signals-table">
              <div className="signal-row signal-header">
                <span>Market</span>
                <span>Side</span>
                <span>Price</span>
                <span>Size</span>
                <span>Edge</span>
                <span>Conf</span>
                <span>Status</span>
              </div>
              {signals.map((sig, i) => {
                const isExpanded = expandedSignal === i;
                const edgeInfo = EDGE_TYPE_LABELS[sig.edge_type] || { label: sig.edge_type, color: 'gray' };
                const riskColor = RISK_COLORS[sig.risk_level] || 'gray';

                return (
                  <div key={i}>
                    <div
                      className={`signal-row signal-clickable ${isExpanded ? 'signal-active' : ''}`}
                      onClick={() => setExpandedSignal(isExpanded ? null : i)}
                    >
                      <span className="signal-market" title={sig.market}>
                        {sig.market?.substring(0, 50)}{sig.market?.length > 50 ? '...' : ''}
                      </span>
                      <span className={sig.side === 'BUY' ? 'text-green' : 'text-red'}>
                        {sig.side}
                      </span>
                      <span>${sig.price?.toFixed(3)}</span>
                      <span>{sig.size}</span>
                      <span className={`badge ${edgeInfo.color}`}>{edgeInfo.label}</span>
                      <span>{sig.confidence?.toFixed(0)}%</span>
                      <span>
                        <StatusBadge status={sig.status} />
                      </span>
                    </div>

                    {isExpanded && (
                      <div className="signal-expanded">
                        <div className="signal-detail-badges">
                          {sig.risk_level && (
                            <span className={`badge ${riskColor}`}>{sig.risk_level} risk</span>
                          )}
                          {sig.expected_return != null && (
                            <span className={`badge ${sig.expected_return > 0 ? 'green' : 'red'}`}>
                              {sig.expected_return > 0 ? '+' : ''}{sig.expected_return.toFixed(1)}% EV
                            </span>
                          )}
                        </div>

                        {sig.description && (
                          <div className="signal-detail-section">
                            <div className="signal-detail-label">Edge Description</div>
                            <div>{sig.description}</div>
                          </div>
                        )}

                        {sig.suggested_action && (
                          <div className="signal-detail-section">
                            <div className="signal-detail-label">Suggested Action</div>
                            <div className="signal-detail-highlight">{sig.suggested_action}</div>
                          </div>
                        )}

                        {sig.reasoning && (
                          <div className="signal-detail-section">
                            <div className="signal-detail-label">Reasoning</div>
                            <div className="text-secondary">{sig.reasoning}</div>
                          </div>
                        )}

                        {sig.status === 'blocked' && sig.reason && (
                          <div className="signal-detail-section">
                            <div className="signal-detail-label">Block Reason</div>
                            <div className="text-red">{sig.reason}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingInput({ label, value, min, step, prefix, suffix, unlimited, onChange }) {
  const [local, setLocal] = useState(value);
  const [isUnlimited, setIsUnlimited] = useState(value >= UNLIMITED);

  useEffect(() => {
    setLocal(value);
    setIsUnlimited(value >= UNLIMITED);
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
      setLocal(UNLIMITED);
      onChange(UNLIMITED);
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

function StatusBadge({ status }) {
  const colors = {
    executed: 'green',
    dry_run: 'blue',
    blocked: 'yellow',
    failed: 'red',
  };
  return (
    <span className={`badge ${colors[status] || 'gray'}`}>
      {status === 'dry_run' ? 'paper' : status}
    </span>
  );
}
