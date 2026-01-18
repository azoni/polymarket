/**
 * AdBanner Component
 * Displays Google AdSense ads.
 * 
 * Note: You'll need to create ad units in AdSense dashboard
 * and replace the data-ad-slot values.
 */

import { useEffect, useRef } from 'react';

export function AdBanner({ 
  slot = '', 
  format = 'auto', 
  responsive = true,
  style = {} 
}) {
  const adRef = useRef(null);
  const initialized = useRef(false);

  useEffect(() => {
    // Only initialize once
    if (initialized.current) return;
    
    try {
      if (window.adsbygoogle && adRef.current) {
        window.adsbygoogle.push({});
        initialized.current = true;
      }
    } catch (err) {
      console.error('[AdBanner] Error loading ad:', err);
    }
  }, []);

  // Don't render if no slot provided
  if (!slot) {
    return null;
  }

  return (
    <div style={{ 
      width: '100%', 
      minHeight: '90px',
      display: 'flex',
      justifyContent: 'center',
      margin: 'var(--spacing-md) 0',
      ...style 
    }}>
      <ins
        ref={adRef}
        className="adsbygoogle"
        style={{ display: 'block', width: '100%' }}
        data-ad-client="ca-pub-6660375648681858"
        data-ad-slot={slot}
        data-ad-format={format}
        data-full-width-responsive={responsive}
      />
    </div>
  );
}