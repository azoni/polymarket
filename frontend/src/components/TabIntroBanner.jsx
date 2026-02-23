/**
 * TabIntroBanner — Dismissable info banner shown at the top of each tab.
 */

import { useLocalStorage } from '../hooks';

export function TabIntroBanner({ tabName, text }) {
  const [dismissed, setDismissed] = useLocalStorage(`dismissed_intro_${tabName}`, false);

  if (dismissed) return null;

  return (
    <div className="tab-intro-banner">
      <span className="tab-intro-icon">i</span>
      <span>{text}</span>
      <button className="tab-intro-dismiss" onClick={() => setDismissed(true)}>
        Dismiss
      </button>
    </div>
  );
}
