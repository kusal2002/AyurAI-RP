/**
 * AyurAI Backend — Express Server
 *
 * Architecture:
 *   ESP32 → Firebase → POST /api/analyze/:deviceId
 *                           ↓
 *                    PPG Feature Extraction
 *                           ↓
 *                        Groq API
 *                           ↓
 *               Firebase /ayurai/analysis/device01
 *                           ↓
 *                      Dashboard / App
 *
 * Routes:
 *   POST /api/analyze/:deviceId  — Analyze latest sensor data
 *   GET  /api/latest/:deviceId   — Get latest analysis result
 *   GET  /health                 — Health check
 */

require("dotenv").config();

const express      = require("express");
const admin        = require("firebase-admin");
const { analyzeAyurAI }     = require("./services/groq");
const { extractPPGFeatures } = require("./services/ppgFeatures");

// =====================================================
// Express
// =====================================================

const app = express();
app.use(express.json());

// CORS for development (dashboard at localhost:5173)
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "Content-Type");
  next();
});

// =====================================================
// Firebase Admin SDK
// =====================================================

// Check for service account file before loading
const fs = require("fs");
const SERVICE_ACCOUNT_PATH = "./firebase-service-account.json";

if (!fs.existsSync(SERVICE_ACCOUNT_PATH)) {
  console.error("\n=====================================");
  console.error("  ERROR: Firebase service account not found!");
  console.error("=====================================");
  console.error("\nTo fix this:");
  console.error("  1. Go to https://console.firebase.google.com");
  console.error(`  2. Open your project: ayurai-39fff`);
  console.error("  3. Click the gear icon → Project Settings");
  console.error("  4. Go to the 'Service accounts' tab");
  console.error("  5. Click 'Generate new private key' → Download JSON");
  console.error(`  6. Rename the file to: firebase-service-account.json`);
  console.error(`  7. Place it at: F:\\SLIIT\\SLIIT\\Research\\AyurAI_Stimulation_Prototype\\ayurai-backend\\firebase-service-account.json`);
  console.error("\nThen run: node server.js\n");
  process.exit(1);
}

const serviceAccount = require(SERVICE_ACCOUNT_PATH);

admin.initializeApp({
  credential:  admin.credential.cert(serviceAccount),
  databaseURL: process.env.FIREBASE_DATABASE_URL
});

const db = admin.database();

const PORT = process.env.PORT || 3000;

// =====================================================
// HEALTH CHECK
// =====================================================

app.get("/health", (req, res) => {
  res.json({
    status:    "ok",
    service:   "AyurAI Backend",
    timestamp: new Date().toISOString()
  });
});

// =====================================================
// Decode millisecond UTC timestamp from Firebase push key
function decodePushId(id) {
  if (!id || typeof id !== 'string' || id.length < 8) return null;
  const chars = '-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz';
  let time = 0;
  for (let i = 0; i < 8; i++) {
    const c = id.charAt(i);
    const index = chars.indexOf(c);
    if (index === -1) return null;
    time = time * 64 + index;
  }
  return time;
}

// Statistical calculation helpers
function calcMean(arr) {
  if (!arr || arr.length === 0) return 0;
  return parseFloat((arr.reduce((s, v) => s + v, 0) / arr.length).toFixed(1));
}

function calcStdDev(arr) {
  if (!arr || arr.length < 2) return 0;
  const m = calcMean(arr);
  const variance = arr.reduce((s, v) => s + Math.pow(v - m, 2), 0) / arr.length;
  return parseFloat(Math.sqrt(variance).toFixed(1));
}

// =====================================================
// POST /api/analyze/:deviceId
//
// Accepts or queries all recorded data from the last 2 minutes,
// computes temporal aggregations (HR, SpO2, Temp, Hb, Glucose, PI),
// extracts multi-window PPG features, calls Groq AI for an
// advanced diagnostic interpretation, and stores the result.
// =====================================================

