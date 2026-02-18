/**
 * DashboardTab — Two-column layout: main dashboard left, signals sidebar right.
 */

import { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const EDGE_TYPE_LABELS = {
  arbitrage: { label: 'Arbitrage', color: 'green' },
  mispricing: { label: 'Mispricing', color: 'yellow' },
  volume_signal: { label: 'Vol Signal', color: 'purple' },
  liquidity_gap: { label: 'Liq Gap', color: 'blue' },
};

const EDGE_COLORS = {
  arbitrage: 'green',
  mispricing: 'yellow',
  volume_signal: 'purple',
  liquidity_gap: 'blue',
};

const RISK_COLORS = {
  low: 'green',
  medium: 'yellow',
  high: 'red',
};

const UNLIMITED = 999999;

export function DashboardTab({
  status, signals, scanning, onScan, config, onConfigChange, onReset,
  autoScanning, onAutoScanToggle,
}) {
  const balance = status?.balance || { balance: 10000, starting_balance: 10000, pnl: 0 };
  const risk = status?.risk || {};
  const mode = status?.mode || 'paper';
  const pnl = balance.pnl || 0;
  const history = status?.balance_history || [];
  const positions = risk.position_details || {};
  const perf = status?.performance || { total_trades: 0, total_cost: 0, avg_confidence: 0, by_edge_type: {} };

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [expandedSignal, setExpandedSignal] = useState(null);

  const chartData = history.map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    balance: h.balance,
  }));

  const formatTime = (ts) => {
    if (!ts) return '';
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const timeAgo = (ts) => {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const positionEntries = Object.entries(positions);

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

  const signalList = signals || [];

  return (
    <div className="dashboard-layout">
      {/* ── Left: Main Dashboard ── */}
      <div className="dashboard-main">
        {/* Scan Controls */}
        <div className="scan-controls mb-md">
          <button
            className="btn btn-primary"
            onClick={onScan}
            disabled={scanning || autoScanning}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            {scanning ? (
              <>
                <span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }} />
                Scanning...
              </>
            ) : (
              'Run Scan'
            )}
          </button>
          <button
            className={`btn ${autoScanning ? 'btn-danger' : 'btn-secondary'}`}
            onClick={onAutoScanToggle}
            style={{ minWidth: 150, justifyContent: 'center' }}
          >
            {autoScanning ? 'Stop Auto-Scan' : 'Start Auto-Scan'}
          </button>
        </div>
        {autoScanning && (
          <div className="auto-scan-banner mb-md">
            <span className="spinner" style={{ width: 14, height: 14 }} />
            Auto-scanning every {config?.scan_interval || 120}s
            {status?.last_scan_at && (
              <span className="text-muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
                Last scan: {formatTime(status.last_scan_at)}
              </span>
            )}
          </div>
        )}
        {!autoScanning && status?.last_scan_at && (
          <div className="text-muted mb-md" style={{ fontSize: 11 }}>
            Last scan: {formatTime(status.last_scan_at)} ({timeAgo(status.last_scan_at)})
          </div>
        )}

        {/* Account + Chart */}
        <div className="dashboard-grid">
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
              <div className="metrics mt-md">
                <div className="metric">
                  <span className="label">Daily P&L</span>
                  <span className={`value ${(risk.daily_pnl || 0) >= 0 ? 'text-green' : 'text-red'}`}>
                    ${(risk.daily_pnl || 0).toFixed(2)}
                  </span>
                </div>
                <div className="metric">
                  <span className="label">Exposure</span>
                  <span className="value">${(risk.total_exposure || 0).toFixed(0)}</span>
                </div>
                <div className="metric">
                  <span className="label">Positions</span>
                  <span className="value">{risk.open_positions || 0}</span>
                </div>
                <div className="metric">
                  <span className="label">Scans</span>
                  <span className="value">{status?.cycles || 0}</span>
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

          <div className="card">
            <div className="card-header">
              <h3>Balance History</h3>
              <span className="text-muted">{history.length} snapshots</span>
            </div>
            <div className="card-body chart-container">
              {chartData.length < 2 ? (
                <div className="empty-state">
                  <p className="text-muted">Run scans to start tracking balance over time</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="balanceGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={pnl >= 0 ? '#34d399' : '#f87171'} stopOpacity={0.2} />
                        <stop offset="95%" stopColor={pnl >= 0 ? '#34d399' : '#f87171'} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#5a5a5d" fontSize={11} tickLine={false} axisLine={false} fontFamily="Inter, system-ui, sans-serif" />
                    <YAxis
                      stroke="#5a5a5d" fontSize={11} tickLine={false} axisLine={false}
                      tickFormatter={v => `$${v.toLocaleString()}`}
                      domain={['dataMin - 50', 'dataMax + 50']}
                      fontFamily="Inter, system-ui, sans-serif"
                    />
                    <Tooltip
                      contentStyle={{ background: '#161618', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 12, color: '#ececef', boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}
                      labelStyle={{ color: '#8b8b8e' }}
                      formatter={(value) => [`$${value.toLocaleString()}`, 'Balance']}
                    />
                    <Area
                      type="monotone" dataKey="balance"
                      stroke={pnl >= 0 ? '#34d399' : '#f87171'}
                      fill="url(#balanceGrad)" strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        {/* Risk + Performance */}
        <div className="dashboard-grid">
          <div className="card">
            <div className="card-header"><h3>Risk</h3></div>
            <div className="card-body">
              <div className="risk-row">
                <span className="risk-label">Daily P&L</span>
                <span className={risk.daily_pnl >= 0 ? 'text-green' : 'text-red'}>
                  ${(risk.daily_pnl || 0).toFixed(2)}
                </span>
                <span className="text-muted" style={{ marginLeft: 4 }}>
                  / {isUnlimitedVal(risk.daily_loss_limit) ? 'No limit' : `-$${risk.daily_loss_limit || 25}`}
                </span>
              </div>
              <div className="risk-row">
                <span className="risk-label">Exposure</span>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar"
                    style={{ width: `${Math.min(100, ((risk.total_exposure || 0) / (risk.max_exposure || 200)) * 100)}%` }}
                  />
                </div>
                <span className="text-secondary" style={{ marginLeft: 8, whiteSpace: 'nowrap' }}>
                  ${(risk.total_exposure || 0).toFixed(0)} / ${risk.max_exposure || 200}
                </span>
              </div>
              <div className="risk-row">
                <span className="risk-label">Positions</span>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar green"
                    style={{ width: `${Math.min(100, ((risk.open_positions || 0) / (risk.max_positions || 5)) * 100)}%` }}
                  />
                </div>
                <span className="text-secondary" style={{ marginLeft: 8, whiteSpace: 'nowrap' }}>
                  {risk.open_positions || 0} / {risk.max_positions || 5}
                </span>
              </div>
              <div className="risk-row" style={{ marginTop: 4 }}>
                <span className="risk-label">Trades Today</span>
                <span style={{ fontWeight: 600 }}>{risk.trades_today || 0}</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Performance</h3>
              <span className="text-muted">{perf.total_trades} trades</span>
            </div>
            <div className="card-body">
              {perf.total_trades === 0 ? (
                <div className="empty-state">
                  <p className="text-muted">Run scans to start tracking performance</p>
                </div>
              ) : (
                <>
                  <div className="metrics">
                    <div className="metric">
                      <span className="label">Total P&L</span>
                      <span className={`value ${pnl >= 0 ? 'text-green' : 'text-red'}`}>${pnl.toFixed(2)}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Invested</span>
                      <span className="value">${perf.total_cost?.toLocaleString()}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Avg Conf</span>
                      <span className="value">{perf.avg_confidence}%</span>
                    </div>
                  </div>
                  {Object.keys(perf.by_edge_type || {}).length > 0 && (
                    <div className="mt-md">
                      <div className="text-muted" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
                        By Edge Type
                      </div>
                      {Object.entries(perf.by_edge_type).map(([type, data]) => (
                        <div className="edge-breakdown-row" key={type}>
                          <span className={`badge ${EDGE_COLORS[type] || 'gray'}`}>{type.replace('_', ' ')}</span>
                          <span>{data.count} trades</span>
                          <span>${data.total_cost}</span>
                          <span>{data.avg_confidence}% conf</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Active Positions */}
        {positionEntries.length > 0 && (
          <div className="card">
            <div className="card-header">
              <h3>Active Positions</h3>
              <span className="text-muted">{positionEntries.length} open</span>
            </div>
            <div className="card-body">
              <div className="positions-table">
                {positionEntries.map(([tokenId, pos]) => {
                  const info = typeof pos === 'object' ? pos : { exposure: pos };
                  return (
                    <div className="position-card" key={tokenId}>
                      <div className="position-card-top">
                        <span className="position-market" title={info.market || tokenId}>
                          {info.market || `${tokenId.substring(0, 16)}...`}
                        </span>
                        <span style={{ fontWeight: 600 }}>${(info.exposure || 0).toFixed(2)}</span>
                      </div>
                      <div className="position-card-meta">
                        {info.side && (
                          <span className={info.side === 'BUY' ? 'text-green' : 'text-red'}>{info.side}</span>
                        )}
                        {info.entry_price != null && (
                          <span className="text-muted">
                            {Math.round(info.exposure / info.entry_price)} shares @ ${info.entry_price.toFixed(3)}
                          </span>
                        )}
                        {info.edge_type && (
                          <span className={`badge ${EDGE_COLORS[info.edge_type] || 'gray'}`}>{info.edge_type}</span>
                        )}
                        {info.opened_at && (
                          <span className="text-muted" style={{ fontSize: 10 }}>
                            {timeAgo(info.opened_at)}
                          </span>
                        )}
                      </div>
                      {info.reasoning && (
                        <div className="position-reasoning text-muted">{info.reasoning}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Settings (collapsible) */}
        <div className="card settings-card">
          <div
            className="card-header"
            style={{ cursor: 'pointer' }}
            onClick={() => setSettingsOpen(!settingsOpen)}
          >
            <h3>Settings</h3>
            <span className="text-muted" style={{ fontSize: 12 }}>
              {settingsOpen ? 'Hide' : 'Show'}
            </span>
          </div>
          {settingsOpen && config && (
            <div className="card-body">
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
              <SettingInput label="Max Position" value={config.max_position_size} min={10} step={10} prefix="$" onChange={v => onConfigChange({ max_position_size: v })} />
              <SettingInput label="Max Daily Loss" value={config.max_daily_loss} min={5} step={5} prefix="$" unlimited onChange={v => onConfigChange({ max_daily_loss: v })} />
              <SettingInput label="Max Exposure" value={config.max_total_exposure} min={50} step={25} prefix="$" onChange={v => onConfigChange({ max_total_exposure: v })} />
              <SettingInput label="Max Open Positions" value={config.max_open_orders} min={1} step={1} onChange={v => onConfigChange({ max_open_orders: v })} />
              <SettingInput label="Min Confidence" value={config.min_confidence} min={10} step={5} suffix="%" onChange={v => onConfigChange({ min_confidence: v })} />
              <SettingInput label="Min Expected Return" value={config.min_expected_return} min={0.5} step={0.5} suffix="%" onChange={v => onConfigChange({ min_expected_return: v })} />
              <SettingInput label="Min Liquidity" value={config.min_liquidity} min={0} step={1000} prefix="$" onChange={v => onConfigChange({ min_liquidity: v })} />
              <SettingInput label="Scan Interval" value={config.scan_interval} min={10} step={10} suffix="s" onChange={v => onConfigChange({ scan_interval: v })} />
            </div>
          )}
        </div>
      </div>

      {/* ── Right: Signals Sidebar ── */}
      <div className="card signals-sidebar">
        <div className="card-header">
          <h3>Signals</h3>
          <span className="text-muted">{signalList.length}</span>
        </div>
        <div className="signals-sidebar-body">
          {signalList.length === 0 ? (
            <div className="empty-state">
              <p className="text-muted">No signals yet. Run a scan to find opportunities.</p>
            </div>
          ) : (
            signalList.map((sig, i) => {
              const isExpanded = expandedSignal === i;
              const edgeInfo = EDGE_TYPE_LABELS[sig.edge_type] || { label: sig.edge_type, color: 'gray' };
              const riskColor = RISK_COLORS[sig.risk_level] || 'gray';

              return (
                <div key={i}>
                  <div
                    className={`signal-card ${isExpanded ? 'signal-card-active' : ''}`}
                    onClick={() => setExpandedSignal(isExpanded ? null : i)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div className="signal-card-market" title={sig.market} style={{ flex: 1 }}>
                        {sig.market}
                      </div>
                      {sig.timestamp && (
                        <span className="text-muted" style={{ fontSize: 10, whiteSpace: 'nowrap', flexShrink: 0 }}>
                          {timeAgo(sig.timestamp)}
                        </span>
                      )}
                    </div>
                    <div className="signal-card-row">
                      <span className={sig.side === 'BUY' ? 'text-green' : 'text-red'} style={{ fontWeight: 600 }}>
                        {sig.side}
                      </span>
                      <span className="text-secondary">{sig.size} @ ${sig.price?.toFixed(3)}</span>
                      <span className="text-muted">= ${(sig.price * sig.size).toFixed(2)}</span>
                    </div>
                    <div className="signal-card-row" style={{ marginTop: 4 }}>
                      <span className={`badge ${edgeInfo.color}`}>{edgeInfo.label}</span>
                      <span className="text-secondary">{sig.confidence?.toFixed(0)}% conf</span>
                      {sig.expected_return != null && (
                        <span className={sig.expected_return > 0 ? 'text-green' : 'text-muted'} style={{ fontSize: 11 }}>
                          {sig.expected_return > 0 ? '+' : ''}{sig.expected_return.toFixed(1)}% EV
                        </span>
                      )}
                      <StatusBadge status={sig.status} />
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="signal-card-detail">
                      {/* Timestamp + scan cycle */}
                      <div className="text-muted" style={{ fontSize: 10, marginBottom: 8 }}>
                        {sig.timestamp && formatTime(sig.timestamp)}
                        {sig.cycle && <span> &middot; Scan #{sig.cycle}</span>}
                      </div>
                      <div className="signal-detail-badges" style={{ marginBottom: 8 }}>
                        {sig.risk_level && <span className={`badge ${riskColor}`}>{sig.risk_level} risk</span>}
                        {sig.expected_return != null && (
                          <span className={`badge ${sig.expected_return > 0 ? 'green' : 'red'}`}>
                            {sig.expected_return > 0 ? '+' : ''}{sig.expected_return.toFixed(1)}% EV
                          </span>
                        )}
                      </div>
                      {sig.description && (
                        <div style={{ marginBottom: 8 }}>
                          <div className="signal-detail-label">Description</div>
                          <div className="text-secondary">{sig.description}</div>
                        </div>
                      )}
                      {sig.suggested_action && (
                        <div style={{ marginBottom: 8 }}>
                          <div className="signal-detail-label">Action</div>
                          <div className="signal-detail-highlight">{sig.suggested_action}</div>
                        </div>
                      )}
                      {sig.reasoning && (
                        <div style={{ marginBottom: 8 }}>
                          <div className="signal-detail-label">Reasoning</div>
                          <div className="text-secondary">{sig.reasoning}</div>
                        </div>
                      )}
                      {sig.status === 'blocked' && sig.reason && (
                        <div>
                          <div className="signal-detail-label">Block Reason</div>
                          <div className="text-red">{sig.reason}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
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
