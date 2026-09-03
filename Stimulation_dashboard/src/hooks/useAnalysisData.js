import { useState, useEffect } from 'react';
import { ref, onValue, query, limitToLast } from 'firebase/database';
import { db } from '../firebase';

/**
 * Subscribes to the latest Gemini AI analysis result from Firebase.
 * The backend writes to /ayurai/analysis/device01 after each analysis.
 */
export function useAnalysisData(deviceId = 'device01') {
  const [analysis, setAnalysis] = useState(null);
  const [hasAnalysis, setHasAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  useEffect(() => {
    const analysisRef = ref(db, `ayurai/analysis/${deviceId}`);
    const latestQuery = query(analysisRef, limitToLast(1));

    const unsubscribe = onValue(latestQuery, (snapshot) => {
      if (snapshot.exists()) {
        const records = snapshot.val();
        // Firebase push IDs are keyed — grab the single value
        const latest = Object.values(records)[0];
        setAnalysis(latest);
        setHasAnalysis(true);
        setAnalysisError(null);
      } else {
        setHasAnalysis(false);
        setAnalysis(null);
      }
    }, (err) => {
      console.error('Analysis read error:', err);
      setAnalysisError('Failed to load analysis.');
    });

    return () => unsubscribe();
  }, [deviceId]);

  return { analysis, hasAnalysis, analysisError };
}
