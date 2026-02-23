/**
 * ResearchTab — Shows agent status, predictions, and activity feed.
 */

import { useState, useEffect, useCallback } from 'react';
import { ScoreBar } from './ScoreBar';
import * as api from '../api/client';

const AGENT_ICONS = {
  PoliticsAgent: 'POL',
  SportsAgent: 'SPT',
  CryptoAgent: 'CRY',
  EconomicsAgent: 'ECO',
  GeneralAgent: 'GEN',
};

const STATUS_COLORS = {
  online: 'green',
  degraded: 'yellow',
  idle: 'gray',
  offline: 'red',
};

import { DIRECTION_INFO } from '../constants';
import { TabIntroBanner } from './TabIntroBanner';
import { TAB_INTROS } from '../tooltips';

export function ResearchTab({ exchange }) {
  const [agents, setAgents] = useState([]);
  const [activity, setActivity] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all');
  const [expandedPred, setExpandedPred] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [agentData, activityData, predsData] = await Promise.all([
        api.getAgentStatus(),
        api.getAgentActivity({ limit: 50 }),
        api.getPredictions({ limit: 100, exchange: exchange || undefined }),
      ]);
      setAgents(agentData || []);
      setActivity(activityData || []);
      setPredictions(predsData || []);
    } catch (err) {
      console.error('[ResearchTab] fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [exchange]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const filteredPredictions = activeFilter === 'all'
    ? predictions
    : predictions.filter(p => p.agent_name === activeFilter);

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

  if (loading) {
    return (
      <div className="loading" style={{ padding: 'var(--spacing-lg)' }}>
        <div className="spinner" />
        Loading research data...
      </div>
    );
  }

  return (
    <div className="research-tab">
      <TabIntroBanner tabName="research" text={TAB_INTROS.research} />
      {/* Agent Status Grid */}
      <div className="agent-grid">
        {agents.map(agent => {
          const statusColor = STATUS_COLORS[agent.status] || 'gray';
          return (
            <div className="card agent-card" key={agent.name}>
              <div className="card-body">
                <div className="flex items-center gap-sm mb-sm">
                  <span className="agent-icon">{AGENT_ICONS[agent.name] || '?'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{agent.name.replace('Agent', '')}</div>
                    <div className="flex items-center gap-xs">
                      <span className={`agent-status-dot ${agent.status}`} />
                      <span className="text-muted" style={{ fontSize: 11 }}>{agent.status}</span>
                    </div>
                  </div>
                </div>
                <div className="agent-stats">
                  <div className="agent-stat">
                    <span className="label">Analyzed</span>
                    <span className="value">{agent.markets_analyzed || 0}</span>
                  </div>
                  <div className="agent-stat">
                    <span className="label">Success</span>
                    <span className="value">{agent.success_rate || 0}%</span>
                  </div>
                  <div className="agent-stat">
                    <span className="label">Avg Time</span>
                    <span className="value">{(agent.avg_duration_ms || 0).toFixed(0)}ms</span>
                  </div>
                </div>
                {agent.last_run && (
                  <div className="text-muted" style={{ fontSize: 10, marginTop: 6 }}>
                    Last run: {timeAgo(agent.last_run)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="research-layout">
        {/* Predictions Panel */}
        <div className="research-predictions">
          <div className="card">
            <div className="card-header">
              <h3>Predictions</h3>
              <span className="text-muted">{filteredPredictions.length}</span>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {/* Agent filter chips */}
              <div className="filter-chips" style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                <button
                  className={`filter-chip ${activeFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('all')}
                >
                  All
                </button>
                {agents.map(a => (
                  <button
                    key={a.name}
                    className={`filter-chip ${activeFilter === a.name ? 'active' : ''}`}
                    onClick={() => setActiveFilter(a.name)}
                  >
                    {a.name.replace('Agent', '')}
                  </button>
                ))}
              </div>

              {filteredPredictions.length === 0 ? (
                <div className="empty-state" style={{ padding: 'var(--spacing-lg)' }}>
                  <p className="text-muted">No predictions yet. Refresh data to generate predictions.</p>
                </div>
              ) : (
                <div className="predictions-list">
                  {filteredPredictions.map((pred, i) => {
                    const dirInfo = DIRECTION_INFO[pred.direction] || { label: pred.direction, color: 'gray' };
                    const isExpanded = expandedPred === i;
                    const dataSources = pred.data_sources || [];

                    return (
                      <div key={i}>
                        <div
                          className={`prediction-row ${isExpanded ? 'prediction-row-active' : ''}`}
                          onClick={() => setExpandedPred(isExpanded ? null : i)}
                        >
                          <div className="prediction-row-main">
                            <div className="prediction-question">
                              {pred.polymarket_url ? (
                                <a
                                  href={pred.polymarket_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="market-link"
                                  onClick={e => e.stopPropagation()}
                                >
                                  {pred.market_question}
                                  <span className="market-link-icon">&#x2197;</span>
                                </a>
                              ) : pred.market_question}
                            </div>
                            <div className="flex gap-sm mt-xs" style={{ flexWrap: 'wrap' }}>
                              <span className={`badge ${dirInfo.color}`}>{dirInfo.label}</span>
                              <span className="badge gray">{pred.strength}</span>
                              <span className="badge purple">{pred.agent_name?.replace('Agent', '')}</span>
                              {dataSources.map((src, j) => (
                                <span key={j} className="badge blue">{src}</span>
                              ))}
                            </div>
                          </div>
                          <div className="prediction-row-metrics">
                            <div className="metric">
                              <span className="label">Edge</span>
                              <span className={`value ${pred.edge > 0 ? 'text-green' : pred.edge < 0 ? 'text-red' : ''}`}>
                                {pred.edge > 0 ? '+' : ''}{(pred.edge * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="metric">
                              <span className="label">Conf</span>
                              <span className="value">{pred.confidence}%</span>
                            </div>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="prediction-detail">
                            <div className="metrics mb-md">
                              <div className="metric">
                                <span className="label">Current</span>
                                <span className="value">{(pred.current_price * 100).toFixed(0)}%</span>
                              </div>
                              <div className="metric">
                                <span className="label">Predicted</span>
                                <span className="value">{(pred.predicted_probability * 100).toFixed(0)}%</span>
                              </div>
                              <div className="metric">
                                <span className="label">Range</span>
                                <span className="value">
                                  {(pred.confidence_low * 100).toFixed(0)}-{(pred.confidence_high * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                            {pred.reasoning && (
                              <div style={{ marginBottom: 8 }}>
                                <div className="signal-detail-label">Reasoning</div>
                                <div className="text-secondary">{pred.reasoning}</div>
                              </div>
                            )}
                            {pred.key_risks?.length > 0 && (
                              <div style={{ marginBottom: 8 }}>
                                <div className="signal-detail-label">Risks</div>
                                <div className="text-secondary">{pred.key_risks.join(' / ')}</div>
                              </div>
                            )}
                            {pred.catalysts?.length > 0 && (
                              <div>
                                <div className="signal-detail-label">Catalysts</div>
                                <div className="text-secondary">{pred.catalysts.join(' / ')}</div>
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

        {/* Activity Feed */}
        <div className="research-activity">
          <div className="card">
            <div className="card-header">
              <h3>Activity Feed</h3>
              <span className="text-muted">{activity.length}</span>
            </div>
            <div className="card-body activity-feed">
              {activity.length === 0 ? (
                <div className="empty-state">
                  <p className="text-muted">No agent activity yet.</p>
                </div>
              ) : (
                activity.map((entry, i) => (
                  <div className="activity-entry" key={i}>
                    <div className="flex items-center gap-sm">
                      <span className={`agent-status-dot ${entry.success ? 'online' : 'offline'}`} />
                      <span style={{ fontWeight: 600, fontSize: 12 }}>
                        {entry.agent_name?.replace('Agent', '')}
                      </span>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        {entry.action}
                      </span>
                      {entry.data_source && (
                        <span className="badge blue" style={{ fontSize: 10 }}>{entry.data_source}</span>
                      )}
                    </div>
                    {entry.market_question && (
                      <div className="text-secondary activity-market">
                        {entry.market_question}
                      </div>
                    )}
                    <div className="flex gap-sm items-center" style={{ marginTop: 2 }}>
                      {entry.duration_ms > 0 && (
                        <span className="text-muted" style={{ fontSize: 10 }}>
                          {entry.duration_ms.toFixed(0)}ms
                        </span>
                      )}
                      {entry.created_at && (
                        <span className="text-muted" style={{ fontSize: 10 }}>
                          {timeAgo(entry.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
