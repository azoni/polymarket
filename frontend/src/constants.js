/**
 * Shared constants used across multiple components.
 */

export const EDGE_TYPE_LABELS = {
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

export const EDGE_COLORS = {
  arbitrage: 'green',
  mispricing: 'yellow',
  volume_signal: 'purple',
  liquidity_gap: 'blue',
  sentiment: 'blue',
  correlation: 'purple',
  deadline_urgency: 'red',
  consensus_divergence: 'yellow',
  category_momentum: 'green',
};

export const RISK_COLORS = {
  low: 'green',
  medium: 'yellow',
  high: 'red',
};

export const CATEGORY_COLORS = {
  politics: 'blue',
  sports: 'green',
  crypto: 'yellow',
  economics: 'purple',
  entertainment: 'purple',
  science: 'blue',
  other: 'gray',
};

export const DIRECTION_INFO = {
  buy_yes: { label: 'Buy YES', color: 'green' },
  buy_no: { label: 'Buy NO', color: 'red' },
  hold: { label: 'Hold', color: 'gray' },
};

export const SETTINGS_UNLIMITED = 999999;
