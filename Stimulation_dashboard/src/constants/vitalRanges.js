/**
 * AyurAI — Clinical Vital Sign Reference Ranges
 *
 * Based on standard clinical guidelines:
 *   Heart Rate: AHA / WHO normal adult resting HR
 *   SpO2: WHO / pulse oximetry clinical thresholds
 *
 * Statuses: 'normal' | 'warning' | 'critical'
 */

export const VITAL_RANGES = {
  heart_rate: {
    label: 'Heart Rate',
    unit: 'bpm',
    description: 'Resting adult heart rate',
    ranges: [
      { label: 'Critical Low',  min: 0,   max: 39,  status: 'critical', color: 'var(--accent-rose)'    },
      { label: 'Low',           min: 40,  max: 59,  status: 'warning',  color: 'var(--accent-amber)'   },
      { label: 'Normal',        min: 60,  max: 100, status: 'normal',   color: 'var(--accent-emerald)' },
      { label: 'Elevated',      min: 101, max: 120, status: 'warning',  color: 'var(--accent-amber)'   },
      { label: 'Critical High', min: 121, max: 300, status: 'critical', color: 'var(--accent-rose)'    },
    ],
    scaleMin: 0,
    scaleMax: 200,
    reference: [
      { label: 'Bradycardia',    range: '< 60 bpm',    desc: 'Abnormally slow heart rate' },
      { label: 'Normal',         range: '60 – 100 bpm', desc: 'Healthy resting adult range' },
      { label: 'Tachycardia',    range: '> 100 bpm',   desc: 'Abnormally fast heart rate' },
      { label: 'Critical High',  range: '> 120 bpm',   desc: 'Seek immediate assessment' },
    ]
  },
  spo2: {
    label: 'SpO₂',
    unit: '%',
    description: 'Blood oxygen saturation',
    ranges: [
      { label: 'Critical Low',  min: 0,  max: 89,  status: 'critical', color: 'var(--accent-rose)'    },
      { label: 'Low',           min: 90, max: 94,  status: 'warning',  color: 'var(--accent-amber)'   },
      { label: 'Normal',        min: 95, max: 100, status: 'normal',   color: 'var(--accent-emerald)' },
    ],
    scaleMin: 85,
    scaleMax: 100,
    reference: [
      { label: 'Severe Hypoxia', range: '< 90%',    desc: 'Critical — seek immediate care' },
      { label: 'Mild Hypoxia',   range: '90 – 94%', desc: 'Below normal — monitor closely' },
      { label: 'Normal',         range: '95 – 100%', desc: 'Healthy oxygen saturation' },
    ]
  }
};

/**
 * Get the status for a given value and vital key.
 * @param {string} key   — 'heart_rate' | 'spo2'
 * @param {number} value
 * @returns {{ status: string, color: string, label: string } | null}
 */
export function getVitalStatus(key, value) {
  if (value == null || isNaN(value)) return null;
  const vital = VITAL_RANGES[key];
  if (!vital) return null;
  for (const range of vital.ranges) {
    if (value >= range.min && value <= range.max) {
      return { status: range.status, color: range.color, label: range.label };
    }
  }
  return null;
}

/**
 * Get all active alerts for the current readings.
 * @param {{ heart_rate: number|null, spo2: number|null }} data
 * @returns {Array<{ key, value, status, label, color, message }>}
 */
export function getActiveAlerts(data) {
  const alerts = [];

  const checks = [
    {
      key: 'heart_rate',
      value: data.heart_rate,
      messages: {
        critical: (v) => v < 40
          ? `Heart rate critically low at ${v} bpm (bradycardia). Seek immediate attention.`
          : `Heart rate critically high at ${v} bpm (tachycardia). Seek immediate attention.`,
        warning: (v) => v < 60
          ? `Heart rate low at ${v} bpm. Patient may be bradycardic.`
          : `Heart rate elevated at ${v} bpm. Monitor closely.`
      }
    },
    {
      key: 'spo2',
      value: data.spo2,
      messages: {
        critical: (v) => `SpO₂ critically low at ${v}%. Severe hypoxia — seek immediate care.`,
        warning:  (v) => `SpO₂ below normal at ${v}%. Mild hypoxia — monitor closely.`
      }
    }
  ];

  for (const check of checks) {
    if (check.value == null) continue;
    const vitalStatus = getVitalStatus(check.key, check.value);
    if (vitalStatus && (vitalStatus.status === 'critical' || vitalStatus.status === 'warning')) {
      alerts.push({
        key:     check.key,
        value:   check.value,
        status:  vitalStatus.status,
        label:   vitalStatus.label,
        color:   vitalStatus.color,
        message: check.messages[vitalStatus.status]?.(check.value) ?? vitalStatus.label
      });
    }
  }

  return alerts;
}
