/**
 * OpportunityCard Component
 * Displays a detected edge opportunity.
 */

const EDGE_TYPE_LABELS = {
  arbitrage: { label: 'Arbitrage', color: 'green' },
  mispricing: { label: 'Mispricing', color: 'yellow' },
  correlation: { label: 'Correlation', color: 'blue' },
  volume_signal: { label: 'Volume Signal', color: 'purple' },
  liquidity_gap: { label: 'Liquidity Gap', color: 'blue' },
};

const RISK_COLORS = {
  low: 'green',
  medium: 'yellow',
  high: 'red',
};

export function OpportunityCard({ opportunity }) {
  const typeInfo = EDGE_TYPE_LABELS[opportunity.edge_type] || { label: opportunity.edge_type, color: 'gray' };
  const riskColor = RISK_COLORS[opportunity.risk_level] || 'gray';
  
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="flex gap-sm mb-md">
            <span className={`badge ${typeInfo.color}`}>{typeInfo.label}</span>
            <span className={`badge ${riskColor}`}>{opportunity.risk_level} risk</span>
          </div>
          <h3>{opportunity.description}</h3>
          <p className="text-secondary mt-sm" style={{ fontSize: '0.875rem' }}>
            {opportunity.market_question}
          </p>
        </div>
        <div style={{ textAlign: 'right', minWidth: '100px' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            {opportunity.confidence}%
          </div>
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>Confidence</div>
        </div>
      </div>
      
      <div className="card-body">
        <div className="metrics">
          <div className="metric">
            <span className="label">Expected Return</span>
            <span className={`value ${opportunity.expected_return > 0 ? 'text-green' : ''}`}>
              {opportunity.expected_return > 0 ? '+' : ''}{opportunity.expected_return.toFixed(1)}%
            </span>
          </div>
        </div>
        
        {opportunity.suggested_action && (
          <div className="mt-md" style={{ padding: '12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <div className="text-muted" style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Suggested Action</div>
            <div style={{ fontSize: '0.875rem' }}>{opportunity.suggested_action}</div>
          </div>
        )}
        
        {opportunity.reasoning && (
          <div className="mt-md text-secondary" style={{ fontSize: '0.875rem' }}>
            {opportunity.reasoning}
          </div>
        )}
      </div>
    </div>
  );
}
