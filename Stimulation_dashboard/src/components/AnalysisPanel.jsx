import React, { useState } from 'react';
import { Brain, ShieldCheck, AlertTriangle, AlertOctagon, ListChecks, Loader, Activity, AlertCircle } from 'lucide-react';

const RISK_CONFIG = {
  low:      { color: 'var(--accent-emerald)', glow: 'var(--accent-emerald-glow)', Icon: ShieldCheck,    label: 'Low Risk'      },
  moderate: { color: 'var(--accent-amber)',   glow: 'var(--accent-amber-glow)',   Icon: AlertTriangle,  label: 'Moderate Risk' },
  high:     { color: 'var(--accent-rose)',    glow: 'var(--accent-rose-glow)',    Icon: AlertOctagon,   label: 'High Risk'     }
};

/**
 * AnalysisPanel — Displays the latest Groq AI interpretation
 * from the AyurAI backend.
 *
 * Shows: risk level badge, physiological summary,
 * anemia screening text, confidence score, and recommendations.
 */
export function AnalysisPanel({ analysis, hasAnalysis, analysisError }) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const triggerAnalysis = async () => {
    setIsAnalyzing(true);
    try {
      await fetch('http://localhost:3000/api/analyze/device01', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      // The Firebase hook will automatically pick up the new analysis
    } catch (err) {
      console.error("Analysis trigger failed:", err);
      alert("Failed to reach backend. Make sure it is running on port 3000.");
    } finally {
      // Add a slight delay to allow Firebase to sync before stopping the spinner
      setTimeout(() => setIsAnalyzing(false), 2000);
    }
  };
  // ── Not yet analysed ──
  if (!hasAnalysis && !analysisError) {
    return (
      <div className="glass" style={{ padding: '2rem', marginTop: '1.5rem', textAlign: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', color: 'var(--text-muted)' }}>
          <Brain size={40} style={{ opacity: 0.4 }} />
          <div>
            <p style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--text-color)', marginBottom: '0.5rem' }}>
              Awaiting AI Analysis
            </p>
            <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: '1.6' }}>
              Once sensor data is streaming, click the button below to trigger the Groq AI interpretation.
            </p>
            <button 
              onClick={triggerAnalysis} 
              disabled={isAnalyzing}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                background: 'var(--accent-cyan)', color: '#000',
                border: 'none', padding: '0.75rem 1.5rem', borderRadius: '50px',
                fontWeight: 600, cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                opacity: isAnalyzing ? 0.7 : 1,
                boxShadow: '0 0 12px var(--accent-cyan-glow)'
              }}
            >
              {isAnalyzing ? <Loader size={18} className="spin" /> : <Activity size={18} />}
              {isAnalyzing ? 'Analyzing...' : 'Run AI Analysis'}
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
        <p style={{ color: 'var(--accent-rose)', fontWeight: 500 }}>⚠ {analysisError}</p>
      </div>
    );
  }

  const riskKey    = (analysis.risk_level || 'low').toLowerCase();
  const riskConf   = RISK_CONFIG[riskKey] || RISK_CONFIG.low;
  const { Icon: RiskIcon, color: riskColor, glow: riskGlow, label: riskLabel } = riskConf;

  const confidence    = analysis.confidence ?? 0;
  const confPercent   = Math.round(confidence * 100);
  const recommendations = analysis.recommendations || [];

  return (
    <div
      className="glass"
      style={{
        padding:    '2rem',
        marginTop:  '1.5rem',
        background: `radial-gradient(circle at 0% 100%, ${riskGlow} 0%, rgba(15,15,20,0.6) 50%)`
      }}
    >
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Brain style={{ color: 'var(--accent-cyan)' }} size={24} />
          <h3 style={{ fontWeight: 600, fontSize: '1.25rem', margin: 0 }}>Groq AI Interpretation</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Trigger Button */}
          <button 
            onClick={triggerAnalysis} 
            disabled={isAnalyzing}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              background: 'transparent', color: 'var(--text-color)',
              border: '1px solid rgba(255,255,255,0.2)', padding: '0.4rem 1rem', borderRadius: '50px',
              fontSize: '0.85rem', cursor: isAnalyzing ? 'not-allowed' : 'pointer',
              opacity: isAnalyzing ? 0.6 : 1, transition: 'all 0.2s'
            }}
          >
            {isAnalyzing ? <Loader size={14} className="spin" /> : <Activity size={14} />}
            {isAnalyzing ? 'Updating...' : 'Re-Analyze'}
          </button>

        {/* Risk Badge */}
        <div style={{
          display:      'flex',
          alignItems:   'center',
          gap:          '0.5rem',
          padding:      '0.4rem 1rem',
          borderRadius: '50px',
          background:   `rgba(${riskKey === 'low' ? '16,185,129' : riskKey === 'moderate' ? '245,158,11' : '244,63,94'}, 0.15)`,
          border:       `1px solid ${riskColor}`,
          boxShadow:    `0 0 12px ${riskGlow}`
        }}>
          <RiskIcon size={16} style={{ color: riskColor }} />
          <span style={{ color: riskColor, fontWeight: 600, fontSize: '0.9rem' }}>{riskLabel}</span>
        </div>
      </div>
      </div>

      {/* ── Confidence Bar ── */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Interpretation Confidence</span>
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

      {/* ── Physiological Summary ── */}
      <div style={{ marginBottom: '1.25rem' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem' }}>
          Physiological Summary
        </p>
        <p style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-color)' }}>
          {analysis.physiological_summary}
        </p>
      </div>

      {/* ── Anemia Screening ── */}
      <div style={{
        padding:      '1rem',
        borderRadius: '12px',
        background:   'rgba(255,255,255,0.04)',
        border:       '1px solid rgba(255,255,255,0.06)',
        marginBottom: '1rem'
      }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem' }}>
          Anemia Screening
        </p>
        <p style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-color)' }}>
          {analysis.anemia_screening}
        </p>
      </div>

      {/* ── Diabetes & Blood Sugar Screening ── */}
      {analysis.diabetes_screening && (
        <div style={{
          padding:      '1rem',
          borderRadius: '12px',
          background:   'rgba(255,255,255,0.04)',
          border:       '1px solid rgba(255,255,255,0.06)',
          marginBottom: '1.5rem'
        }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem' }}>
            Diabetes & Blood Sugar Screening
          </p>
          <p style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--text-color)' }}>
            {analysis.diabetes_screening}
          </p>
        </div>
      )}

      {/* ── Detailed Parameter Breakdown ── */}
      {analysis.parameter_breakdown && analysis.parameter_breakdown.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.75rem' }}>
            Detailed Parameter Breakdown
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {analysis.parameter_breakdown.map((param, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                padding: '1rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-color)', marginRight: '0.5rem' }}>{param.parameter}</span>
                    <span style={{ color: 'var(--accent-cyan)', fontSize: '0.9rem', fontWeight: 500 }}>{param.value}</span>
                  </div>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.6rem',
                    borderRadius: '50px',
                    textTransform: 'uppercase',
                    background: param.status.toLowerCase().includes('normal') || param.status.toLowerCase().includes('optimal') ? 'rgba(16, 185, 129, 0.2)' : 
                                param.status.toLowerCase().includes('high') || param.status.toLowerCase().includes('elevated') || param.status.toLowerCase().includes('low') ? 'rgba(245, 158, 11, 0.2)' : 
                                'rgba(244, 63, 94, 0.2)',
                    color: param.status.toLowerCase().includes('normal') || param.status.toLowerCase().includes('optimal') ? 'var(--accent-emerald)' : 
                           param.status.toLowerCase().includes('high') || param.status.toLowerCase().includes('elevated') || param.status.toLowerCase().includes('low') ? 'var(--accent-amber)' : 
                           'var(--accent-rose)',
                  }}>
                    {param.status}
                  </span>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
                  {param.analysis}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recommendations ── */}
      {recommendations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ListChecks size={16} style={{ color: 'var(--accent-cyan)' }} />
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Recommendations
            </p>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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
        <AlertCircle size={14} />
        <p style={{ margin: 0, lineHeight: 1.5 }}>
          ⚠ This interpretation is generated by Groq AI for research screening purposes only.
          It is not a clinical diagnosis. The MAX30102 sensor does not directly measure hemoglobin or blood glucose.
        </p>
      </div>
    </div>
  );
}
