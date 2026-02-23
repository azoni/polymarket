/**
 * StatCard Component
 * Displays a single metric with label and animated value.
 */

import { useAnimatedNumber } from '../hooks';

export function StatCard({ label, value, color = 'blue' }) {
  const display = useAnimatedNumber(typeof value === 'number' ? value : 0);

  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className={`value ${color}`}>
        {typeof value === 'number' ? Math.round(display) : value}
      </div>
    </div>
  );
}
