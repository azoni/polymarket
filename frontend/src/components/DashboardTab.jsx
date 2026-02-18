/**
 * DashboardTab — Landing page with P&L chart, positions, and recent signals.
 */

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

const CATEGORY_COLORS = {
  politics: '#3b82f6',
  sports: '#22c55e',
  crypto: '#eab308',
  economics: '#a855f7',
  entertainment: '#ec4899',
  science: '#06b6d4',
  legal: '#f97316',
  other: '#666666',
};

const EDGE_COLORS = {
  arbitrage: 'green',
  mispricing: 'yellow',
  volume_signal: 'purple',
  liquidity_gap: 'blue',
};

const STATUS_COLORS = {
  executed: 'green',
  dry_run: 'blue',
  blocked: 'yellow',
  failed: 'red',
};

export function DashboardTab({ status, signals, stats, onTabChange }) {
  const balance = status?.balance || { balance: 10000, starting_balance: 10000, pnl: 0 };
  const risk = status?.risk || {};
  const mode = status?.mode || 'paper';
  const pnl = balance.pnl || 0;
  const history = status?.balance_history || [];
  const positions = risk.position_details || {};
  const recentSignals = (signals || []).slice(0, 5);

  // Prepare chart data
  const chartData = history.map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    balance: h.balance,
    pnl: h.pnl,
  }));

  // Category data for bar chart
  const categoryData = Object.entries(stats?.markets_by_category || {}).map(([cat, count]) => ({
    name: cat,
    count,
    fill: CATEGORY_COLORS[cat] || '#666',
  }));

  const positionEntries = Object.entries(positions);

  return (
    <div className="dashboard-tab">
      {/* Top row: Account + P&L Chart */}
      <div className="dashboard-grid">
        {/* Account Summary */}
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
          </div>
        </div>

        {/* P&L Chart */}
        <div className="card">
          <div className="card-header">
            <h3>Balance History</h3>
            <span className="text-muted" style={{ fontSize: '0.875rem' }}>
              {history.length} snapshots
            </span>
          </div>
          <div className="card-body chart-container">
            {chartData.length < 2 ? (
              <div className="empty-state" style={{ padding: 'var(--spacing-lg)' }}>
                <p className="text-muted">Run scans to start tracking balance over time</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="balanceGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    stroke="#666"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="#666"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={v => `$${v.toLocaleString()}`}
                    domain={['dataMin - 50', 'dataMax + 50']}
                  />
                  <Tooltip
                    contentStyle={{ background: '#222', border: '1px solid #333', borderRadius: 6 }}
                    labelStyle={{ color: '#aaa' }}
                    formatter={(value) => [`$${value.toLocaleString()}`, 'Balance']}
                  />
                  <Area
                    type="monotone"
                    dataKey="balance"
                    stroke={pnl >= 0 ? '#22c55e' : '#ef4444'}
                    fill="url(#balanceGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Second row: Categories + Positions */}
      <div className="dashboard-grid">
        {/* Category Breakdown */}
        <div className="card">
          <div className="card-header">
            <h3>Markets by Category</h3>
            <span className="text-muted" style={{ fontSize: '0.875rem' }}>
              {stats?.total_markets || 0} total
            </span>
          </div>
          <div className="card-body chart-container">
            {categoryData.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--spacing-lg)' }}>
                <p className="text-muted">Refresh data to see market breakdown</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={categoryData} layout="vertical" margin={{ left: 60 }}>
                  <XAxis type="number" stroke="#666" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#666"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                  />
                  <Tooltip
                    contentStyle={{ background: '#222', border: '1px solid #333', borderRadius: 6 }}
                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {categoryData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Active Positions */}
        <div className="card">
          <div className="card-header">
            <h3>Active Positions</h3>
            <span className="text-muted" style={{ fontSize: '0.875rem' }}>
              {positionEntries.length} open
            </span>
          </div>
          <div className="card-body">
            {positionEntries.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--spacing-md)' }}>
                <p className="text-muted">No open positions</p>
              </div>
            ) : (
              <div className="positions-table">
                {positionEntries.map(([tokenId, pos]) => {
                  const info = typeof pos === 'object' ? pos : { exposure: pos };
                  return (
                    <div className="position-card" key={tokenId}>
                      <div className="position-card-top">
                        <span className="position-market" title={info.market || tokenId}>
                          {info.market || `${tokenId.substring(0, 16)}...`}
                        </span>
                        <span className="value">${(info.exposure || 0).toFixed(2)}</span>
                      </div>
                      <div className="position-card-meta">
                        {info.side && (
                          <span className={info.side === 'BUY' ? 'text-green' : 'text-red'}>
                            {info.side}
                          </span>
                        )}
                        {info.entry_price != null && (
                          <span className="text-muted">@ ${info.entry_price.toFixed(3)}</span>
                        )}
                        {info.edge_type && (
                          <span className={`badge ${EDGE_COLORS[info.edge_type] || 'gray'}`}>
                            {info.edge_type}
                          </span>
                        )}
                      </div>
                      {info.reasoning && (
                        <div className="position-reasoning text-muted">
                          {info.reasoning}
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

      {/* Recent Signals */}
      <div className="card">
        <div className="card-header">
          <h3>Recent Signals</h3>
          {signals?.length > 0 && (
            <button
              className="btn btn-secondary"
              onClick={() => onTabChange('trading')}
              style={{ fontSize: '0.75rem', padding: '4px 8px' }}
            >
              View All ({signals.length})
            </button>
          )}
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {recentSignals.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--spacing-md)' }}>
              <p className="text-muted">No signals yet. Run a scan from the Trading tab.</p>
            </div>
          ) : (
            <div className="recent-signals-compact">
              {recentSignals.map((sig, i) => (
                <div className="recent-signal-row" key={i}>
                  <div className="recent-signal-info">
                    <span className={sig.side === 'BUY' ? 'text-green' : 'text-red'}>
                      {sig.side}
                    </span>
                    <span className="recent-signal-market">{sig.market}</span>
                  </div>
                  <div className="recent-signal-meta">
                    <span>${sig.price?.toFixed(3)}</span>
                    <span className={`badge ${STATUS_COLORS[sig.status] || 'gray'}`}>
                      {sig.status === 'dry_run' ? 'paper' : sig.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
