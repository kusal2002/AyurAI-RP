import React from 'react';
import { VITAL_RANGES, getVitalStatus } from '../constants/vitalRanges';

/**
 * VitalsReference — Shows a clinical reference table and a visual
 * range bar for Heart Rate and SpO2.
 *
 * The bar highlights where the current reading falls within the range spectrum.
 */

function RangeBar({ vitalKey, currentValue }) {
  const vital = VITAL_RANGES[vitalKey];
  if (!vital) return null;

  const { scaleMin, scaleMax } = vital;
  const totalSpan = scaleMax - scaleMin;
  const vitalStatus = getVitalStatus(vitalKey, currentValue);

  return (
    <div>
      {/* Segmented range bar */}
      <div style={{ position: 'relative', height: '10px', borderRadius: '5px', overflow: 'hidden', display: 'flex', marginBottom: '0.5rem' }}>
        {vital.ranges.map((range, i) => {
          const clampedMin = Math.max(range.min, scaleMin);
          const clampedMax = Math.min(range.max, scaleMax);
          if (clampedMin >= clampedMax) return null;
          const left  = ((clampedMin - scaleMin) / totalSpan) * 100;
          const width = ((clampedMax - clampedMin) / totalSpan) * 100;
          return (
            <div
              key={i}
              title={`${range.label}: ${range.min}–${range.max}`}
              style={{
                position:   'absolute',
                left:       `${left}%`,
                width:      `${width}%`,
                height:     '100%',
                background: range.color,
                opacity:    0.5
              }}
            />
          );
        })}

        {/* Current value needle */}
        {currentValue != null && (
          <div
            style={{
              position:   'absolute',
              left:       `clamp(0%, ${((currentValue - scaleMin) / totalSpan) * 100}%, 100%)`,
              top:        '-3px',
              width:      '4px',
              height:     '16px',
              background: vitalStatus?.color ?? '#fff',
              borderRadius: '2px',
              boxShadow:  `0 0 8px ${vitalStatus?.color ?? '#fff'}`,
              transform:  'translateX(-50%)',
              transition: 'left 0.5s ease'
            }}
          />
        )}
      </div>

      {/* Scale labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        <span>{scaleMin}</span>
        <span>{scaleMax}{vital.unit}</span>
      </div>
    </div>
  );
}

function VitalReferenceCard({ vitalKey, currentValue }) {
  const vital = VITAL_RANGES[vitalKey];
  if (!vital) return null;

  const vitalStatus = getVitalStatus(vitalKey, currentValue);

  return (
    <div className="glass" style={{ padding: '1.5rem', flex: '1 1 280px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
        <div>
          <h4 style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.2rem' }}>{vital.label}</h4>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{vital.description}</p>
        </div>

        {/* Status Badge */}
        {vitalStatus && (
          <span style={{
            padding:      '0.25rem 0.75rem',
            borderRadius: '50px',
            fontSize:     '0.75rem',
            fontWeight:   600,
            color:        vitalStatus.color,
            border:       `1px solid ${vitalStatus.color}`,
            background:   `${vitalStatus.color}18`,
            whiteSpace:   'nowrap',
            boxShadow:    `0 0 8px ${vitalStatus.color}40`
          }}>
            {vitalStatus.label}
          </span>
        )}
      </div>

      {/* Range Bar */}
      <RangeBar vitalKey={vitalKey} currentValue={currentValue} />

      {/* Reference Table */}
      <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
        {vital.reference.map((row, i) => {
          // Determine if this row matches the current status
          const matchedRange = vital.ranges.find(r =>
            currentValue != null &&
            currentValue >= r.min &&
            currentValue <= r.max &&
            r.label === row.label
          );
          const isActive = !!matchedRange;

          return (
            <div
              key={i}
              style={{
                display:       'flex',
                alignItems:    'center',
                gap:           '0.75rem',
                padding:       '0.5rem 0.75rem',
                borderRadius:  '8px',
                background:    isActive ? `${matchedRange?.color}18` : 'rgba(255,255,255,0.03)',
                border:        isActive ? `1px solid ${matchedRange?.color}60` : '1px solid transparent',
                transition:    'all 0.3s ease'
              }}
            >
              {/* Color dot */}
              {(() => {
                const rangeForRow = vital.ranges.find(r => r.label === row.label);
                return (
                  <div style={{
                    width:        '8px',
                    height:       '8px',
                    borderRadius: '50%',
                    background:   rangeForRow?.color ?? 'var(--text-muted)',
                    flexShrink:   0,
                    boxShadow:    isActive ? `0 0 6px ${rangeForRow?.color}` : 'none'
                  }} />
                );
              })()}

              <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <div>
                  <span style={{ fontSize: '0.85rem', fontWeight: isActive ? 600 : 400, color: isActive ? 'var(--text-color)' : 'var(--text-muted)' }}>
                    {row.label}
                  </span>
                  {row.desc && (
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                      {row.desc}
                    </p>
                  )}
                </div>
                <span style={{
                  fontSize:   '0.8rem',
                  fontWeight: 600,
                  color:      isActive ? 'var(--text-color)' : 'var(--text-muted)',
                  whiteSpace: 'nowrap'
                }}>
                  {row.range}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function VitalsReference({ heartRate, spo2 }) {
  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.85rem' }}>
        📊 Clinical Reference Ranges
      </h3>
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        <VitalReferenceCard vitalKey="heart_rate" currentValue={heartRate} />
        <VitalReferenceCard vitalKey="spo2"       currentValue={spo2}      />
      </div>
    </div>
  );
}
