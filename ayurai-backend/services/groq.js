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
 * Analyze sensor data + PPG features using Groq.
 *
 * @param {object} data — Combined sensor + feature data
 * @param {number|null} data.heart_rate
 * @param {number|null} data.spo2
 * @param {number|null} data.body_temperature
 * @param {object}      data.ppg_features — Output of extractPPGFeatures()
 * @param {number|null} [data.hb_estimate] — Optional: output from ML model
 * @returns {Promise<object>} Structured Groq interpretation
 */
async function analyzeAyurAI(data) {
  if (!process.env.API_KEY) {
    throw new Error("GROQ API KEY is missing in .env file");
  }

  const { heart_rate, spo2, body_temperature, ppg_features, hb_estimate, glucose_estimate } = data;

  const hbSection = hb_estimate != null
    ? `Hemoglobin estimate (from research ML model, NOT from Groq): ${hb_estimate} g/dL`
    : `Hemoglobin estimate: Not available.`;

  const glucoseSection = glucose_estimate != null
    ? `Blood Glucose estimate (from research ML model, NOT from Groq): ${glucose_estimate} mg/dL`
    : `Blood Glucose estimate: Not available.`;

  const prompt = `
You are the AI interpretation layer of the AyurAI research prototype — a non-invasive anemia screening system using the MAX30102 optical sensor on an ESP32-S3.

## IMPORTANT CONSTRAINTS
1. The MAX30102 measures heart rate, SpO2, and raw RED/IR photoplethysmography (PPG) signals.
2. The MAX30102 does NOT directly measure blood glucose or hemoglobin. Do NOT claim it does.
3. This is a research screening prototype. Do NOT make clinical diagnoses.
4. If a hemoglobin estimate is provided below, it comes from a separately trained ML model — NOT from you.
5. Your role: interpret the physiological context, assess anemia risk indicators, and generate a human-readable explanation.

## SENSOR DATA
- Heart Rate: ${heart_rate ?? "N/A"} bpm
- SpO2: ${spo2 ?? "N/A"} %
- Body Temperature: ${body_temperature ?? "N/A"} °C
- Hemoglobin (Hb) Estimate: ${hb_estimate ?? "N/A"} g/dL
- Blood Glucose Estimate: ${glucose_estimate ?? "N/A"} mg/dL
- Perfusion Index (PI): ${ppg_features.perfusion_index} %
- Pulse Amplitude: ${ppg_features.pulse_amp} ADC units
- Ratio of Ratios (R): ${ppg_features.ratio_r}
- Signal Valid: ${ppg_features.valid ? "Yes (Finger Detected)" : "No (Poor Contact)"}

## YOUR TASK
Based only on the above, provide:
1. A detailed physiological summary.
2. An anemia screening assessment.
3. A diabetes & blood sugar screening assessment (HEAVILY FOCUS ON THIS, analyzing the glucose estimate in detail).
4. A detailed breakdown of EVERY available parameter. You MUST include: Heart Rate, SpO2, Body Temperature, Hemoglobin, Blood Glucose, Perfusion Index (PI), and Pulse Amplitude. State the value, clinical status (e.g., Normal, High, Critical, Low), and a detailed explanation of what that level means for the patient's cardiovascular and metabolic health.
5. An overall risk level (low, moderate, high).
6. Your confidence score (0.0 to 1.0) considering the signal validity.
7. A list of actionable recommendations.

Output MUST be valid JSON adhering exactly to this schema:
{
  "physiological_summary": "string",
  "anemia_screening": "string",
  "diabetes_screening": "string",
  "parameter_breakdown": [
    {
      "parameter": "string",
      "value": "string",
      "status": "string (e.g. Normal, Elevated, Low, Critical)",
      "analysis": "string"
    }
  ],
  "risk_level": "string (low, moderate, high)",
  "confidence": number,
  "recommendations": ["string"]
}
`.trim();

  const chatCompletion = await groq.chat.completions.create({
    messages: [
      {
        role: "system",
        content: "You are a medical JSON API. You only respond in pure JSON. No markdown formatting, no backticks, no explanations outside of the JSON block."
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
