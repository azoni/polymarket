/**
 * MarketCard Component
 * Displays a single market with its key metrics.
 */

import { ScoreBar } from './ScoreBar';

const CATEGORY_COLORS = {
  politics: 'blue',
  sports: 'green',
  crypto: 'yellow',
  economics: 'purple',
  entertainment: 'purple',
  science: 'blue',
  other: 'gray',
};

export function MarketCard({ market }) {
  const categoryColor = CATEGORY_COLORS[market.category] || 'gray';
  
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>{market.question}</h3>
          <div className="flex gap-sm mt-sm">
            <span className={`badge ${categoryColor}`}>{market.category}</span>
            {market.days_until_resolution !== null && (
              <span className="badge gray">{market.days_until_resolution}d left</span>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right', minWidth: '100px' }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            {(market.current_price * 100).toFixed(0)}%
          </div>
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>Current Price</div>
        </div>
      </div>
      
      <div className="card-body">
        <div className="metrics">
          <div className="metric">
            <span className="label">Edge Score</span>
            <div className="flex items-center gap-sm">
              <span className="value">{market.edge_score.toFixed(0)}</span>
              <ScoreBar value={market.edge_score} />
            </div>
          </div>
          
          <div className="metric">
            <span className="label">24h Volume</span>
            <span className="value">${market.volume_24h.toLocaleString()}</span>
          </div>
          
          <div className="metric">
            <span className="label">Liquidity</span>
            <span className="value">${market.liquidity.toLocaleString()}</span>
          </div>
          
          <div className="metric">
            <span className="label">Spread</span>
            <span className="value">{market.spread_pct.toFixed(1)}%</span>
          </div>
        </div>
        
        {market.polymarket_url && (
          <div className="mt-md">
            <a href={market.polymarket_url} target="_blank" rel="noopener noreferrer">
              View on Polymarket →
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
