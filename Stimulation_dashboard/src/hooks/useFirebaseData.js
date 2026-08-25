import { useState, useEffect } from 'react';
import { ref, onValue, query, limitToLast } from 'firebase/database';
import { db } from '../firebase';

export function useFirebaseData() {
  const [data, setData] = useState({
    temperature: 0,
    activity_x: 0,
    heart_rate: 0,
    spo2: 0,
    raw_ppg: 0,
    time: 0
  });
  const [history, setHistory] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Reference to the ayurai/device01/logs in Firebase RTDB
    const logsRef = ref(db, 'ayurai/device01/logs');
    
    // Query the last 20 inserted logs for the graph
    const latestLogQuery = query(logsRef, limitToLast(20));

    const unsubscribe = onValue(latestLogQuery, (snapshot) => {
      if (snapshot.exists()) {
        setIsConnected(true);
        
        const newHistory = [];
        snapshot.forEach((childSnapshot) => {
          const val = childSnapshot.val();
          // Format time for the chart (just HH:MM:SS)
          const date = new Date(val.time || Date.now());
          const timeString = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
          
          newHistory.push({
            ...val,
            formattedTime: timeString
          });
        });

        setHistory(newHistory);

        // The latest data is the last item in the array
        const latestData = newHistory[newHistory.length - 1];
        
        setData({
          temperature: latestData.temperature || 0,
          activity_x: latestData.activity_x || 0,
          heart_rate: latestData.heart_rate || 0,
          spo2: latestData.spo2 || 0,
          raw_ppg: latestData.raw_ppg || 0,
          time: latestData.time || 0
        });
        setError(null);
      } else {
        setIsConnected(false);
        setError("No data available in Firebase.");
      }
    }, (err) => {
      console.error("Firebase read error:", err);
      setError("Failed to connect to Firebase.");
      setIsConnected(false);
    });

    // Cleanup subscription on unmount
    return () => unsubscribe();
  }, []);

  return { data, history, isConnected, error };
}

