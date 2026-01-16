/**
 * ScoreBar Component
 * Visual progress bar for scores 0-100.
 */

export function ScoreBar({ value, max = 100 }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  let colorClass = 'low';
  if (percentage >= 70) colorClass = 'high';
  else if (percentage >= 40) colorClass = 'medium';
  
  return (
    <div className="score-bar">
      <div 
        className={`fill ${colorClass}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
