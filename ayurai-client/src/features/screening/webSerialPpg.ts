/**
 * Component 1: read the AyurAI ESP32-S3 + MAX30102 firmware over Web Serial (desktop Chrome/Edge, HTTPS).
 *
 * Firmware output (arduino/ayurai_max30102_local, 115200 baud):
 *   "time_ms,red,ir"                              one RED/IR sample per line (about 25 per second)
 *   "#METRICS,time_ms,hr,spo2,temp,finger"        about once per second; "null" when a value is unknown
 *   "#AYURAI_MAX30102_LOCAL_READY", "#METRICS_FORMAT,...", the header "time_ms,red,ir"   (ignored)
 *   "#ERROR,MAX30102_NOT_FOUND"                   sensor not detected (no samples follow)
 *
 * Parsing and timing mirror component1/acquisition/ppg/capture_live_ppg.py (same ranges, 2 s start-up wait,
 * host-elapsed timestamps), and the recording is returned in that recorder's CSV format, so the server
 * processes it with the unchanged pipeline.
 */

export type SerialSample = [hostElapsedS: number, esp32Ms: number, red: number, ir: number]
export type SerialMetric = [timeMs: number, hr: number | null, spo2: number | null, temperature: number | null, finger: 0 | 1]

export type SerialPortLike = {
  open(options: { baudRate: number }): Promise<void>
  close(): Promise<void>
  readable: ReadableStream<Uint8Array> | null
  getInfo(): { usbVendorId?: number; usbProductId?: number }
}

type SerialLike = { requestPort(options?: object): Promise<SerialPortLike> }

const ADC_MAX = 262143 // MAX30102 18-bit ADC, as capture_live_ppg.parse_sensor_line.
const START_UP_MS = 2000 // The ESP32 restarts when the port opens (capture_live_ppg waits 2 s too).
const NO_DATA_TIMEOUT_MS = 6000

export class SerialCaptureError extends Error {}

function serialApi(): SerialLike | null {
  return (navigator as Navigator & { serial?: SerialLike }).serial ?? null
}

/** Web Serial needs a Chromium desktop browser and a secure (HTTPS or localhost) page. */
export function isWebSerialSupported(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && serialApi() !== null
}

/** Must be called from a click handler: the browser shows its port chooser. Returns null if the user cancels. */
export async function requestEsp32Port(): Promise<SerialPortLike | null> {
  const serial = serialApi()
  if (!serial) throw new SerialCaptureError("This browser cannot access USB serial devices. Use desktop Chrome or Edge.")
  try {
    return await serial.requestPort()
  } catch (error) {
    if (error instanceof DOMException && error.name === "NotFoundError") return null // chooser closed
    throw new SerialCaptureError("The browser could not access USB serial devices.")
  }
}

export function portLabel(port: SerialPortLike): string {
  const info = port.getInfo()
  if (info.usbVendorId === undefined) return "USB serial device"
  const hex = (value?: number) => (value ?? 0).toString(16).toUpperCase().padStart(4, "0")
  return `USB serial device ${hex(info.usbVendorId)}:${hex(info.usbProductId)}${info.usbVendorId === 0x303a ? " (Espressif ESP32)" : ""}`
}

const INTEGER = /^-?\d+$/

function toInt(value: string): number | null {
  const text = value.trim()
  return INTEGER.test(text) ? Number(text) : null
}

/** "time_ms,red,ir" -> [time_ms, red, ir], or null (same rules as parse_sensor_line). */
export function parseSensorLine(line: string): [number, number, number] | null {
  const parts = line.trim().split(",")
  if (parts.length !== 3) return null
  const [millis, red, ir] = parts.map(toInt)
  if (millis === null || red === null || ir === null || millis < 0) return null
  if (!(red >= 0 && red <= ADC_MAX && ir >= 0 && ir <= ADC_MAX)) return null
  return [millis, red, ir]
}

/** "#METRICS,time_ms,hr,spo2,temp,finger" -> metric, or null (same rules as parse_metrics_line). */
export function parseMetricsLine(line: string): SerialMetric | null {
  const parts = line.split(",").map((part) => part.trim())
  if (parts.length !== 6 || parts[0] !== "#METRICS") return null
  const optional = (text: string) => (text.toLowerCase() === "null" ? null : toInt(text) ?? Number.NaN)
  const timestamp = toInt(parts[1])
  const hr = optional(parts[2])
  const spo2 = optional(parts[3])
  const temperature = parts[4].toLowerCase() === "null" ? null : Number(parts[4])
  const finger = toInt(parts[5])
  if (timestamp === null || timestamp < 0 || (finger !== 0 && finger !== 1)) return null
  if (Number.isNaN(hr) || Number.isNaN(spo2) || (temperature !== null && !Number.isFinite(temperature))) return null
  if (hr !== null && !(hr >= 0 && hr <= 300)) return null
  if (spo2 !== null && !(spo2 >= 0 && spo2 <= 100)) return null
  return [timestamp, hr, spo2, temperature, finger]
}

export type CaptureProgress = {
  phase: "opening" | "starting" | "receiving"
  samples: number
  metrics: number
  elapsedS: number
  lastMetric: SerialMetric | null
}

export type CaptureResult = { samples: SerialSample[]; metrics: SerialMetric[]; badLines: number }

/**
 * Open the port, wait for the ESP32 to start, then record `seconds` of samples. Always closes the port.
 * Throws SerialCaptureError with an operator-facing message; an aborted signal throws a DOMException "AbortError".
 */
