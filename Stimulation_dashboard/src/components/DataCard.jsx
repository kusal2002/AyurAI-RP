import React, { useEffect, useState } from 'react';

export function DataCard({ title, value, unit, icon: Icon, trend }) {
  // Simple animation effect on value change
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    setAnimate(true);
    const timer = setTimeout(() => setAnimate(false), 300);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="glass data-card">
      <div className="data-card-header">
        <span>{title}</span>
        {Icon && <Icon size={20} color="var(--primary)" />}
      </div>
      <div 
        className="data-card-value" 
        style={{ 
          transform: animate ? 'scale(1.05)' : 'scale(1)', 
          transition: 'transform 0.1s ease',
          color: animate ? '#60a5fa' : 'inherit'
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
