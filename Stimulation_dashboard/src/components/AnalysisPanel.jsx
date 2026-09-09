import React, { useState } from 'react';
import { 
  Brain, ShieldCheck, AlertTriangle, AlertOctagon, ListChecks, Loader, 
  Activity, AlertCircle, Clock, Stethoscope, FileText, Sparkles, 
  CheckCircle2, Heart, Droplets, Thermometer, TestTube, Syringe, TrendingUp, Info
} from 'lucide-react';

const RISK_CONFIG = {
  low:      { color: 'var(--accent-emerald)', glow: 'var(--accent-emerald-glow)', Icon: ShieldCheck,   label: 'Low Risk'      },
  moderate: { color: 'var(--accent-amber)',   glow: 'var(--accent-amber-glow)',   Icon: AlertTriangle, label: 'Moderate Risk' },
  high:     { color: 'var(--accent-rose)',    glow: 'var(--accent-rose-glow)',    Icon: AlertOctagon,  label: 'High Risk'     }
};

const SEVERITY_CONFIG = {
  'normal':                     { bg: 'rgba(16, 185, 129, 0.15)', border: 'var(--accent-emerald)', text: 'var(--accent-emerald)' },
  'mild risk':                  { bg: 'rgba(245, 158, 11, 0.15)', border: 'var(--accent-amber)',   text: 'var(--accent-amber)' },
  'moderate risk':              { bg: 'rgba(245, 158, 11, 0.25)', border: 'var(--accent-amber)',   text: 'var(--accent-amber)' },
  'elevated concern':           { bg: 'rgba(244, 63, 94, 0.2)',   border: 'var(--accent-rose)',    text: 'var(--accent-rose)' },
  'critical attention required':{ bg: 'rgba(244, 63, 94, 0.3)',   border: 'var(--accent-rose)',    text: 'var(--accent-rose)' }
};

/**
 * AnalysisPanel — Displays Groq AI clinical diagnostic interpretation
 * based on 2-minute continuous sensor recording.
 */
