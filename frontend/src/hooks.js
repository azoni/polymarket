/**
 * Shared custom hooks.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Persist state to localStorage. Reads on mount, writes on change.
 */
export function useLocalStorage(key, defaultValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored !== null ? JSON.parse(stored) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch { /* ignore quota errors */ }
  }, [key, value]);

  return [value, setValue];
}

/**
 * Smoothly animate a number from its previous value to a new target.
 */
export function useAnimatedNumber(target, duration = 400) {
  const [display, setDisplay] = useState(target);
  const prevRef = useRef(target);
  const rafRef = useRef(null);

  useEffect(() => {
    const from = prevRef.current;
    const to = target;
    prevRef.current = target;

    if (from === to) return;

    const start = performance.now();
    const tick = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out quad
      const eased = 1 - (1 - progress) * (1 - progress);
      setDisplay(from + (to - from) * eased);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return display;
}

/**
 * Derive a bot status label and CSS class from boolean flags.
 */
export function useBotStatus(scanning, refreshing, autoScanning) {
  if (scanning || refreshing) {
    return { statusClass: 'status-scanning', label: 'Scanning...' };
  }
  if (autoScanning) {
    return { statusClass: 'status-active', label: 'Auto-scanning' };
  }
  return { statusClass: 'status-idle', label: 'Idle' };
}
