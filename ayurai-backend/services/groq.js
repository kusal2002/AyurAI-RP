/**
 * AyurAI — Groq AI Interpretation Service
 *
 * Sends physiological sensor data + extracted PPG features to
 * the Groq API and returns a structured JSON interpretation.
 *
 * IMPORTANT:
 *   • Groq (LLaMA 3) is the INTERPRETATION layer, not the measurement layer.
 *   • It receives real HR, SpO2, and computed PPG features.
 *   • It does NOT claim to measure hemoglobin or glucose directly.
 *   • Hb/anemia estimates come from a separate trained ML model;
 *     Groq explains that model's output in human-readable form.
 */

const Groq = require("groq-sdk");
require("dotenv").config();

// The user saved the key as API_KEY in .env, so we read process.env.API_KEY
const groq = new Groq({
  apiKey: process.env.API_KEY
});

/**
 * Analyze 2-minute sensor data + temporal features using Groq.
 *
 * @param {object} data — Aggregated 2-minute session data + metrics
 * @returns {Promise<object>} Structured Groq clinical diagnostic interpretation
 */
async function analyzeAyurAI(data) {
  if (!process.env.API_KEY) {
    throw new Error("GROQ API KEY is missing in .env file");
  }

  const {
    session = {},
    vitals_summary_2min = {},
    latest = {},
    // Backward compatibility if single reading passed:
    heart_rate,
    spo2,
    body_temperature,
    ppg_features,
    hb_estimate,
    glucose_estimate
  } = data;

  const durationSec = session.duration_seconds || 120;
  const sampleCount = session.sample_count || 1;
  const signalQuality = session.signal_quality_percent != null ? `${session.signal_quality_percent}%` : "100%";

  const hrMean = vitals_summary_2min.heart_rate?.mean ?? heart_rate ?? "N/A";
  const hrRange = vitals_summary_2min.heart_rate ? `${vitals_summary_2min.heart_rate.min} - ${vitals_summary_2min.heart_rate.max} bpm (trend: ${vitals_summary_2min.heart_rate.trend || 'stable'}, HRV SD: ${vitals_summary_2min.heart_rate.stdDev || 0})` : `${hrMean} bpm`;

  const spo2Mean = vitals_summary_2min.spo2?.mean ?? spo2 ?? "N/A";
  const spo2Range = vitals_summary_2min.spo2 ? `${vitals_summary_2min.spo2.min} - ${vitals_summary_2min.spo2.max} % (desaturations: ${vitals_summary_2min.spo2.desaturation_events || 0})` : `${spo2Mean} %`;

  const tempMean = vitals_summary_2min.body_temperature?.mean ?? body_temperature ?? "N/A";
  const tempRange = vitals_summary_2min.body_temperature ? `${vitals_summary_2min.body_temperature.min} - ${vitals_summary_2min.body_temperature.max} °C` : `${tempMean} °C`;

  const hbMean = vitals_summary_2min.hb_estimate?.mean ?? hb_estimate ?? "N/A";
  const hbRange = vitals_summary_2min.hb_estimate ? `${vitals_summary_2min.hb_estimate.min} - ${vitals_summary_2min.hb_estimate.max} g/dL` : `${hbMean} g/dL`;

  const glucoseMean = vitals_summary_2min.glucose_estimate?.mean ?? glucose_estimate ?? "N/A";
  const glucoseRange = vitals_summary_2min.glucose_estimate ? `${vitals_summary_2min.glucose_estimate.min} - ${vitals_summary_2min.glucose_estimate.max} mg/dL` : `${glucoseMean} mg/dL`;

  const piMean = vitals_summary_2min.perfusion_index?.mean ?? ppg_features?.perfusion_index ?? "N/A";
  const piRange = vitals_summary_2min.perfusion_index ? `${vitals_summary_2min.perfusion_index.min} - ${vitals_summary_2min.perfusion_index.max} %` : `${piMean} %`;

  const ratioR = vitals_summary_2min.ratio_r?.mean ?? ppg_features?.ratio_r ?? "N/A";
  const pulseAmp = vitals_summary_2min.pulse_amplitude?.mean ?? ppg_features?.pulse_amp ?? "N/A";

  const prompt = `
You are the AI clinical interpretation engine of AyurAI — a non-invasive cardiovascular, anemia, and metabolic screening prototype using continuous optical photoplethysmography (MAX30102 RED/IR) on an ESP32-S3.

## MONITORING CONTEXT & CONSTRAINTS
1. You are analyzing a CONTINUOUS 2-MINUTE (${durationSec}-second) RECORDING WINDOW comprising ${sampleCount} recorded telemetry frames.
2. The MAX30102 measures heart rate, SpO2, and raw RED/IR optical absorption. Hemoglobin (Hb) and Blood Glucose (BG) are derived via validated empirical photoplethysmographic algorithms across the 2-minute window (filtering out single-sample motion artifacts).
3. This is a research screening prototype. Provide a thorough, clinical-grade diagnostic impression, risk stratification, and confirmatory laboratory test recommendations.

## 2-MINUTE SESSION TELEMETRY SUMMARY
- Total Recording Duration: ${durationSec} seconds
- Total Telemetry Frames: ${sampleCount} records
- Signal Contact Quality: ${signalQuality} valid finger contact
- Heart Rate (2-min window): Average ${hrMean} bpm | Range: ${hrRange}
- SpO2 (2-min window): Average ${spo2Mean} % | Range: ${spo2Range}
- Body Temperature (2-min window): Average ${tempMean} °C | Range: ${tempRange}
- Estimated Hemoglobin (Hb): Average ${hbMean} g/dL | Range: ${hbRange}
- Estimated Blood Glucose: Average ${glucoseMean} mg/dL | Range: ${glucoseRange}
- Perfusion Index (PI): Average ${piMean} % | Range: ${piRange}
- Ratio of Ratios (R): ${ratioR}
- Pulse Amplitude: ${pulseAmp} ADC units
- Latest Snapshot: HR ${latest.heart_rate ?? hrMean} bpm, SpO2 ${latest.spo2 ?? spo2Mean}%, Temp ${latest.body_temperature ?? tempMean}°C

## YOUR DIAGNOSTIC TASK
Synthesize the entire 2-minute dataset to provide:
1. **Primary Clinical Diagnosis / Impression**: A clear, precise diagnostic screening impression (e.g., "Normal Cardiorespiratory & Glycemic Status", "Suspected Mild Microcytic/Normocytic Anemia Pattern", "Compensatory Tachycardia with Peripheral Vasoconstriction", "Impaired Glycemic Pattern with Reduced Perfusion").
2. **Diagnostic Category**: E.g. "Hematological", "Metabolic", "Cardiovascular", "Optimal / Healthy", or "Autonomic".
3. **Severity**: One of: "Normal", "Mild Risk", "Moderate Risk", "Elevated Concern", "Critical Attention Required".
4. **Session Overview & Temporal Trend Summary**: Evaluate how vitals trended over the 2 minutes (e.g. resting heart rate stabilization, heart rate variability, SpO2 dips/stability, sensor stability).
5. **Physiological Summary**: Multi-system synthesis connecting cardiovascular and metabolic function.
6. **Anemia Screening**: In-depth clinical assessment evaluating the 2-minute Hb estimate, Ratio of Ratios (R), oxygen-carrying capacity, and tissue hypoxia risk.
7. **Diabetes & Glycemic Screening**: In-depth metabolic assessment evaluating estimated Glucose, Perfusion Index (blood viscosity/microvascular resistance), and pulse wave morphology.
8. **Detailed Parameter Breakdown**: Provide an item for EACH parameter: Heart Rate, SpO2, Body Temperature, Hemoglobin (Est), Blood Glucose (Est), Perfusion Index (PI), Pulse Amplitude, and Ratio of Ratios (R). State the value with range, clinical reference range, status (e.g., Optimal, Normal, Borderline, Elevated, Low, Critical), and a detailed explanation of clinical significance.
9. **Actionable Recommendations**: General clinical guidance.
10. **Confirmatory Diagnostic Lab Tests**: Specific laboratory tests to advise the patient (e.g., "Complete Blood Count (CBC) with Red Cell Indices", "Serum Ferritin & Total Iron Binding Capacity", "HbA1c & Fasting Plasma Glucose").
11. **Holistic & Dietary Guidance**: Ayurvedic / nutritional recommendations tailored to the findings (e.g. iron-rich nutrition, Triphala, Moringa, hydration, stress reduction).
12. **Overall Risk Level**: ("low", "moderate", "high").
13. **Confidence Score**: (0.0 to 1.0, reflecting signal quality and data consistency).

Output MUST be valid JSON adhering strictly to this schema:
{
  "primary_diagnosis": "string",
  "diagnostic_category": "string",
  "severity": "string",
  "risk_level": "string",
  "confidence": number,
  "session_overview": "string",
  "temporal_trend_summary": "string",
  "physiological_summary": "string",
  "anemia_screening": "string",
  "diabetes_screening": "string",
  "parameter_breakdown": [
    {
      "parameter": "string",
      "value": "string",
      "clinical_reference": "string",
      "status": "string",
      "analysis": "string"
    }
  ],
  "recommendations": ["string"],
  "lab_tests_recommended": ["string"],
  "holistic_and_lifestyle": ["string"]
}
`.trim();

  const chatCompletion = await groq.chat.completions.create({
    messages: [
      {
        role: "system",
        content: "You are an advanced medical JSON API for physiological telemetry. You only respond in pure JSON. No markdown formatting, no backticks, no explanations outside of the JSON block."
      },
      {
        role: "user",
        content: prompt
      }
    ],
    model: "groq/compound",
    temperature: 0.2,
    response_format: { type: "json_object" }
  });

  const responseText = chatCompletion.choices[0].message.content;
  return JSON.parse(responseText);
}

module.exports = { analyzeAyurAI };