export function AnalysisPanel({ analysis, hasAnalysis, analysisError, last2MinRecords = [] }) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const triggerAnalysis = async () => {
    setIsAnalyzing(true);
    try {
      const payload = {
        duration_seconds: 120,
        records: last2MinRecords
      };

      await fetch('http://localhost:3000/api/analyze/device01', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      // The Firebase hook automatically picks up the new analysis
    } catch (err) {
      console.error("Analysis trigger failed:", err);
      alert("Failed to reach backend. Make sure it is running on port 3000.");
    } finally {
      // Allow Firebase to sync before stopping spinner
      setTimeout(() => setIsAnalyzing(false), 2000);
    }
  };

  // ── Not yet analysed ──
  if (!hasAnalysis && !analysisError) {
    return (
      <div className="glass" style={{ padding: '2.5rem', marginTop: '1.5rem', textAlign: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem', color: 'var(--text-muted)' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: 'rgba(34, 211, 238, 0.1)', border: '1px solid rgba(34, 211, 238, 0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)'
          }}>
            <Brain size={32} />
          </div>

          <div>
            <h3 style={{ fontWeight: 600, fontSize: '1.3rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
              Awaiting 2-Minute AI Clinical Analysis
            </h3>
            <p style={{ color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: '1.6', maxWidth: '600px', margin: '0 auto 1.5rem auto' }}>
              Click below to aggregate the last 2 minutes of continuous PPG telemetry, compute temporal trends, and generate a comprehensive diagnostic screening.
            </p>

            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.04)', padding: '0.4rem 1rem', borderRadius: '50px', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
              <Clock size={14} style={{ color: 'var(--accent-cyan)' }} />
              <span style={{ color: 'var(--text-muted)' }}>Telemetry buffer:</span>
              <strong style={{ color: 'var(--accent-cyan)' }}>{last2MinRecords.length} records ready</strong>
            </div>

            <br />

            <button 
              onClick={triggerAnalysis} 
              disabled={isAnalyzing}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.6rem',
                background: 'var(--accent-cyan)', color: '#000',
                border: 'none', padding: '0.85rem 2rem', borderRadius: '50px',
                fontWeight: 600, fontSize: '0.95rem', cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                opacity: isAnalyzing ? 0.7 : 1,
                boxShadow: '0 0 20px var(--accent-cyan-glow)',
                transition: 'all 0.2s ease'
              }}
            >
              {isAnalyzing ? <Loader size={18} className="spin" /> : <Activity size={18} />}
              {isAnalyzing ? 'Analyzing 2-Min Telemetry...' : 'Run 2-Minute AI Analysis'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Error ──
  if (analysisError) {
    return (
      <div className="glass" style={{ padding: '1.5rem', marginTop: '1.5rem', border: '1px solid rgba(244,63,94,0.3)' }}>
        <p style={{ color: 'var(--accent-rose)', fontWeight: 500, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertCircle size={18} /> {analysisError}
        </p>
      </div>
    );
  }

  const riskKey    = (analysis.risk_level || 'low').toLowerCase();
  const riskConf   = RISK_CONFIG[riskKey] || RISK_CONFIG.low;
  const { Icon: RiskIcon, color: riskColor, glow: riskGlow, label: riskLabel } = riskConf;

  const severityKey = (analysis.severity || 'normal').toLowerCase();
  const sevStyle = SEVERITY_CONFIG[severityKey] || SEVERITY_CONFIG['normal'];

  const confidence      = analysis.confidence ?? 0;
  const confPercent     = Math.round(confidence * 100);
  const recommendations = analysis.recommendations || [];
  const labTests        = analysis.lab_tests_recommended || [];
  const holistic        = analysis.holistic_and_lifestyle || [];
  const vitalsSummary   = analysis.vitals_summary_2min || {};
  const sessionInfo     = analysis.session || {};

  return (
    <div
      className="glass"
      style={{
        padding:    '2rem',
        marginTop:  '1.5rem',
        background: `radial-gradient(circle at 0% 100%, ${riskGlow} 0%, rgba(15,15,20,0.6) 50%)`
      }}
    >
      {/* ── Header & Action ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: 'rgba(34, 211, 238, 0.1)', border: '1px solid rgba(34, 211, 238, 0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)'
          }}>
            <Brain size={22} />
          </div>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: '1.25rem', margin: 0 }}>Groq AI Clinical Interpretation</h3>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              2-Minute Continuous Physiological Profiling
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Re-Analyze Button */}
          <button 
            onClick={triggerAnalysis} 
            disabled={isAnalyzing}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              background: 'rgba(255,255,255,0.06)', color: 'var(--text-color)',
              border: '1px solid rgba(255,255,255,0.15)', padding: '0.45rem 1.1rem', borderRadius: '50px',
              fontSize: '0.85rem', cursor: isAnalyzing ? 'not-allowed' : 'pointer',
              opacity: isAnalyzing ? 0.6 : 1, transition: 'all 0.2s'
            }}
          >
            {isAnalyzing ? <Loader size={14} className="spin" /> : <Activity size={14} />}
            {isAnalyzing ? 'Analyzing 2-Min...' : `Re-Analyze (${last2MinRecords.length} pts)`}
          </button>

          {/* Risk Level Badge */}
          <div style={{
            display:      'flex',
            alignItems:   'center',
            gap:          '0.5rem',
            padding:      '0.45rem 1rem',
            borderRadius: '50px',
            background:   `rgba(${riskKey === 'low' ? '16,185,129' : riskKey === 'moderate' ? '245,158,11' : '244,63,94'}, 0.15)`,
            border:       `1px solid ${riskColor}`,
            boxShadow:    `0 0 12px ${riskGlow}`
          }}>
            <RiskIcon size={16} style={{ color: riskColor }} />
            <span style={{ color: riskColor, fontWeight: 600, fontSize: '0.85rem' }}>{riskLabel}</span>
          </div>
        </div>
      </div>

      {/* ── Primary Diagnostic Impression Banner ── */}
      <div style={{
        padding: '1.5rem',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
        border: '1px solid rgba(255,255,255,0.12)',
        marginBottom: '1.5rem',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Stethoscope size={20} style={{ color: 'var(--accent-cyan)' }} />
            <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-muted)', fontWeight: 600 }}>
              Primary Diagnostic Screening Impression
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {analysis.diagnostic_category && (
              <span style={{
                fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase',
                padding: '0.2rem 0.6rem', borderRadius: '50px',
                background: 'rgba(34, 211, 238, 0.15)', color: 'var(--accent-cyan)',
                border: '1px solid rgba(34, 211, 238, 0.3)'
              }}>
                {analysis.diagnostic_category}
              </span>
            )}
            {analysis.severity && (
              <span style={{
                fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase',
                padding: '0.2rem 0.6rem', borderRadius: '50px',
                background: sevStyle.bg, color: sevStyle.text, border: `1px solid ${sevStyle.border}`
              }}>
                {analysis.severity}
              </span>
            )}
          </div>
        </div>

        <h2 style={{
          fontSize: '1.35rem', fontWeight: 700, margin: '0 0 0.5rem 0',
          color: '#fff', letterSpacing: '-0.3px'
        }}>
          {analysis.primary_diagnosis || "Diagnostic Impression Pending"}
        </h2>

        {analysis.session_overview && (
          <p style={{ margin: 0, fontSize: '0.92rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            {analysis.session_overview}
          </p>
        )}
      </div>

      {/* ── 2-Minute Session Analytics Bar ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '0.75rem', marginBottom: '1.5rem'
      }}>
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
            <Clock size={13} style={{ color: 'var(--accent-cyan)' }} />
            <span>RECORDING WINDOW</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)' }}>
            {sessionInfo.duration_seconds || 120}s <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>({sessionInfo.sample_count || last2MinRecords.length} frames)</span>
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
            <Activity size={13} style={{ color: 'var(--accent-emerald)' }} />
            <span>SIGNAL QUALITY</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>
            {sessionInfo.signal_quality_percent != null ? `${sessionInfo.signal_quality_percent}%` : '100%'}
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '4px' }}>contact</span>
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
            <Heart size={13} style={{ color: 'var(--accent-rose)' }} />
            <span>HR 2-MIN RANGE</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)' }}>
            {vitalsSummary.heart_rate ? `${vitalsSummary.heart_rate.min} - ${vitalsSummary.heart_rate.max}` : '—'} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>bpm</span>
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
            <Droplets size={13} style={{ color: 'var(--accent-cyan)' }} />
            <span>SpO₂ 2-MIN RANGE</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)' }}>
            {vitalsSummary.spo2 ? `${vitalsSummary.spo2.min} - ${vitalsSummary.spo2.max}` : '—'} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>%</span>
          </div>
        </div>
      </div>

      {/* ── Interpretation Confidence ── */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Sparkles size={14} style={{ color: 'var(--accent-cyan)' }} />
            Diagnostic Confidence Score
          </span>
          <span style={{ color: riskColor, fontWeight: 600, fontSize: '0.85rem' }}>{confPercent}%</span>
        </div>
        <div style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px' }}>
          <div style={{
            height:           '100%',
            width:            `${confPercent}%`,
            borderRadius:     '3px',
            background:       riskColor,
            boxShadow:        `0 0 8px ${riskGlow}`,
            transition:       'width 0.6s ease'
          }} />
        </div>
      </div>

      {/* ── 2-Minute Temporal Trend Summary ── */}
      {analysis.temporal_trend_summary && (
        <div style={{
          padding: '1rem 1.25rem',
          borderRadius: '12px',
          background: 'rgba(34, 211, 238, 0.04)',
          border: '1px solid rgba(34, 211, 238, 0.12)',
          marginBottom: '1.25rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
            <TrendingUp size={15} style={{ color: 'var(--accent-cyan)' }} />
            <span style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
              2-Minute Temporal Dynamics & Stability
            </span>
          </div>
          <p style={{ fontSize: '0.92rem', lineHeight: 1.6, color: 'var(--text-color)', margin: 0 }}>
            {analysis.temporal_trend_summary}
          </p>
        </div>
      )}

      {/* ── Physiological Summary ── */}
      <div style={{ marginBottom: '1.5rem' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem', fontWeight: 600 }}>
          Physiological Multi-System Assessment
        </p>
        <p style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-color)', margin: 0 }}>
          {analysis.physiological_summary}
        </p>
      </div>

      {/* ── Specialized Screening Grid (Anemia & Diabetes) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {/* Anemia Screening */}
        <div style={{
          padding:      '1.25rem',
          borderRadius: '12px',
          background:   'rgba(244, 63, 94, 0.04)',
          border:       '1px solid rgba(244, 63, 94, 0.12)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Syringe size={16} style={{ color: 'var(--accent-rose)' }} />
              <span style={{ color: 'var(--accent-rose)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
                Anemia Screening
              </span>
            </div>
            {vitalsSummary.hb_estimate && (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Hb Avg: <strong style={{ color: 'var(--accent-rose)' }}>{vitalsSummary.hb_estimate.mean} g/dL</strong>
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--text-color)', margin: 0 }}>
            {analysis.anemia_screening}
          </p>
        </div>

        {/* Diabetes & Blood Sugar Screening */}
        {analysis.diabetes_screening && (
          <div style={{
            padding:      '1.25rem',
            borderRadius: '12px',
            background:   'rgba(34, 211, 238, 0.04)',
            border:       '1px solid rgba(34, 211, 238, 0.12)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TestTube size={16} style={{ color: 'var(--accent-cyan)' }} />
                <span style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
                  Diabetes & Metabolic Screening
                </span>
              </div>
              {vitalsSummary.glucose_estimate && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  BG Avg: <strong style={{ color: 'var(--accent-cyan)' }}>{vitalsSummary.glucose_estimate.mean} mg/dL</strong>
                </span>
              )}
            </div>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--text-color)', margin: 0 }}>
              {analysis.diabetes_screening}
            </p>
          </div>
        )}
      </div>

      {/* ── Detailed Parameter Breakdown ── */}
      {analysis.parameter_breakdown && analysis.parameter_breakdown.length > 0 && (
        <div style={{ marginBottom: '1.75rem' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.75rem', fontWeight: 600 }}>
            Detailed Parameter Breakdown & Clinical Benchmarks
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {analysis.parameter_breakdown.map((param, i) => {
              const statusStr = (param.status || '').toLowerCase();
              const isNormal = statusStr.includes('normal') || statusStr.includes('optimal');
              const isWarning = statusStr.includes('high') || statusStr.includes('elevated') || statusStr.includes('low') || statusStr.includes('borderline');
              const badgeColor = isNormal ? 'var(--accent-emerald)' : isWarning ? 'var(--accent-amber)' : 'var(--accent-rose)';
              const badgeBg = isNormal ? 'rgba(16, 185, 129, 0.15)' : isWarning ? 'rgba(245, 158, 11, 0.15)' : 'rgba(244, 63, 94, 0.15)';

              return (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '1rem 1.25rem'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-color)', fontSize: '0.95rem' }}>{param.parameter}</span>
                      <span style={{ color: 'var(--accent-cyan)', fontSize: '0.9rem', fontWeight: 600 }}>{param.value}</span>
                      {param.clinical_reference && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '0.5rem' }}>
                          Ref: {param.clinical_reference}
                        </span>
                      )}
                    </div>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      padding: '0.2rem 0.6rem',
                      borderRadius: '50px',
                      textTransform: 'uppercase',
                      background: badgeBg,
                      color: badgeColor,
                      border: `1px solid ${badgeColor}`
                    }}>
                      {param.status}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
                    {param.analysis}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Diagnostic Next Steps & Recommendations Grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {/* Confirmatory Lab Tests */}
        {labTests.length > 0 && (
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <TestTube size={16} style={{ color: 'var(--accent-cyan)' }} />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
                Recommended Confirmatory Lab Tests
              </span>
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem', margin: 0, padding: 0 }}>
              {labTests.map((test, i) => (
                <li key={i} style={{
                  display: 'flex', gap: '0.6rem', alignItems: 'flex-start',
                  fontSize: '0.88rem', color: 'var(--text-color)', lineHeight: 1.4
                }}>
                  <CheckCircle2 size={14} style={{ color: 'var(--accent-cyan)', marginTop: '3px', flexShrink: 0 }} />
                  {test}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Holistic, Lifestyle & Ayurvedic Guidance */}
        {holistic.length > 0 && (
          <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <Sparkles size={16} style={{ color: 'var(--accent-emerald)' }} />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
                Ayurvedic & Holistic Guidance
              </span>
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem', margin: 0, padding: 0 }}>
              {holistic.map((item, i) => (
                <li key={i} style={{
                  display: 'flex', gap: '0.6rem', alignItems: 'flex-start',
                  fontSize: '0.88rem', color: 'var(--text-color)', lineHeight: 1.4
                }}>
                  <span style={{ color: 'var(--accent-emerald)', marginTop: '2px', flexShrink: 0 }}>✦</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── General Actionable Takeaways ── */}
      {recommendations.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ListChecks size={16} style={{ color: 'var(--accent-cyan)' }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>
              Actionable Recommendations
            </span>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', margin: 0, padding: 0 }}>
            {recommendations.map((rec, i) => (
              <li key={i} style={{
                display:    'flex',
                gap:        '0.75rem',
                alignItems: 'flex-start',
                fontSize:   '0.9rem',
                color:      'var(--text-color)',
                lineHeight: 1.5
              }}>
                <span style={{ color: 'var(--accent-cyan)', marginTop: '2px', flexShrink: 0 }}>→</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Research Disclaimer ── */}
      <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        <AlertCircle size={15} style={{ flexShrink: 0 }} />
        <p style={{ margin: 0, lineHeight: 1.5 }}>
          ⚠ This clinical interpretation is generated by Groq AI for research screening purposes only.
          It is not a clinical diagnosis. The MAX30102 sensor measures photoplethysmography; hemoglobin and blood glucose are research empirical approximations.
        </p>
      </div>
    </div>
  );
}
