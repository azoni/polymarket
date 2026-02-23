/**
 * OverviewTab — Smart landing page combining key info from all tabs.
 */

import { useState } from 'react';
import { useAnimatedNumber } from '../hooks';
import { TabIntroBanner } from './TabIntroBanner';
import { TAB_INTROS } from '../tooltips';
import { EDGE_TYPE_LABELS, RISK_COLORS } from '../constants';

export function OverviewTab({
  stats, tradingStatus, tradingSignals, opportunities,
  scanning, autoScanning, onScan, onAutoScanToggle,
  onNavigate, activeExchange,
}) {
  const [expandedOpp, setExpandedOpp] = useState(null);

  const balance = tradingStatus?.balance || { balance: 10000, starting_balance: 10000, pnl: 0 };
  const risk = tradingStatus?.risk || {};
  const mode = tradingStatus?.mode || 'paper';
  const pnl = balance.pnl || 0;
  const totalValue = balance.total_value || (balance.balance + (risk.total_exposure || 0));
  const pnlPct = balance.starting_balance > 0 ? (pnl / balance.starting_balance * 100) : 0;

  const animatedTotal = useAnimatedNumber(totalValue);
  const animatedPnl = useAnimatedNumber(pnl);

  // Top opportunities sorted by confidence * expected_return
  const topOpps = [...(opportunities || [])]
    .filter(o => o.expected_return > 0)
    .sort((a, b) => (b.confidence * b.expected_return) - (a.confidence * a.expected_return))
    .slice(0, 5);

  // Recent signals
  const recentSignals = (tradingSignals || []).slice(0, 5);

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

  const exchangeLabel = activeExchange === 'kalshi' ? 'Kalshi' : 'Polymarket';

  return (
    <div className="overview-tab">
      <TabIntroBanner tabName="overview" text={TAB_INTROS.overview} />

      {/* Bot Status Bar */}
      <div className="overview-status-bar">
        <div className="overview-status-left">
          <span className={`badge ${mode === 'paper' ? 'yellow' : 'red'}`}>
            {mode === 'paper' ? 'Paper' : 'LIVE'}
          </span>
          <span className="text-secondary">{exchangeLabel}</span>
          <span className="text-muted">{stats?.total_markets || 0} markets</span>
          {stats?.total_opportunities > 0 && (
            <span className="text-green">{stats.total_opportunities} edges found</span>
          )}
        </div>
        <div className="overview-actions">
          <button
            className="btn btn-primary btn-sm"
            onClick={onScan}
            disabled={scanning || autoScanning}
          >
            {scanning ? 'Scanning...' : 'Scan Now'}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => onNavigate('scanner')}
          >
            All Markets
          </button>
        </div>
      </div>

      {/* Main Grid: Portfolio + Opportunities */}
      <div className="overview-grid">
        {/* Portfolio Summary */}
        <div
          className="card overview-portfolio-summary"
          onClick={() => onNavigate('dashboard')}
        >
          <div className="card-body">
            <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>Portfolio Value</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 4 }}>
              ${animatedTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ marginBottom: 12 }}>
              <span className={pnl >= 0 ? 'text-green' : 'text-red'} style={{ fontWeight: 600 }}>
                {animatedPnl >= 0 ? '+' : ''}{animatedPnl.toFixed(2)}
              </span>
              <span className="text-muted"> ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%) all time</span>
            </div>
            <div className="flex gap-md" style={{ fontSize: 13 }}>
              <div>
                <span className="text-muted">Cash </span>
                <span style={{ fontWeight: 600 }}>
                  ${balance.balance?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div>
                <span className="text-muted">Positions </span>
                <span style={{ fontWeight: 600 }}>
                  ${(risk.total_exposure || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div>
                <span className="text-muted">Open </span>
                <span style={{ fontWeight: 600 }}>{risk.open_positions || 0}</span>
              </div>
            </div>
            <div className="text-muted" style={{ fontSize: 11, marginTop: 10 }}>
              Click for full dashboard &rarr;
            </div>
          </div>
        </div>

        {/* Top Opportunities */}
        <div className="card">
          <div className="card-header">
            <h3>Top Opportunities</h3>
            {topOpps.length > 0 && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => onNavigate('scanner')}
              >
                View All
              </button>
            )}
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            {topOpps.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--sp-lg)' }}>
                <h4>No edges detected yet</h4>
                <p className="text-muted">Click "Scan Now" to find opportunities, or "Refresh Data" in the header to fetch markets first.</p>
              </div>
            ) : (
              topOpps.map((opp, i) => {
                const typeInfo = EDGE_TYPE_LABELS[opp.edge_type] || { label: opp.edge_type, color: 'gray' };
                const riskColor = RISK_COLORS[opp.risk_level] || 'gray';
                const isExpanded = expandedOpp === i;

                return (
                  <div
                    key={i}
                    className="top-opportunity-card"
                    onClick={() => setExpandedOpp(isExpanded ? null : i)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6 }} className="text-clamp-2">
                          {opp.market_question || opp.description}
                        </div>
                        <div className="flex gap-sm" style={{ flexWrap: 'wrap' }}>
                          <span className={`badge ${typeInfo.color}`}>{typeInfo.label}</span>
                          <span className={`badge ${riskColor}`}>{opp.risk_level}</span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div className="text-green" style={{ fontWeight: 700, fontSize: 14 }}>
                          +{opp.expected_return.toFixed(1)}%
                        </div>
                        <div className="text-muted" style={{ fontSize: 11 }}>
                          {opp.confidence}% conf
                        </div>
                      </div>
                    </div>
                    {isExpanded && (
                      <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
                        {opp.description && (
                          <div className="text-secondary" style={{ fontSize: 13, marginBottom: 6 }}>
                            {opp.description}
                          </div>
                        )}
                        {opp.suggested_action && (
                          <div style={{ padding: '8px 12px', background: 'var(--bg-overlay)', borderRadius: 6, fontSize: 13 }}>
                            {opp.suggested_action}
                          </div>
                        )}
                        {opp.reasoning && (
                          <div className="text-muted" style={{ fontSize: 12, marginTop: 6 }}>
                            {opp.reasoning}
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

      {/* Recent Activity */}
      {recentSignals.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>Recent Activity</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('dashboard')}>
              All Signals
            </button>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            {recentSignals.map((sig, i) => {
              const edgeInfo = EDGE_TYPE_LABELS[sig.edge_type] || { label: sig.edge_type, color: 'gray' };
              const statusColors = { executed: 'green', dry_run: 'blue', blocked: 'yellow', failed: 'red' };

              return (
                <div key={i} className="overview-activity-row">
                  <span className={`badge ${statusColors[sig.status] || 'gray'}`}>
                    {sig.status === 'dry_run' ? 'paper' : sig.status}
                  </span>
                  <span className={sig.side === 'BUY' ? 'text-green' : 'text-red'} style={{ fontWeight: 600, fontSize: 12 }}>
                    {sig.side}
                  </span>
                  <span className="text-secondary overview-activity-market">
                    {sig.market}
                  </span>
                  <span className={`badge ${edgeInfo.color}`} style={{ fontSize: 10 }}>{edgeInfo.label}</span>
                  <span className="text-muted" style={{ fontSize: 11, marginLeft: 'auto', flexShrink: 0 }}>
                    {timeAgo(sig.timestamp)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
