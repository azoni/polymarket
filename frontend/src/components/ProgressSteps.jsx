/**
 * ProgressSteps — Horizontal multi-step indicator.
 * Each step: { label: string }
 * currentStep: 0-indexed active step (-1 = none started)
 */

export function ProgressSteps({ steps, currentStep }) {
  return (
    <div className="progress-steps">
      {steps.map((step, i) => {
        const isCompleted = i < currentStep;
        const isActive = i === currentStep;
        const cls = isCompleted ? 'completed' : isActive ? 'active' : '';

        return (
          <span key={i} style={{ display: 'contents' }}>
            {i > 0 && (
              <span className={`progress-step-connector ${isCompleted ? 'completed' : ''}`} />
            )}
            <span className={`progress-step ${cls}`}>
              <span className="progress-step-dot">
                {isCompleted ? '\u2713' : i + 1}
              </span>
              {step.label}
            </span>
          </span>
        );
      })}
    </div>
  );
}