export async function captureFromPort(
  port: SerialPortLike,
  { seconds, baudRate, signal, onProgress }: { seconds: number; baudRate: number; signal?: AbortSignal; onProgress?: (p: CaptureProgress) => void },
): Promise<CaptureResult> {
  const samples: SerialSample[] = []
  const metrics: SerialMetric[] = []
  let badLines = 0
  onProgress?.({ phase: "opening", samples: 0, metrics: 0, elapsedS: 0, lastMetric: null })
  try {
    await port.open({ baudRate })
  } catch {
    throw new SerialCaptureError(
      "The ESP32 port could not be opened. Close Arduino Serial Monitor, the Streamlit Live PPG page or any other program using it, then try again.",
    )
  }

  const reader = port.readable?.getReader()
  if (!reader) {
    await port.close().catch(() => undefined)
    throw new SerialCaptureError("The ESP32 port opened but cannot be read. Unplug it, plug it back in and choose Connect ESP32.")
  }
  const decoder = new TextDecoder("ascii")
  const opened = performance.now()
  let recordingStart: number | null = null
  let previousChunk = 0
  let skipPartialLine = false
  let buffer = ""
  let lastData = performance.now()
  let stalled = false
  let sensorMissing = false
  let lastReport = 0
  const watchdog = window.setInterval(() => {
    const now = performance.now()
    const startUpDone = now - opened >= START_UP_MS
    if (signal?.aborted || (startUpDone && now - lastData > NO_DATA_TIMEOUT_MS) ||
        (recordingStart !== null && now - recordingStart >= seconds * 1000)) {
      stalled = !signal?.aborted && now - lastData > NO_DATA_TIMEOUT_MS
      void reader.cancel().catch(() => undefined)
    }
  }, 100)

  const handleLine = (raw: string, now: number) => {
    const line = raw.trim()
    if (!line) return
    if (line.startsWith("#ERROR")) {
      if (line.includes("MAX30102_NOT_FOUND")) sensorMissing = true
      return
    }
    if (recordingStart === null) return // start-up output and buffered lines are discarded
    if (line.startsWith("#METRICS,")) {
      const metric = parseMetricsLine(line)
      if (metric) metrics.push(metric)
      else badLines += 1
      return
    }
    if (line.startsWith("#") || line === "time_ms,red,ir") return
    const parsed = parseSensorLine(line)
    if (!parsed) {
      badLines += 1
      return
    }
    const elapsed = Math.round(((now - recordingStart) / 1000) * 1e6) / 1e6
    if (elapsed >= seconds) return
    samples.push([elapsed, parsed[0], parsed[1], parsed[2]])
  }

  try {
    for (;;) {
      let chunk: ReadableStreamReadResult<Uint8Array>
      try {
        chunk = await reader.read()
      } catch {
        throw new SerialCaptureError("The ESP32 was disconnected. Check the USB cable, then choose Connect ESP32 again.")
      }
      if (chunk.done) break
      const now = performance.now()
      lastData = now
      if (recordingStart === null && now - opened >= START_UP_MS) {
        // Like reset_input_buffer(): everything received during start-up is dropped, including the line in progress.
        recordingStart = now
        previousChunk = now
        buffer = ""
        skipPartialLine = true
        continue
      }
      buffer += decoder.decode(chunk.value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() ?? ""
      if (skipPartialLine && lines.length) {
        lines.shift()
        skipPartialLine = false
      }
      // Several lines can arrive in one USB read. The quality check derives the sample rate from host_elapsed_s
      // (1 / median interval), so each line gets an approximate receive time spread between this read and the
      // previous one, never several identical timestamps.
      lines.forEach((line, index) => handleLine(line, previousChunk + ((now - previousChunk) * (index + 1)) / lines.length))
      if (recordingStart !== null) previousChunk = now
      if (now - lastReport > 250) {
        lastReport = now
        onProgress?.({
          phase: recordingStart === null ? "starting" : "receiving",
          samples: samples.length,
          metrics: metrics.length,
          elapsedS: recordingStart === null ? 0 : Math.min(seconds, Math.round((now - recordingStart) / 100) / 10),
          lastMetric: metrics.at(-1) ?? null,
        })
      }
    }
  } finally {
    window.clearInterval(watchdog)
    reader.releaseLock()
    await port.close().catch(() => undefined)
  }

  if (signal?.aborted) throw new DOMException("Recording cancelled", "AbortError")
  if (sensorMissing) throw new SerialCaptureError("The ESP32 reports that the MAX30102 sensor was not found. Check the sensor wiring.")
  if (stalled && samples.length === 0) {
    throw new SerialCaptureError("No data arrived from the ESP32. Check that the AyurAI firmware is running at 115200 baud.")
  }
  if (stalled) throw new SerialCaptureError("The ESP32 stopped sending data during the recording. Check the USB cable and try again.")
  if (samples.length === 0) {
    throw new SerialCaptureError("No valid RED/IR samples arrived. Check that the AyurAI firmware is running and the finger is on the sensor.")
  }
  return { samples, metrics, badLines }
}

/** CSV in capture_live_ppg's format (csv.writer: CRLF line endings, empty field for a missing value). */
export function samplesCsv(rows: SerialSample[]): string {
  return ["host_elapsed_s,esp32_readout_ms,red,ir", ...rows.map((row) => row.join(","))].join("\r\n") + "\r\n"
}

export function metricsCsv(rows: SerialMetric[]): string {
  if (rows.length === 0) return ""
  const cell = (value: number | null) => (value === null ? "" : String(value))
  return ["time_ms,hr_bpm,spo2_percent,temperature_c,finger_present", ...rows.map((row) => row.map(cell).join(","))].join("\r\n") + "\r\n"
}
