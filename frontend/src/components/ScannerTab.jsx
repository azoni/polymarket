/**
 * ScannerTab — Filterable market browser with inline edge/prediction details.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ScoreBar } from './ScoreBar';
import * as api from '../api/client';

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'politics', label: 'Politics' },
  { value: 'sports', label: 'Sports' },
  { value: 'crypto', label: 'Crypto' },
  { value: 'economics', label: 'Economics' },
  { value: 'entertainment', label: 'Entertainment' },
  { value: 'science', label: 'Science' },
  { value: 'other', label: 'Other' },
];

const SORT_OPTIONS = [
  { value: 'edge_score', label: 'Edge Score' },
  { value: 'volume_24h', label: 'Volume' },
  { value: 'liquidity', label: 'Liquidity' },
  { value: 'spread_pct', label: 'Spread' },
];

const CATEGORY_COLORS = {
  politics: 'blue', sports: 'green', crypto: 'yellow',
  economics: 'purple', entertainment: 'purple', science: 'blue', other: 'gray',
};

const EDGE_TYPE_LABELS = {
  arbitrage: { label: 'Arbitrage', color: 'green' },
  mispricing: { label: 'Mispricing', color: 'yellow' },
  volume_signal: { label: 'Volume Signal', color: 'purple' },
  liquidity_gap: { label: 'Liquidity Gap', color: 'blue' },
  sentiment: { label: 'Sentiment', color: 'blue' },
  correlation: { label: 'Correlation', color: 'purple' },
  deadline_urgency: { label: 'Deadline', color: 'red' },
  consensus_divergence: { label: 'Consensus', color: 'yellow' },
  category_momentum: { label: 'Momentum', color: 'green' },
};

const DIRECTION_INFO = {
  buy_yes: { label: 'Buy YES', color: 'green' },
  buy_no: { label: 'Buy NO', color: 'red' },
  hold: { label: 'Hold', color: 'gray' },
};

const RISK_COLORS = { low: 'green', medium: 'yellow', high: 'red' };

export function ScannerTab({ opportunities, predictions, exchange }) {
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState('');
  const [sortBy, setSortBy] = useState('edge_score');
  const [search, setSearch] = useState('');
  const [expandedMarket, setExpandedMarket] = useState(null);
  const [marketEdges, setMarketEdges] = useState(null);
  const searchTimer = useRef(null);

  // Index opportunities and predictions by market_id for badge display
  const oppsByMarket = {};
  (opportunities || []).forEach(o => {
    if (!oppsByMarket[o.market_id]) oppsByMarket[o.market_id] = [];
    oppsByMarket[o.market_id].push(o);
  });

  const predsByMarket = {};
  (predictions || []).forEach(p => {
    predsByMarket[p.market_id] = p;
  });

  const fetchMarkets = useCallback(async (params = {}) => {
    try {
      setLoading(true);
      const data = await api.getMarkets({
        category: params.category || category || undefined,
        sortBy: params.sortBy || sortBy,
        search: params.search !== undefined ? params.search : search || undefined,
        limit: 100,
        exchange: exchange || undefined,
      });
      setMarkets(data);
    } catch (err) {
      console.error('[ScannerTab] fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [category, sortBy, search, exchange]);

  // Fetch on mount and when exchange changes
  useEffect(() => {
    fetchMarkets();
  }, [exchange]);

  const handleCategoryChange = (val) => {
    setCategory(val);
    setExpandedMarket(null);
    fetchMarkets({ category: val || undefined });
  };

  const handleSortChange = (val) => {
    setSortBy(val);
    setExpandedMarket(null);
    fetchMarkets({ sortBy: val });
  };

  const handleSearchInput = (val) => {
    setSearch(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      fetchMarkets({ search: val || undefined });
    }, 300);
  };

  const handleExpandMarket = async (marketId) => {
    if (expandedMarket === marketId) {
      setExpandedMarket(null);
      setMarketEdges(null);
      return;
    }
    setExpandedMarket(marketId);
    try {
      const edges = await api.getMarketEdges(marketId);
      setMarketEdges(edges);
    } catch (err) {
      console.error('[ScannerTab] edges fetch error:', err);
      setMarketEdges({ opportunities: [], predictions: [] });
    }
  };

  return (
    <div className="scanner-tab">
      {/* Filter Bar */}
      <div className="scanner-filters">
        <div className="scanner-filter-group">
          <select
            className="scanner-select"
            value={category}
            onChange={e => handleCategoryChange(e.target.value)}
          >
            {CATEGORIES.map(c => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        <div className="scanner-filter-group">
          <select
            className="scanner-select"
            value={sortBy}
            onChange={e => handleSortChange(e.target.value)}
          >
            {SORT_OPTIONS.map(s => (
              <option key={s.value} value={s.value}>Sort: {s.label}</option>
            ))}
          </select>
        </div>

        <div className="scanner-filter-group" style={{ flex: 1 }}>
          <input
            type="text"
            className="scanner-search"
            placeholder="Search markets..."
            value={search}
            onChange={e => handleSearchInput(e.target.value)}
          />
        </div>

        <span className="text-muted" style={{ fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
          {markets.length} markets
        </span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading" style={{ padding: 'var(--spacing-md)' }}>
          <div className="spinner" />
          Loading markets...
        </div>
      )}

      {/* Market List */}
      {!loading && markets.length === 0 && (
        <div className="empty-state">
          <p className="text-muted">No markets found. Click "Refresh Data" in the header to fetch markets.</p>
        </div>
      )}

      {!loading && markets.map(market => {
        const isExpanded = expandedMarket === market.market_id;
        const catColor = CATEGORY_COLORS[market.category] || 'gray';
        const marketOpps = oppsByMarket[market.market_id] || [];
        const marketPred = predsByMarket[market.market_id];

        return (
          <div className="card" key={market.market_id} style={{ marginBottom: 'var(--spacing-sm)' }}>
            {/* Market Row */}
            <div
              className="market-row market-row-clickable"
              onClick={() => handleExpandMarket(market.market_id)}
            >
              <div className="market-row-main">
                <h4 className="market-row-question">
                  {market.polymarket_url ? (
                    <a
                      href={market.polymarket_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="market-link"
                      onClick={e => e.stopPropagation()}
                    >
                      {market.question}
                      <span className="market-link-icon">&#x2197;</span>
                    </a>
                  ) : market.question}
                </h4>
                <div className="flex gap-sm mt-sm" style={{ flexWrap: 'wrap' }}>
                  <span className={`badge ${catColor}`}>{market.category}</span>
                  {market.days_until_resolution != null && (
                    <span className="badge gray">{market.days_until_resolution}d</span>
                  )}
                  {marketOpps.map((opp, i) => {
                    const eInfo = EDGE_TYPE_LABELS[opp.edge_type?.value || opp.edge_type] || { label: 'Edge', color: 'gray' };
                    return (
                      <span key={i} className={`badge ${eInfo.color}`}>{eInfo.label}</span>
                    );
                  })}
                  {marketPred && marketPred.direction !== 'hold' && (
                    <span className={`badge ${(DIRECTION_INFO[marketPred.direction] || {}).color || 'gray'}`}>
                      {(DIRECTION_INFO[marketPred.direction] || {}).label || marketPred.direction}
                    </span>
                  )}
                </div>
              </div>

              <div className="market-row-metrics">
                <div className="metric">
                  <span className="label">Price</span>
                  <span className="value">{(market.current_price * 100).toFixed(0)}%</span>
                </div>
                <div className="metric">
                  <span className="label">Volume</span>
                  <span className="value">${(market.volume_24h / 1000).toFixed(0)}k</span>
                </div>
                <div className="metric">
                  <span className="label">Edge</span>
                  <div className="flex items-center gap-sm">
                    <span className="value">{market.edge_score.toFixed(0)}</span>
                    <ScoreBar value={market.edge_score} />
                  </div>
                </div>
              </div>
            </div>

            {/* Expanded Detail */}
            {isExpanded && (
              <div className="market-expanded">
                {/* Full Metrics */}
                <div className="market-detail-section">
                  <div className="metrics">
                    <div className="metric">
                      <span className="label">Spread</span>
                      <span className="value">{market.spread_pct.toFixed(1)}%</span>
                    </div>
                    <div className="metric">
                      <span className="label">Liquidity</span>
                      <span className="value">${market.liquidity.toLocaleString()}</span>
                    </div>
                    <div className="metric">
                      <span className="label">24h Volume</span>
                      <span className="value">${market.volume_24h.toLocaleString()}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Efficiency</span>
                      <span className="value">{market.efficiency_score.toFixed(0)}</span>
                    </div>
                  </div>
                </div>

                {/* Opportunities */}
                {marketEdges?.opportunities?.length > 0 && (
                  <div className="market-detail-section">
                    <div className="signal-detail-label">Detected Edges</div>
                    {marketEdges.opportunities.map((opp, i) => {
                      const eInfo = EDGE_TYPE_LABELS[opp.edge_type?.value || opp.edge_type] || { label: opp.edge_type, color: 'gray' };
                      const riskColor = RISK_COLORS[opp.risk_level] || 'gray';
                      return (
                        <div key={i} className="market-edge-card">
                          <div className="flex gap-sm mb-md">
                            <span className={`badge ${eInfo.color}`}>{eInfo.label}</span>
                            <span className={`badge ${riskColor}`}>{opp.risk_level} risk</span>
                            <span className={`badge ${opp.expected_return > 0 ? 'green' : 'gray'}`}>
                              {opp.expected_return > 0 ? '+' : ''}{opp.expected_return.toFixed(1)}% EV
                            </span>
                            <span className="text-muted">{opp.confidence}% confidence</span>
                          </div>
                          <div style={{ marginBottom: 8 }}>{opp.description}</div>
                          {opp.suggested_action && (
                            <div className="signal-detail-highlight">{opp.suggested_action}</div>
                          )}
                          {opp.reasoning && (
                            <div className="text-secondary mt-sm" style={{ fontSize: '0.875rem' }}>
                              {opp.reasoning}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Prediction */}
                {marketEdges?.predictions?.length > 0 && (
                  <div className="market-detail-section">
                    <div className="signal-detail-label">Research Prediction</div>
                    {marketEdges.predictions.map((pred, i) => {
                      const dirInfo = DIRECTION_INFO[pred.direction] || { label: pred.direction, color: 'gray' };
                      return (
                        <div key={i} className="market-edge-card">
                          <div className="flex gap-sm mb-md" style={{ flexWrap: 'wrap' }}>
                            <span className={`badge ${dirInfo.color}`}>{dirInfo.label}</span>
                            <span className="badge gray">{pred.strength}</span>
                            <span className="badge purple">{pred.agent_name}</span>
                            {(pred.data_sources || []).map((src, j) => (
                              <span key={j} className="badge blue">{src}</span>
                            ))}
                          </div>
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
                              <span className="label">Edge</span>
                              <span className={`value ${pred.edge > 0 ? 'text-green' : 'text-red'}`}>
                                {pred.edge > 0 ? '+' : ''}{(pred.edge * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="metric">
                              <span className="label">Confidence</span>
                              <span className="value">{pred.confidence}%</span>
                            </div>
                          </div>
                          {pred.reasoning && (
                            <div className="signal-detail-highlight">{pred.reasoning}</div>
                          )}
                          {pred.key_risks?.length > 0 && (
                            <div className="text-secondary mt-sm" style={{ fontSize: '0.875rem' }}>
                              Risks: {pred.key_risks.join(' / ')}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* No edges found */}
                {marketEdges && marketEdges.opportunities?.length === 0 && marketEdges.predictions?.length === 0 && (
                  <div className="market-detail-section">
                    <p className="text-muted">No edges or predictions detected for this market.</p>
                  </div>
                )}

                {/* Loading edges */}
                {!marketEdges && (
                  <div className="market-detail-section">
                    <div className="loading" style={{ padding: 'var(--spacing-sm)' }}>
                      <div className="spinner" style={{ width: 16, height: 16 }} />
                      Loading details...
                    </div>
                  </div>
                )}

                {/* Link */}
                {market.polymarket_url && (
                  <div className="market-detail-section" style={{ textAlign: 'right' }}>
                    <a href={market.polymarket_url} target="_blank" rel="noopener noreferrer" className="market-external-link">
                      View on {market.market_id?.startsWith('kalshi:') ? 'Kalshi' : 'Polymarket'} &#x2197;
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
