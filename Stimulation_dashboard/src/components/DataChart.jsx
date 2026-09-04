import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="glass" style={{ padding: '1rem', border: '1px solid rgba(255,255,255,0.1)', minWidth: '180px' }}>
        <p style={{ color: 'var(--text-muted)', marginBottom: '0.5rem', fontSize: '0.9rem' }}>{label}</p>
        {payload.map((entry, index) => (
          <div key={index} style={{ display: 'flex', justifyContent: 'space-between', margin: '0.25rem 0' }}>
            <span style={{ color: entry.color, fontWeight: 500 }}>{entry.name}</span>
            <span style={{ color: '#fff', fontWeight: 600 }}>{entry.value.toFixed(1)}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export function DataChart({ data }) {
  return (
    <div className="glass" style={{ padding: '2rem', height: '450px', display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ marginBottom: '1.5rem', color: 'var(--text-color)', fontWeight: 600, fontSize: '1.25rem' }}>Live Telemetry Trends</h3>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
            <defs>
              <linearGradient id="colorHeart" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-rose)" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="var(--accent-rose)" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorSpO2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-cyan)" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="var(--accent-cyan)" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-amber)" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="var(--accent-amber)" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis 
              dataKey="formattedTime" 
              stroke="var(--text-muted)" 
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }} 
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
            />
            <YAxis 
              yAxisId="left" 
              stroke="var(--text-muted)" 
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }} 
              domain={['auto', 'auto']}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              yAxisId="right" 
              orientation="right" 
              stroke="var(--text-muted)" 
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }} 
              domain={['auto', 'auto']}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1, strokeDasharray: '5 5' }} />
            <Legend wrapperStyle={{ paddingTop: '20px' }} iconType="circle" />
            <Area 
              yAxisId="left" 
              type="monotone" 
              dataKey="heart_rate" 
              name="Heart Rate (bpm)" 
              stroke="var(--accent-rose)" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorHeart)"
              isAnimationActive={true}
              animationDuration={500}
            />
            <Area 
              yAxisId="left" 
              type="monotone" 
              dataKey="spo2" 
              name="SpO2 (%)" 
              stroke="var(--accent-cyan)" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorSpO2)"
              isAnimationActive={true}
              animationDuration={500}
            />
            <Area 
              yAxisId="right" 
              type="monotone" 
              dataKey="body_temperature" 
              name="Temp (°C)" 
              stroke="var(--accent-amber)" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorTemp)"
              isAnimationActive={true}
              animationDuration={500}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
