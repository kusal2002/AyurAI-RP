import React from 'react';
import { Wifi, AlertCircle } from 'lucide-react';

export function ConnectionPanel({ isConnected, error }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
      <div className="glass connection-panel" style={{ padding: '0.5rem 1rem', margin: 0, borderRadius: '50px', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div className={`status-indicator ${isConnected ? 'status-connected' : 'status-disconnected'}`} />
        <span style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-color)' }}>
          {isConnected ? 'Stream Active' : 'Waiting for Data...'}
        </span>
        <div style={{ display: 'flex', gap: '0.5rem', color: 'var(--text-muted)', alignItems: 'center', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '0.75rem' }}>
          <Wifi size={16} />
        </div>
      </div>

      {error && (
        <div style={{ 
          padding: '0.5rem 1rem', 
          backgroundColor: 'rgba(239, 68, 68, 0.1)', 
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          color: '#fca5a5',
          fontSize: '0.85rem'
        }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}
    </div>
  );
}
