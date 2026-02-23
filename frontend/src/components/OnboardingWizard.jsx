/**
 * OnboardingWizard — First-run setup wizard shown on initial visit.
 */

import { useState, useEffect } from 'react';
import { ProgressSteps } from './ProgressSteps';
import * as api from '../api/client';

const REFRESH_STEPS = [
  { label: 'Connecting' },
  { label: 'Fetching' },
  { label: 'Processing' },
  { label: 'Done' },
];

export function OnboardingWizard({ onComplete, onRefresh, refreshing, refreshStatus }) {
  const [step, setStep] = useState(0);
  const [backendOk, setBackendOk] = useState(null);
  const [checking, setChecking] = useState(false);

  // Step 1: check backend connection
  const checkBackend = async () => {
    setChecking(true);
    try {
      await api.getStatus();
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (step === 1 && backendOk === null) {
      checkBackend();
    }
  }, [step]);

  // Derive refresh progress step
  const getRefreshStep = () => {
    if (!refreshing) return -1;
    if (refreshStatus.includes('Starting')) return 0;
    if (refreshStatus.includes('Fetching')) return 1;
    if (refreshStatus.includes('Processing')) return 2;
    return 1;
  };

  return (
    <div className="wizard-overlay">
      <div className="wizard-card">
        {/* Step dots */}
        <div className="wizard-step-indicators">
          {[0, 1, 2, 3].map(i => (
            <span
              key={i}
              className={`wizard-step-dot ${i === step ? 'active' : i < step ? 'completed' : ''}`}
            />
          ))}
        </div>

        {/* Step 0: Welcome */}
        {step === 0 && (
          <div>
            <h2 style={{ marginBottom: 12 }}>Welcome to Polymarket Edge Finder</h2>
            <p className="text-secondary" style={{ lineHeight: 1.6, marginBottom: 16 }}>
              This platform finds pricing edges in prediction markets and paper-trades them automatically.
              It continuously scans markets on <strong>Polymarket</strong> and <strong>Kalshi</strong>,
              identifies mispricings using AI research agents, and executes simulated trades.
            </p>
            <div style={{ padding: 14, background: 'var(--bg-overlay)', borderRadius: 8, fontSize: 13 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>How it works:</div>
              <div className="text-secondary" style={{ lineHeight: 1.7 }}>
                1. <strong>Fetch</strong> live markets from prediction exchanges<br />
                2. <strong>Analyze</strong> each market with AI research agents<br />
                3. <strong>Detect</strong> pricing edges and opportunities<br />
                4. <strong>Trade</strong> automatically in paper mode (no real money)
              </div>
            </div>
          </div>
        )}

        {/* Step 1: Check Connection */}
        {step === 1 && (
          <div>
            <h2 style={{ marginBottom: 12 }}>Check Connection</h2>
            <p className="text-secondary" style={{ marginBottom: 16 }}>
              Let's make sure the backend server is running.
            </p>
            <div style={{ padding: 16, background: 'var(--bg-overlay)', borderRadius: 8, textAlign: 'center' }}>
              {checking && (
                <div className="flex items-center gap-sm" style={{ justifyContent: 'center' }}>
                  <span className="spinner" style={{ width: 16, height: 16 }} />
                  <span className="text-secondary">Checking connection...</span>
                </div>
              )}
              {backendOk === true && (
                <div>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>&#10003;</div>
                  <div style={{ color: 'var(--green)', fontWeight: 600 }}>Backend connected</div>
                  <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>Server is running and responding</div>
                </div>
              )}
              {backendOk === false && (
                <div>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>&#10007;</div>
                  <div style={{ color: 'var(--red)', fontWeight: 600, marginBottom: 8 }}>Cannot reach backend</div>
                  <div className="text-secondary" style={{ fontSize: 13, textAlign: 'left', lineHeight: 1.6 }}>
                    Start the backend server:<br />
                    <code style={{ background: 'var(--bg-base)', padding: '4px 8px', borderRadius: 4, fontSize: 12 }}>
                      cd backend && uvicorn main:app --reload --port 8001
                    </code>
                  </div>
                  <button className="btn btn-secondary mt-md" onClick={checkBackend}>
                    Retry
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 2: Load Data */}
        {step === 2 && (
          <div>
            <h2 style={{ marginBottom: 12 }}>Load Market Data</h2>
            <p className="text-secondary" style={{ marginBottom: 16 }}>
              Fetch live markets from Polymarket. This pulls current prices, runs edge detection,
              and generates AI predictions.
            </p>
            <div style={{ textAlign: 'center', padding: 16 }}>
              {!refreshing && (
                <button className="btn btn-primary" onClick={onRefresh} style={{ minWidth: 200 }}>
                  Fetch Live Markets
                </button>
              )}
              {refreshing && (
                <div>
                  <ProgressSteps steps={REFRESH_STEPS} currentStep={getRefreshStep()} />
                  <div className="text-muted" style={{ marginTop: 12, fontSize: 13 }}>
                    {refreshStatus || 'Loading...'}
                  </div>
                </div>
              )}
            </div>
            <p className="text-muted" style={{ fontSize: 12, marginTop: 16, textAlign: 'center' }}>
              You can skip this and load data later from the header.
            </p>
          </div>
        )}

        {/* Step 3: Explore */}
        {step === 3 && (
          <div>
            <h2 style={{ marginBottom: 12 }}>You're All Set</h2>
            <p className="text-secondary" style={{ marginBottom: 16 }}>
              Here's what each section does:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { name: 'Overview', desc: 'Quick summary — top opportunities, portfolio, bot status' },
                { name: 'Dashboard', desc: 'Deep portfolio view — balance chart, risk meters, trade signals' },
                { name: 'Scanner', desc: 'Browse all markets — filter, sort, expand to see edges' },
                { name: 'Research', desc: 'AI agent status — predictions, accuracy, activity feed' },
              ].map(tab => (
                <div key={tab.name} style={{ padding: '10px 14px', background: 'var(--bg-overlay)', borderRadius: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{tab.name}</span>
                  <span className="text-secondary" style={{ fontSize: 13 }}> — {tab.desc}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="wizard-actions">
          <div>
            {step > 0 && (
              <button className="btn btn-secondary" onClick={() => setStep(step - 1)}>
                Back
              </button>
            )}
          </div>
          <div className="flex gap-sm">
            <button
              className="btn btn-secondary"
              onClick={onComplete}
            >
              Skip
            </button>
            {step < 3 ? (
              <button className="btn btn-primary" onClick={() => setStep(step + 1)}>
                Next
              </button>
            ) : (
              <button className="btn btn-primary" onClick={onComplete}>
                Get Started
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
