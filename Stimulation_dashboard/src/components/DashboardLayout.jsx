import React from 'react';
import { ConnectionPanel } from './ConnectionPanel';
import { DataCard } from './DataCard';
import { DataChart } from './DataChart';
import { Activity, Thermometer, Droplets, Heart } from 'lucide-react';
import { useFirebaseData } from '../hooks/useFirebaseData';

export function DashboardLayout() {
  const { data, history, isConnected, error } = useFirebaseData();

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1>AyurAI Data Stimulation</h1>
          <p style={{ color: '#94a3b8', marginTop: '0.5rem' }}>Real-time telemetry from Firebase</p>
        </div>
      </header>

      <ConnectionPanel
        isConnected={isConnected}
        error={error}
      />

      {/* Main Data Grid */}
      <div className="dashboard-grid">
        <DataCard
          title="Body Temperature"
          value={data.temperature.toFixed(1)}
          unit="°C"
          icon={Thermometer}
        />
        <DataCard
          title="SpO2"
          value={data.spo2.toFixed(0)}
          unit="%"
          icon={Droplets}
        />
        <DataCard
          title="Heart Rate"
          value={data.heart_rate.toFixed(0)}
          unit="bpm"
          icon={Heart}
        />
        <DataCard
          title="Activity (X-axis)"
          value={data.activity_x.toFixed(2)}
          unit="g"
          icon={Activity}
        />
      </div>

      {/* Historical Data Chart */}
      {history.length > 0 && <DataChart data={history} />}
    </div>
  );
}
