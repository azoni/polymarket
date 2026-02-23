/**
 * Help text and intro strings used across the app.
 */

export const METRIC_HELP = {
  edge_score: 'Composite score (0-100) measuring how mispriced this market appears. Higher = stronger opportunity.',
  confidence: 'How certain the research agents are about this prediction, based on data quality and source agreement.',
  spread: 'Difference between best bid and ask. Wider spreads mean higher trading costs but potential market-making opportunity.',
  liquidity: 'Total dollar value in the order book. Higher liquidity = easier to enter and exit positions.',
  expected_return: 'Projected % gain if this edge reverts to fair value. Factors in confidence and current price.',
  risk_level: 'LOW: well-understood, high liquidity. MEDIUM: moderate uncertainty. HIGH: thin liquidity or binary catalyst.',
  pnl: 'Profit & Loss — total gain or loss on your paper trading portfolio since the starting balance.',
  daily_pnl: 'Profit & Loss for the current day only. Resets at midnight.',
  exposure: 'Total dollar amount currently deployed in open positions.',
  // Edge types
  arbitrage: 'Cross-market pricing discrepancy between related markets.',
  mispricing: 'Market price deviates from implied fair value of the token pair.',
  volume_signal: 'Unusual volume-to-liquidity ratio indicating large informed flow.',
  liquidity_gap: 'Wide bid-ask spread offering market-making opportunity.',
  sentiment: 'News/social sentiment diverges from current market price.',
  correlation: 'Correlated markets have temporarily decoupled.',
  deadline_urgency: 'Time-decay effects as a market approaches resolution.',
  consensus_divergence: 'Agent predictions diverge significantly from market price.',
  category_momentum: 'Category-wide trend where related markets move together.',
};

export const TAB_INTROS = {
  overview: 'Your command center. See top opportunities, portfolio summary, and bot status at a glance.',
  dashboard: 'Deep portfolio view with balance history, risk meters, performance breakdown, and all trade signals.',
  scanner: 'Browse all markets. Filter by category, sort by edge score, and expand any market to see detected edges.',
  research: 'Monitor AI research agents — prediction accuracy, activity logs, and probability predictions with reasoning.',
};