app.post("/api/analyze/:deviceId", async (req, res) => {
  const { deviceId } = req.params;

  try {
    console.log(`\n[AyurAI] Analyzing 2-minute recorded session for device: ${deviceId}`);

    let sensorRecords = [];

    // Check if client supplied 2-minute records array
    if (req.body && Array.isArray(req.body.records) && req.body.records.length > 0) {
      sensorRecords = req.body.records;
      console.log(`[AyurAI] Received ${sensorRecords.length} records in request body.`);
    } else if (req.body && req.body.heart_rate) {
      // Single record provided in body (testing or fallback)
      sensorRecords = [req.body];
      console.log("[AyurAI] Received single record in request body.");
    } else {
      // Query Firebase for the last 120 records (up to 2 minutes)
      console.log("[AyurAI] Fetching up to 2 minutes of records from Firebase...");

      const snapshot = await db
        .ref(`ayurai/sensor_data/${deviceId}`)
        .orderByKey()
        .limitToLast(120)
        .once("value");

      if (!snapshot.exists()) {
        return res.status(404).json({
          success: false,
          error: `No sensor data found for device: ${deviceId}`
        });
      }

      const recordsObj = snapshot.val();
      const keys = Object.keys(recordsObj);

      const allRecords = keys.map((key) => {
        const item = recordsObj[key];
        const pushTime = decodePushId(key);
        const effectiveTime = (item.timestamp && item.timestamp > 1000000000000)
          ? item.timestamp
          : (pushTime || Date.now());

        return {
          ...item,
          _key: key,
          effectiveTime
        };
      });

      // Filter last 2 minutes (120,000 ms)
      if (allRecords.length > 0) {
        const latest = allRecords[allRecords.length - 1];
        if (latest.effectiveTime > 1000000000000) {
          sensorRecords = allRecords.filter(r => (latest.effectiveTime - r.effectiveTime) <= 120000);
        } else if (latest.timestamp != null) {
          sensorRecords = allRecords.filter(r => (latest.timestamp - r.timestamp) <= 120000);
        }
      }

      if (!sensorRecords || sensorRecords.length === 0) {
        sensorRecords = allRecords.slice(-20);
      }

      console.log(`[AyurAI] Fetched ${sensorRecords.length} records within 2-minute window from Firebase.`);
    }

    if (sensorRecords.length === 0) {
      return res.status(404).json({
        success: false,
        error: `No valid sensor records available in the last 2 minutes for ${deviceId}`
      });
    }

    // --- Process Each Record & Extract Features ---
    const hrValues = [];
    const spo2Values = [];
    const tempValues = [];
    const hbValues = [];
    const glucoseValues = [];
    const piValues = [];
    const ratioRValues = [];
    const pulseAmpValues = [];
    let validContactCount = 0;

    sensorRecords.forEach((record) => {
      // HR
      if (record.heart_rate != null && record.heart_rate >= 40 && record.heart_rate <= 220) {
        hrValues.push(record.heart_rate);
      }
      // SpO2
      if (record.spo2 != null && record.spo2 >= 70 && record.spo2 <= 100) {
        spo2Values.push(record.spo2);
      }
      // Temp
      if (record.body_temperature != null && record.body_temperature >= 25 && record.body_temperature <= 45) {
        tempValues.push(record.body_temperature);
      }

      // PPG feature extraction
      const feat = extractPPGFeatures(
        record.ppg_ir_window || [],
        record.ppg_red_window || []
      );

      if (feat.valid) {
        validContactCount++;

        if (feat.perfusion_index > 0) {
          piValues.push(feat.perfusion_index);
        }
        if (feat.ratio_r > 0) {
          ratioRValues.push(feat.ratio_r);

          // Empirical Hemoglobin: Hb ≈ 17.5 - (3.5 * ratio_r)
          let calcHb = 17.5 - (3.5 * feat.ratio_r);
          calcHb = Math.max(8.0, Math.min(18.0, calcHb));
          hbValues.push(parseFloat(calcHb.toFixed(1)));
        }
        if (feat.pulse_amp > 0) {
          pulseAmpValues.push(feat.pulse_amp);
        }

        // Empirical Glucose: BG ≈ 115 - (10 * PI) + (0.4 * HR)
        if (feat.perfusion_index > 0 && record.heart_rate) {
          let calcGlucose = 115 - (10 * feat.perfusion_index) + (0.4 * record.heart_rate);
          calcGlucose = Math.max(60, Math.min(250, calcGlucose));
          glucoseValues.push(Math.round(calcGlucose));
        }
      }
    });

    // --- Determine Heart Rate Trend ---
    let hrTrend = "stable";
    if (hrValues.length >= 4) {
      const firstHalf = hrValues.slice(0, Math.floor(hrValues.length / 2));
      const secondHalf = hrValues.slice(Math.floor(hrValues.length / 2));
      const diff = calcMean(secondHalf) - calcMean(firstHalf);
      if (diff > 4) hrTrend = "rising";
      else if (diff < -4) hrTrend = "falling";
      else if (calcStdDev(hrValues) > 6) hrTrend = "fluctuating";
    }

    // --- Build 2-Minute Session Summary ---
    const vitals_summary_2min = {
      heart_rate: hrValues.length ? {
        mean: calcMean(hrValues),
        min: Math.min(...hrValues),
        max: Math.max(...hrValues),
        stdDev: calcStdDev(hrValues),
        trend: hrTrend
      } : null,
      spo2: spo2Values.length ? {
        mean: calcMean(spo2Values),
        min: Math.min(...spo2Values),
        max: Math.max(...spo2Values),
        desaturation_events: spo2Values.filter(v => v < 95).length
      } : null,
      body_temperature: tempValues.length ? {
        mean: calcMean(tempValues),
        min: Math.min(...tempValues),
        max: Math.max(...tempValues)
      } : null,
      hb_estimate: hbValues.length ? {
        mean: calcMean(hbValues),
        min: Math.min(...hbValues),
        max: Math.max(...hbValues)
      } : null,
      glucose_estimate: glucoseValues.length ? {
        mean: Math.round(calcMean(glucoseValues)),
        min: Math.min(...glucoseValues),
        max: Math.max(...glucoseValues)
      } : null,
      perfusion_index: piValues.length ? {
        mean: calcMean(piValues),
        min: parseFloat(Math.min(...piValues).toFixed(2)),
        max: parseFloat(Math.max(...piValues).toFixed(2))
      } : null,
      ratio_r: ratioRValues.length ? {
        mean: parseFloat(calcMean(ratioRValues).toFixed(4)),
        min: parseFloat(Math.min(...ratioRValues).toFixed(4)),
        max: parseFloat(Math.max(...ratioRValues).toFixed(4))
      } : null,
      pulse_amplitude: pulseAmpValues.length ? {
        mean: Math.round(calcMean(pulseAmpValues)),
        min: Math.min(...pulseAmpValues),
        max: Math.max(...pulseAmpValues)
      } : null
    };

    const session = {
      duration_seconds: 120,
      sample_count: sensorRecords.length,
      valid_sample_count: validContactCount,
      signal_quality_percent: sensorRecords.length > 0
        ? Math.round((validContactCount / sensorRecords.length) * 100)
        : 100
    };

    const latestRecord = sensorRecords[sensorRecords.length - 1];

    console.log("[AyurAI] 2-Minute Session Summary:", JSON.stringify({ session, vitals_summary_2min }, null, 2));

    // --- Call Groq AI ---
    console.log("[AyurAI] Calling Groq with 2-minute session data...");

    const groqResult = await analyzeAyurAI({
      session,
      vitals_summary_2min,
      latest: latestRecord,
      // Backward compatibility fields
      heart_rate: vitals_summary_2min.heart_rate?.mean ?? latestRecord.heart_rate,
      spo2: vitals_summary_2min.spo2?.mean ?? latestRecord.spo2,
      body_temperature: vitals_summary_2min.body_temperature?.mean ?? latestRecord.body_temperature,
      hb_estimate: vitals_summary_2min.hb_estimate?.mean,
      glucose_estimate: vitals_summary_2min.glucose_estimate?.mean,
      ppg_features: {
        perfusion_index: vitals_summary_2min.perfusion_index?.mean ?? 0,
        ratio_r: vitals_summary_2min.ratio_r?.mean ?? 0,
        pulse_amp: vitals_summary_2min.pulse_amplitude?.mean ?? 0,
        valid: validContactCount > 0
      }
    });

    console.log("[AyurAI] Groq AI Diagnostic Result received.");

    // --- Save Analysis to Firebase ---
    const analysisRef = db.ref(`ayurai/analysis/${deviceId}`);
    const newAnalysisEntry = analysisRef.push();

    await newAnalysisEntry.set({
      ...groqResult,
      session,
      vitals_summary_2min,
      device_id: deviceId,
      heart_rate: vitals_summary_2min.heart_rate?.mean ?? latestRecord.heart_rate ?? null,
      spo2: vitals_summary_2min.spo2?.mean ?? latestRecord.spo2 ?? null,
      body_temperature: vitals_summary_2min.body_temperature?.mean ?? latestRecord.body_temperature ?? null,
      hb_estimate: vitals_summary_2min.hb_estimate?.mean ?? null,
      glucose_estimate: vitals_summary_2min.glucose_estimate?.mean ?? null,
      timestamp: Date.now()
    });

    console.log(`[AyurAI] Saved analysis to Firebase: ayurai/analysis/${deviceId}/${newAnalysisEntry.key}`);

    // --- Respond ---
    res.json({
      success: true,
      device_id: deviceId,
      analysis: groqResult,
      session,
      vitals_summary_2min
    });

  } catch (error) {
    console.error("[AyurAI] Error in 2-minute analysis:", error.message);
    res.status(500).json({
      success: false,
      error: "AI analysis failed",
      detail: error.message
    });
  }
});

