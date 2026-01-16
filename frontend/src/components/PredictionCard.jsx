/**
 * PredictionCard Component
 * Displays a research agent's prediction for a market.
 */

const DIRECTION_INFO = {
  buy_yes: { label: 'Buy YES', color: 'green' },
  buy_no: { label: 'Buy NO', color: 'red' },
  hold: { label: 'Hold', color: 'gray' },
};

export function PredictionCard({ prediction }) {
  const directionInfo = DIRECTION_INFO[prediction.direction] || { label: prediction.direction, color: 'gray' };
  const edgePositive = prediction.edge > 0;
  
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="flex gap-sm mb-md">
            <span className={`badge ${directionInfo.color}`}>{directionInfo.label}</span>
            <span className="badge gray">{prediction.strength}</span>
            <span className="badge purple">{prediction.agent_name}</span>
          </div>
          <h3>{prediction.market_question}</h3>
        </div>
        <div style={{ textAlign: 'right', minWidth: '100px' }}>
          <div className={`${edgePositive ? 'text-green' : 'text-red'}`} style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            {edgePositive ? '+' : ''}{(prediction.edge * 100).toFixed(1)}%
          </div>
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>Edge</div>
        </div>
      </div>
      
      <div className="card-body">
        <div className="metrics">
          <div className="metric">
            <span className="label">Current Price</span>
            <span className="value">{(prediction.current_price * 100).toFixed(0)}%</span>
          </div>
          
          <div className="metric">
            <span className="label">Predicted</span>
            <span className="value">{(prediction.predicted_probability * 100).toFixed(0)}%</span>
          </div>
          
          <div className="metric">
            <span className="label">Confidence</span>
            <span className="value">{prediction.confidence}%</span>
          </div>
          
          <div className="metric">
            <span className="label">Range</span>
            <span className="value">
              {(prediction.confidence_low * 100).toFixed(0)}% - {(prediction.confidence_high * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        
        {prediction.reasoning && (
          <div className="mt-md" style={{ padding: '12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <div className="text-muted" style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Analysis</div>
            <div style={{ fontSize: '0.875rem' }}>{prediction.reasoning}</div>
          </div>
        )}
        
        <div className="flex gap-md mt-md" style={{ flexWrap: 'wrap' }}>
          {prediction.key_risks?.length > 0 && (
            <div style={{ flex: 1, minWidth: '200px' }}>
              <div className="text-muted" style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Key Risks</div>
              <div style={{ fontSize: '0.875rem' }}>
                {prediction.key_risks.join(' • ')}
              </div>
            </div>
          )}
          
          {prediction.catalysts?.length > 0 && (
            <div style={{ flex: 1, minWidth: '200px' }}>
              <div className="text-muted" style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Catalysts</div>
              <div style={{ fontSize: '0.875rem' }}>
                {prediction.catalysts.join(' • ')}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
