/**
 * StatCard Component
 * Displays a single metric with label and value.
 */

export function StatCard({ label, value, color = 'blue' }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className={`value ${color}`}>{value}</div>
    </div>
  );
}
