import { useState, useRef, useEffect, useCallback } from 'react';

export function useSerialPort() {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState({ sensor1: 0, sensor2: 0, sensor3: 0 }); // Example default data
  const [error, setError] = useState(null);
  
  const portRef = useRef(null);
  const readerRef = useRef(null);
  const isReadingRef = useRef(false);

  // Parse incoming data. Assuming JSON or simple comma separated values
  const handleIncomingData = useCallback((chunk) => {
    try {
      // Try to parse as JSON first if Arduino sends JSON: {"sensor1": 23, ...}
      const parsed = JSON.parse(chunk);
      setData(prev => ({ ...prev, ...parsed }));
    } catch (e) {
      // Fallback: assume comma separated "val1,val2,val3"
      const parts = chunk.split(',');
      if (parts.length >= 3) {
        setData({
          sensor1: parseFloat(parts[0]) || 0,
          sensor2: parseFloat(parts[1]) || 0,
          sensor3: parseFloat(parts[2]) || 0,
        });
      }
    }
  }, []);

  const connect = async () => {
    if (!('serial' in navigator)) {
      setError('Web Serial API is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    try {
      // Request a port and open a connection.
      const port = await navigator.serial.requestPort();
      await port.open({ baudRate: 9600 }); // standard Arduino baud rate
      portRef.current = port;
      
      setIsConnected(true);
      setError(null);
      isReadingRef.current = true;
      
      readLoop();
    } catch (err) {
      console.error('Error connecting to serial port:', err);
      setError(err.message || 'Failed to connect to device');
    }
  };

  const readLoop = async () => {
    const port = portRef.current;
    if (!port) return;

    // Web Serial uses Streams
    const textDecoder = new TextDecoderStream();
    const readableStreamClosed = port.readable.pipeTo(textDecoder.writable);
    const reader = textDecoder.readable.getReader();
    readerRef.current = reader;

    let buffer = '';

    try {
      while (isReadingRef.current) {
        const { value, done } = await reader.read();
        if (done) {
          // Reader has been canceled.
          break;
        }
        if (value) {
          buffer += value;
          // Split by newline (Arduino typically uses Serial.println)
          const lines = buffer.split('\n');
          // The last element is an incomplete line, keep it in the buffer
          buffer = lines.pop();

          lines.forEach(line => {
            const trimmed = line.trim();
            if (trimmed) {
              handleIncomingData(trimmed);
            }
          });
        }
      }
    } catch (error) {
      console.error('Read error:', error);
      setError('Connection lost or read error.');
      setIsConnected(false);
    } finally {
      reader.releaseLock();
    }
  };

  const disconnect = async () => {
    isReadingRef.current = false;
    if (readerRef.current) {
      await readerRef.current.cancel();
      readerRef.current = null;
    }
    
    if (portRef.current) {
      try {
        await portRef.current.close();
      } catch (e) {
        console.error('Error closing port:', e);
      }
      portRef.current = null;
    }
    setIsConnected(false);
  };

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (isConnected) {
        disconnect();
      }
    };
  }, [isConnected]);

  // For demonstration/testing without an Arduino:
  const simulateData = () => {
    setIsConnected(true);
    const interval = setInterval(() => {
      setData({
        sensor1: Math.floor(Math.random() * 100),
        sensor2: Math.floor(Math.random() * 100),
        sensor3: Math.floor(Math.random() * 100),
      });
    }, 1000);
    return () => clearInterval(interval);
  };

  return { isConnected, data, error, connect, disconnect, simulateData };
}
