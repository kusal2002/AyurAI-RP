import { useState, useEffect } from 'react';
import { ref, onValue, query, limitToLast } from 'firebase/database';
import { db } from '../firebase';

export function useFirebaseData() {
  const [data, setData] = useState({
    heart_rate: null,
    spo2:       null,
    raw_ir:     null,
    raw_red:    null,
    hb_estimate: null,
    glucose_estimate: null,
    timestamp:  null
  });
  const [history, setHistory] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Updated path: /ayurai/sensor_data/device01 (matches new firmware + Firebase structure)
    const sensorRef = ref(db, 'ayurai/sensor_data/device01');

    // Query the last 20 records for the chart
    const latestQuery = query(sensorRef, limitToLast(20));

    const unsubscribe = onValue(latestQuery, (snapshot) => {
      if (snapshot.exists()) {
        setIsConnected(true);

        const newHistory = [];

        snapshot.forEach((childSnapshot) => {
          const val = childSnapshot.val();

          // Format timestamp for chart axis
          const date = val.timestamp
            ? new Date(val.timestamp)
            : new Date();

          const timeString = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;

          newHistory.push({
            ...val,
            formattedTime: timeString
          });
        });

        setHistory(newHistory);

        // Latest data is the last item
        const latest = newHistory[newHistory.length - 1];

        // --- Calculate Live Empirical Estimates ---
        let liveHb = null;
        let liveGlucose = null;

        const irWin = latest.ppg_ir_window || [];
        const redWin = latest.ppg_red_window || [];

        if (irWin.length > 0 && redWin.length > 0) {
          const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
          const stdDev = (arr) => {
            const m = mean(arr);
            return Math.sqrt(arr.reduce((a, b) => a + Math.pow(b - m, 2), 0) / arr.length);
          };

          const ir_dc = mean(irWin);
          const ir_ac = stdDev(irWin);
          const red_dc = mean(redWin);
          const red_ac = stdDev(redWin);

          if (ir_dc > 500 && red_dc > 0) { // Valid signal check
            const ratio_r = (red_ac / red_dc) / (ir_ac / ir_dc);
            
            // Hb calculation
            if (ratio_r > 0) {
              let calcHb = 17.5 - (3.5 * ratio_r);
              calcHb = Math.max(8.0, Math.min(18.0, calcHb));
              liveHb = parseFloat(calcHb.toFixed(1));
            }

            // Glucose calculation
            const ir_peak = Math.max(...irWin);
            const ir_trough = Math.min(...irWin);
            const pulse_amp = ir_peak - ir_trough;
            const perfusion_index = (pulse_amp / ir_dc) * 100;

            if (perfusion_index > 0 && latest.heart_rate) {
              let calcGlucose = 115 - (10 * perfusion_index) + (0.4 * latest.heart_rate);
              calcGlucose = Math.max(60, Math.min(250, calcGlucose));
              liveGlucose = Math.round(calcGlucose);
            }
          }
        }

        setData({
          heart_rate: latest.heart_rate ?? null,
          spo2:       latest.spo2       ?? null,
          raw_ir:     latest.raw_ir     ?? null,
          raw_red:    latest.raw_red    ?? null,
          hb_estimate: liveHb,
          glucose_estimate: liveGlucose,
          timestamp:  latest.timestamp  ?? null
        });

        setError(null);
      } else {
        setIsConnected(false);
        setError('No sensor data yet. Flash the firmware and place your finger on the MAX30102.');
      }
    }, (err) => {
      console.error('Firebase read error:', err);
      setError('Failed to connect to Firebase.');
      setIsConnected(false);
    });

    return () => unsubscribe();
  }, []);

  return { data, history, isConnected, error };
}
