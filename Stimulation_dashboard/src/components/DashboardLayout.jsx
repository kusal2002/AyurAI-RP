import React from 'react';
import { ConnectionPanel } from './ConnectionPanel';
import { DataCard } from './DataCard';
import { DataChart } from './DataChart';
import { AnalysisPanel } from './AnalysisPanel';
import { AlertBanner } from './AlertBanner';
import { VitalsReference } from './VitalsReference';
import { Heart, Droplets, Radio, Waves, Syringe, TestTube, Thermometer } from 'lucide-react';
import { useFirebaseData } from '../hooks/useFirebaseData';
import { useAnalysisData } from '../hooks/useAnalysisData';
import { getVitalStatus, getActiveAlerts } from '../constants/vitalRanges';

export function DashboardLayout() {
  const { data, history, last2MinRecords, isConnected, error } = useFirebaseData();
  const { analysis, hasAnalysis, analysisError } = useAnalysisData('device01');

  // Helper: format values or show '—' when null
  const fmt = (val, decimals = 0) =>
    val != null ? Number(val).toFixed(decimals) : '—';

  // Get live clinical status for HR, SpO2, and Temp
  const hrStatus  = getVitalStatus('heart_rate', data.heart_rate);
  const spo2Status = getVitalStatus('spo2', data.spo2);
  const tempStatus = getVitalStatus('body_temperature', data.body_temperature);

  // Get all active alerts
  const alerts = getActiveAlerts(data);

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1>AyurAI Dashboard</h1>
          <p className="header-subtitle">
            MAX30102 · ESP32-S3 · Firebase · Groq
          </p>
        </div>
        <ConnectionPanel isConnected={isConnected} error={error} />
      </header>

      {/* ── Live Alerts ── */}
      <AlertBanner alerts={alerts} />

      {/* ── Sensor Cards ── */}
      <div className="dashboard-grid">
        <DataCard
          title="Heart Rate"
          value={fmt(data.heart_rate)}
          unit="bpm"
          icon={Heart}
          accentColor="rose"
          vitalStatus={hrStatus}
        />
        <DataCard
          title="SpO₂"
          value={fmt(data.spo2)}
          unit="%"
          icon={Droplets}
          accentColor="cyan"
          vitalStatus={spo2Status}
        />
        <DataCard
          title="Body Temp"
          value={fmt(data.body_temperature, 1)}
          unit="°C"
          icon={Thermometer}
          accentColor="amber"
          vitalStatus={tempStatus}
        />
        <DataCard
          title="Raw IR"
          value={data.raw_ir != null ? (data.raw_ir / 1000).toFixed(1) + 'k' : '—'}
          unit="ADC"
          icon={Waves}
          accentColor="amber"
        />
        <DataCard
          title="Raw RED"
          value={data.raw_red != null ? (data.raw_red / 1000).toFixed(1) + 'k' : '—'}
          unit="ADC"
          icon={Radio}
          accentColor="emerald"
        />
        <DataCard
          title="Hemoglobin (Est)"
          value={fmt(data.hb_estimate, 1)}
          unit="g/dL"
          icon={Syringe}
          accentColor="rose"
        />
        <DataCard
          title="Glucose (Est)"
          value={fmt(data.glucose_estimate)}
          unit="mg/dL"
          icon={TestTube}
          accentColor="cyan"
        />
      </div>

      {/* ── Clinical Reference Ranges ── */}
      <VitalsReference heartRate={data.heart_rate} spo2={data.spo2} />

      {/* ── Historical Chart ── */}
      {history.length > 0 && <DataChart data={history} />}

      {/* ── Groq AI Interpretation ── */}
      <AnalysisPanel
        analysis={analysis}
        hasAnalysis={hasAnalysis}
        analysisError={analysisError}
        last2MinRecords={last2MinRecords}
      />
    </div>
  );
}

