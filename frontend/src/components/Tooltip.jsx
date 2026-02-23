/**
 * Tooltip — CSS-only hover tooltip.
 * HelpIcon — Small "?" circle that shows a tooltip on hover.
 */

export function Tooltip({ children, text, position = 'top' }) {
  return (
    <span className="tooltip-wrapper">
      {children}
      <span className={`tooltip-bubble tooltip-${position}`}>{text}</span>
    </span>
  );
}

export function HelpIcon({ tooltip, position = 'top' }) {
  return (
    <Tooltip text={tooltip} position={position}>
      <span className="help-icon">?</span>
    </Tooltip>
  );
}
