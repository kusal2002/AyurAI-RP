import React from 'react';
import { Wifi, AlertCircle } from 'lucide-react';

export function ConnectionPanel({ isConnected, error }) {
  return (
    <div className="glass" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div className={`status-indicator ${isConnected ? 'status-connected' : 'status-disconnected'}`} />
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>
            {isConnected ? 'Live Firebase Stream Active' : 'Waiting for Data...'}
          </h2>
        </div>

        <div style={{ display: 'flex', gap: '1rem', color: '#94a3b8', alignItems: 'center' }}>
          <Wifi size={20} />
          <span>Cloud Sync</span>
        </div>
      </div>

      {error && (
        <div style={{ 
          marginTop: '1rem', 
          padding: '1rem', 
          backgroundColor: 'rgba(239, 68, 68, 0.1)', 
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          color: '#fca5a5'
        }}>
          <AlertCircle size={20} />
          {error}
        </div>
      )}
    </div>
  );
}
