import React, { useEffect, useState } from 'react';

export function DataCard({ title, value, unit, icon: Icon, trend, accentColor = 'cyan', vitalStatus }) {
  // Simple animation effect on value change
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    setAnimate(true);
    const timer = setTimeout(() => setAnimate(false), 300);
    return () => clearTimeout(timer);
  }, [value]);

  // Use vitalStatus color if provided (overrides accentColor for live clinical feedback)
  const colorVar = vitalStatus?.color ?? `var(--accent-${accentColor})`;
  const glowVar  = vitalStatus?.color
    ? `${vitalStatus.color}40`
    : `var(--accent-${accentColor}-glow)`;

  return (
    <div 
      className="glass data-card"
      style={{
        background: `radial-gradient(circle at 100% 0%, ${glowVar} 0%, rgba(15,15,20,0.6) 50%)`
      }}
    >
      <div className="data-card-header">
        <span>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {vitalStatus && (
            <div title={vitalStatus.label} style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: colorVar,
              boxShadow: `0 0 6px ${colorVar}`,
              animation: vitalStatus.status !== 'normal' ? 'pulse-status 1.5s infinite' : 'none'
            }} />
          )}
          {Icon && <Icon size={22} style={{ color: colorVar, filter: `drop-shadow(0 0 8px ${glowVar})` }} />}
        </div>
      </div>
      <div 
        className="data-card-value" 
        style={{ 
          transform: animate ? 'scale(1.03)' : 'scale(1)', 
          color: animate ? colorVar : 'inherit',
          textShadow: animate ? `0 0 20px ${glowVar}` : 'none'
        }}
      >
        {value}
        <span className="data-card-unit">{unit}</span>
      </div>
      {trend && (
        <div className={`value-trend ${trend > 0 ? 'trend-up' : 'trend-down'}`}>
          {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}% from last hour
        </div>
      )}
    </div>
  );
}