// =====================================================
// GET /api/latest/:deviceId
//
// Returns the most recent analysis result from Firebase.
// The dashboard can poll this to display Groq output.
// =====================================================

app.get("/api/latest/:deviceId", async (req, res) => {
  const { deviceId } = req.params;

  try {
    const snapshot = await db
      .ref(`ayurai/analysis/${deviceId}`)
      .orderByKey()
      .limitToLast(1)
      .once("value");

    if (!snapshot.exists()) {
      return res.status(404).json({
        success: false,
        error:   `No analysis found for device: ${deviceId}`
      });
    }

    const records = snapshot.val();
    const latest  = Object.values(records)[0];

    res.json({ success: true, device_id: deviceId, analysis: latest });

  } catch (error) {
    console.error("[AyurAI] Error fetching latest:", error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// =====================================================
// START SERVER
// =====================================================

app.listen(PORT, () => {
  console.log("=====================================");
  console.log(`  AyurAI Backend running on port ${PORT}`);
  console.log("=====================================");
  console.log(`  Health:  http://localhost:${PORT}/health`);
  console.log(`  Analyze: POST http://localhost:${PORT}/api/analyze/device01`);
  console.log(`  Latest:  GET  http://localhost:${PORT}/api/latest/device01`);
  console.log("=====================================\n");
});
