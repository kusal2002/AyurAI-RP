import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export function DataChart({ data }) {
  return (
    <div className="glass" style={{ padding: '1.5rem', marginTop: '2rem', height: '400px', display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ marginBottom: '1rem', color: '#f8fafc', fontWeight: 500 }}>Live Telemetry Trends</h3>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis 
              dataKey="formattedTime" 
              stroke="#94a3b8" 
              tick={{ fill: '#94a3b8', fontSize: 12 }} 
            />
            <YAxis 
              yAxisId="left" 
              stroke="#94a3b8" 
              tick={{ fill: '#94a3b8', fontSize: 12 }} 
              domain={['auto', 'auto']}
            />
            <YAxis 
              yAxisId="right" 
              orientation="right" 
              stroke="#94a3b8" 
              tick={{ fill: '#94a3b8', fontSize: 12 }} 
              domain={['auto', 'auto']}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              itemStyle={{ color: '#fff' }}
            />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            <Line 
              yAxisId="left" 
              type="monotone" 
              dataKey="heart_rate" 
              name="Heart Rate (bpm)" 
              stroke="#ef4444" 
              strokeWidth={3}
              dot={{ r: 4, strokeWidth: 2 }}
              activeDot={{ r: 6 }} 
              isAnimationActive={false}
            />
            <Line 
              yAxisId="left" 
              type="monotone" 
              dataKey="spo2" 
              name="SpO2 (%)" 
              stroke="#3b82f6" 
              strokeWidth={3}
              dot={{ r: 4, strokeWidth: 2 }} 
              isAnimationActive={false}
            />
            <Line 
              yAxisId="right" 
              type="monotone" 
              dataKey="temperature" 
              name="Temperature (°C)" 
              stroke="#f59e0b" 
              strokeWidth={3}
              dot={{ r: 4, strokeWidth: 2 }} 
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
