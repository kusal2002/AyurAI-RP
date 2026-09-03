/**
 * AyurAI — PPG Feature Extraction Service
 *
 * Extracts physiologically meaningful features from a window of
 * raw RED and IR PPG samples collected by the MAX30102.
 *
 * These features can be used by:
 *   1. A future trained Hb/anemia prediction model
 *   2. Gemini API for contextual interpretation
 *
 * NOTE: The MAX30102 does NOT directly measure hemoglobin or
 * blood glucose. These features are derived signals that
 * correlate with light absorption in tissue — they are inputs
 * to a research model, not direct measurements.
 */

/**
 * Compute mean of an array.
 * @param {number[]} arr
 * @returns {number}
 */
function mean(arr) {
  if (!arr || arr.length === 0) return 0;
  return arr.reduce((sum, v) => sum + v, 0) / arr.length;
}

/**
 * Compute standard deviation of an array.
 * @param {number[]} arr
 * @returns {number}
 */
function stdDev(arr) {
  if (!arr || arr.length < 2) return 0;
  const m = mean(arr);
  const variance = arr.reduce((sum, v) => sum + Math.pow(v - m, 2), 0) / arr.length;
  return Math.sqrt(variance);
}

/**
 * Extract PPG signal features from RED and IR windows.
 *
 * Features extracted:
 *   ir_dc       — DC component (mean IR value; relates to tissue thickness & blood volume)
 *   ir_ac       — AC component (std dev IR; pulse amplitude variation)
 *   red_dc      — DC component of RED channel
 *   red_ac      — AC component of RED channel
 *   ratio_r     — AC_red/DC_red ÷ AC_ir/DC_ir — core ratio for SpO2/Hb estimation
 *   ir_peak     — Maximum IR value in window
 *   ir_trough   — Minimum IR value in window
 *   pulse_amp   — ir_peak - ir_trough (pulsatile amplitude)
 *   perfusion_index — pulse_amp / ir_dc × 100 (%)
 *
 * @param {number[]} irWindow   — Array of IR ADC samples (10–100 values)
 * @param {number[]} redWindow  — Array of RED ADC samples (10–100 values)
 * @returns {object} Feature map
 */
function extractPPGFeatures(irWindow, redWindow) {
  if (!irWindow || !redWindow || irWindow.length === 0) {
    return {
      ir_dc: 0, ir_ac: 0,
      red_dc: 0, red_ac: 0,
      ratio_r: 0,
      ir_peak: 0, ir_trough: 0,
      pulse_amp: 0,
      perfusion_index: 0,
      sample_count: 0,
      valid: false
    };
  }

  const ir_dc  = mean(irWindow);
  const ir_ac  = stdDev(irWindow);
  const red_dc = mean(redWindow);
  const red_ac = stdDev(redWindow);

  // Ratio of ratios — key feature for photoplethysmography-based estimation
  // R = (AC_red / DC_red) / (AC_ir / DC_ir)
  const ratio_r = (ir_dc > 0 && red_dc > 0)
    ? (red_ac / red_dc) / (ir_ac / ir_dc)
    : 0;

  const ir_peak   = Math.max(...irWindow);
  const ir_trough = Math.min(...irWindow);
  const pulse_amp = ir_peak - ir_trough;

  // Perfusion Index = pulsatile / non-pulsatile × 100 (%)
  const perfusion_index = ir_dc > 0
    ? (pulse_amp / ir_dc) * 100
    : 0;

  return {
    ir_dc:            parseFloat(ir_dc.toFixed(2)),
    ir_ac:            parseFloat(ir_ac.toFixed(2)),
    red_dc:           parseFloat(red_dc.toFixed(2)),
    red_ac:           parseFloat(red_ac.toFixed(2)),
    ratio_r:          parseFloat(ratio_r.toFixed(4)),
    ir_peak,
    ir_trough,
    pulse_amp,
    perfusion_index:  parseFloat(perfusion_index.toFixed(4)),
    sample_count:     irWindow.length,
    valid: ir_dc > 500 // Sanity check — finger must be on sensor (lowered for prototype LED brightness)
  };
}

module.exports = { extractPPGFeatures };
