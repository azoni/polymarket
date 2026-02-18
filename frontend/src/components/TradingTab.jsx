/**
 * TradingTab — trading dashboard showing account, risk, signals, and controls.
 */

export function TradingTab({ status, signals, scanning, onScan }) {
  const balance = status?.balance || { balance: 10000, starting_balance: 10000, pnl: 0 };
  const risk = status?.risk || {};
  const mode = status?.mode || 'paper';
  const pnl = balance.pnl || 0;

  return (
    <div className="trading-tab">
      {/* Top row: Account + Risk */}
      <div className="trading-grid">
        {/* Account Card */}
        <div className="card">
          <div className="card-header">
            <h3>Account</h3>
            <span className={`badge ${mode === 'paper' ? 'yellow' : 'green'}`}>
              {mode === 'paper' ? 'Paper' : 'Live'}
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
          </div>
        </div>

        {/* Risk Card */}
        <div className="card">
          <div className="card-header">
            <h3>Risk</h3>
          </div>
          <div className="card-body">
            {/* Daily P&L */}
            <div className="risk-row">
              <span className="risk-label">Daily P&L</span>
              <span className={risk.daily_pnl >= 0 ? 'text-green' : 'text-red'}>
                ${(risk.daily_pnl || 0).toFixed(2)}
              </span>
              <span className="text-muted">/ -${risk.daily_loss_limit || 25}</span>
            </div>

            {/* Exposure */}
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

            {/* Positions */}
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

            {/* Trades today */}
            <div className="risk-row mt-sm">
              <span className="risk-label">Trades Today</span>
              <span className="value">{risk.trades_today || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Scan button */}
      <div className="mb-md">
        <button
          className="btn btn-primary"
          onClick={onScan}
          disabled={scanning}
          style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
        >
          {scanning ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16 }} />
              Scanning markets...
            </>
          ) : (
            'Run Scan'
          )}
        </button>
      </div>

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
              {signals.map((sig, i) => (
                <div className="signal-row" key={i}>
                  <span className="signal-market" title={sig.market}>
                    {sig.market?.substring(0, 50)}{sig.market?.length > 50 ? '...' : ''}
                  </span>
                  <span className={sig.side === 'BUY' ? 'text-green' : 'text-red'}>
                    {sig.side}
                  </span>
                  <span>${sig.price?.toFixed(3)}</span>
                  <span>{sig.size}</span>
                  <span className="badge gray">{sig.edge_type}</span>
                  <span>{sig.confidence?.toFixed(0)}%</span>
                  <span>
                    <StatusBadge status={sig.status} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
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
