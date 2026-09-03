import React, { useEffect, useState } from 'react';
import { AlertTriangle, AlertOctagon, X } from 'lucide-react';

/**
 * AlertBanner — Shows flashing alert banners for out-of-range vitals.
 * Alerts can be dismissed individually.
 */
export function AlertBanner({ alerts }) {
  const [dismissed, setDismissed] = useState(new Set());
  const [flash, setFlash] = useState(false);

  const activeAlerts = alerts.filter(a => !dismissed.has(a.key + a.value));

  // Flash effect when new critical alerts arrive
  useEffect(() => {
    const hasCritical = activeAlerts.some(a => a.status === 'critical');
    if (hasCritical) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 600);
      return () => clearTimeout(t);
    }
  }, [alerts.length]);

  if (activeAlerts.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
      {activeAlerts.map((alert) => {
        const isCritical = alert.status === 'critical';
        const bgColor    = isCritical ? 'rgba(244,63,94,0.12)'  : 'rgba(245,158,11,0.10)';
        const border     = isCritical ? 'rgba(244,63,94,0.5)'   : 'rgba(245,158,11,0.5)';
        const glow       = isCritical ? 'rgba(244,63,94,0.2)'   : 'rgba(245,158,11,0.15)';
        const Icon       = isCritical ? AlertOctagon : AlertTriangle;
        const iconColor  = isCritical ? 'var(--accent-rose)'   : 'var(--accent-amber)';

        return (
          <div
            key={alert.key}
            style={{
              display:       'flex',
              alignItems:    'flex-start',
              gap:           '1rem',
              padding:       '1rem 1.25rem',
              borderRadius:  '14px',
              background:    bgColor,
              border:        `1px solid ${border}`,
              boxShadow:     `0 0 20px ${glow}`,
              animation:     (isCritical && flash) ? 'alert-flash 0.3s ease' : 'none',
              position:      'relative'
            }}
          >
            <Icon
              size={22}
              style={{
                color:     iconColor,
                flexShrink: 0,
                marginTop: '1px',
                filter:    `drop-shadow(0 0 6px ${iconColor})`
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                <span style={{
                  fontWeight:   700,
                  color:        iconColor,
                  fontSize:     '0.9rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  {isCritical ? '⚠ Critical' : '⚠ Warning'} — {alert.label}
                </span>
              </div>
              <p style={{ color: 'var(--text-color)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {alert.message}
              </p>
              {isCritical && (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                  This is a research prototype. Consult a medical professional for clinical assessment.
                </p>
              )}
            </div>

            {/* Dismiss button */}
            <button
              onClick={() => setDismissed(prev => new Set([...prev, alert.key + alert.value]))}
              style={{
                background:   'none',
                border:       'none',
                cursor:       'pointer',
                color:        'var(--text-muted)',
                padding:      '0.25rem',
                borderRadius: '4px',
                flexShrink:   0,
                opacity: 0.6
              }}
              title="Dismiss alert"
            >
              <X size={16} />
            </button>
          </div>
        );
      })}

      <style>{`
        @keyframes alert-flash {
          0%   { opacity: 1; }
          50%  { opacity: 0.4; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
