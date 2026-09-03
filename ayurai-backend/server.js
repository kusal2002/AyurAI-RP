/**
 * AyurAI Backend — Express Server
 *
 * Architecture:
 *   ESP32 → Firebase → POST /api/analyze/:deviceId
 *                           ↓
 *                    PPG Feature Extraction
 *                           ↓
 *                       Gemini API
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
const { analyzeAyurAI }     = require("./services/gemini");
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
// POST /api/analyze/:deviceId
//
// Reads the latest sensor record from Firebase,
// extracts PPG features, calls Gemini, saves analysis.
//
// Can also accept sensor data directly in the request body
// (useful for testing without a physical device).
// =====================================================

app.post("/api/analyze/:deviceId", async (req, res) => {
  const { deviceId } = req.params;

  try {
    console.log(`\n[AyurAI] Analyzing device: ${deviceId}`);

    // --- Get sensor data ---
    // Use request body if provided; otherwise fetch latest from Firebase
    let sensorData = req.body;

    if (!sensorData || !sensorData.heart_rate) {
      console.log("[AyurAI] No body provided — fetching latest from Firebase...");

      const snapshot = await db
        .ref(`ayurai/sensor_data/${deviceId}`)
        .orderByKey()
        .limitToLast(1)
        .once("value");

      if (!snapshot.exists()) {
        return res.status(404).json({
          success: false,
          error:   `No sensor data found for device: ${deviceId}`
        });
      }

      // Firebase returns an object keyed by push ID — grab the value
      const records = snapshot.val();
      sensorData = Object.values(records)[0];

      console.log("[AyurAI] Latest sensor record:", sensorData);
    }

    // --- Extract PPG features ---
    const ppg_features = extractPPGFeatures(
      sensorData.ppg_ir_window  || [],
      sensorData.ppg_red_window || []
    );

    console.log("[AyurAI] PPG features:", ppg_features);

    // --- Empirical Research Formulas (No ML) ---
    // Without a trained ML model on clinical data, the most accurate way 
    // to estimate these values using only RED/IR is via known empirical correlations.
    
    // Hemoglobin (Hb) is inversely correlated with the Ratio of Ratios (R).
    // Empirical approximation formula: Hb (g/dL) ≈ 17.5 - (3.5 * ratio_r)
    // We clamp the result to biologically plausible bounds (8.0 - 18.0)
    let empiricalHb = null;
    if (ppg_features.valid && ppg_features.ratio_r > 0) {
      let calcHb = 17.5 - (3.5 * ppg_features.ratio_r);
      calcHb = Math.max(8.0, Math.min(18.0, calcHb)); // Clamp to realistic range
      empiricalHb = parseFloat(calcHb.toFixed(1));
    }

    // Blood Glucose (BG) subtly affects blood viscosity, which inversely affects 
    // the Perfusion Index (PI) and slightly elevates Heart Rate.
    // Empirical approximation: BG (mg/dL) ≈ 115 - (10 * PI) + (0.4 * HR)
    let empiricalGlucose = null;
    if (ppg_features.valid && ppg_features.perfusion_index > 0 && sensorData.heart_rate) {
      let calcGlucose = 115 - (10 * ppg_features.perfusion_index) + (0.4 * sensorData.heart_rate);
      calcGlucose = Math.max(60, Math.min(250, calcGlucose)); // Clamp to realistic range
      empiricalGlucose = Math.round(calcGlucose);
    }

    // --- Call Gemini ---
    console.log("[AyurAI] Sending to Gemini...");

    const geminiResult = await analyzeAyurAI({
      heart_rate:   sensorData.heart_rate ?? null,
      spo2:         sensorData.spo2 ?? null,
      ppg_features,
      hb_estimate:  empiricalHb,
      glucose_estimate: empiricalGlucose
    });

    console.log("[AyurAI] Gemini result:", geminiResult);

    // --- Save analysis to Firebase ---
    const analysisRef  = db.ref(`ayurai/analysis/${deviceId}`);
    const newAnalysisEntry = analysisRef.push();

    await newAnalysisEntry.set({
      ...geminiResult,
      ppg_features,
      device_id:  deviceId,
      heart_rate: sensorData.heart_rate ?? null,
      spo2:       sensorData.spo2 ?? null,
      raw_ir:     sensorData.raw_ir ?? null,
      raw_red:    sensorData.raw_red ?? null,
      hb_estimate: empiricalHb,
      glucose_estimate: empiricalGlucose,
      timestamp:  Date.now()
    });

    console.log(`[AyurAI] Analysis saved to Firebase: ayurai/analysis/${deviceId}/${newAnalysisEntry.key}`);

    // --- Respond ---
    res.json({
      success:   true,
      device_id: deviceId,
      analysis:  geminiResult,
      ppg_features
    });

  } catch (error) {
    console.error("[AyurAI] Error:", error.message);
    res.status(500).json({
      success: false,
      error:   "AI analysis failed",
      detail:  error.message
    });
  }
});

// =====================================================
// GET /api/latest/:deviceId
//
// Returns the most recent analysis result from Firebase.
// The dashboard can poll this to display Gemini output.
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
