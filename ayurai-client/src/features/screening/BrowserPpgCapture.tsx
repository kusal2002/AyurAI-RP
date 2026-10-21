import * as React from "react"
import { Activity, RotateCcw, Square, Usb } from "lucide-react"

import { KeyValueList, Notice, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { component1Api } from "@/lib/api/component1"
import type { C1PpgUploadBody, C1RecordingResult } from "@/lib/api/types"
import {
  SerialCaptureError,
  captureFromPort,
  isWebSerialSupported,
  metricsCsv,
  portLabel,
  requestEsp32Port,
  samplesCsv,
  type CaptureProgress,
  type SerialPortLike,
} from "@/features/screening/webSerialPpg"

/** Saved-recording summary (same for USB-on-server and browser recordings). */
export function RecordingSummary({ result }: { result: C1RecordingResult }) {
  return (
    <div className="space-y-2">
      <KeyValueList
        items={[
          { label: "Saved to", value: `session ${result.session_id} · SQLite recording #${result.recording_id}` },
          { label: "RED/IR samples", value: `${result.sample_count} @ ${result.observed_receive_rate_hz ?? "?"} Hz` },
          {
            label: "Technical quality",
            value: result.quality_passed ? "Passed (candidate for pulse validation)" : "Not passed — retake suggested",
          },
          { label: "Experimental HR (device)", value: result.median_experimental_hr_bpm != null ? `${result.median_experimental_hr_bpm} bpm` : "not reported" },
          { label: "Experimental SpO2 (device)", value: result.median_experimental_spo2_percent != null ? `${result.median_experimental_spo2_percent}%` : "not reported" },
          { label: "Temperature", value: result.median_temperature_c != null ? `${result.median_temperature_c} °C` : "N/A (no temperature sensor)" },
          { label: "Hb from PPG", value: "Not applied — live PPG Hb transfer is not validated" },
        ]}
      />
      <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-600">
        {result.quality_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  )
}

type Phase = "idle" | "opening" | "starting" | "receiving" | "uploading" | "saved" | "probe_ok" | "cancelled" | "failed"

const BUSY: Phase[] = ["opening", "starting", "receiving", "uploading"]
const PROBE_SECONDS = 4

function headline(phase: Phase, error: string | null): { text: string; tone: "info" | "caution" | "critical" | "neutral" } | null {
  switch (phase) {
    case "opening":
      return { text: "Opening the ESP32 port…", tone: "info" }
    case "starting":
      return { text: "Port open — waiting for the ESP32 to start (it restarts when the port opens)", tone: "info" }
    case "receiving":
      return { text: "Receiving live RED/IR samples", tone: "info" }
    case "uploading":
      return { text: "Recording finished — uploading, running technical-quality checks and saving", tone: "info" }
    case "saved":
      return { text: "Recording saved", tone: "neutral" }
    case "probe_ok":
      return { text: "Live signal confirmed (check only — nothing saved)", tone: "neutral" }
    case "cancelled":
      return { text: "Recording cancelled — nothing was saved", tone: "caution" }
    case "failed":
      return { text: error ?? "Recording failed", tone: "critical" }
    default:
      return null
  }
}

function errorText(error: unknown): string {
  if (error instanceof SerialCaptureError || error instanceof ApiError) return error.message
  return "Unexpected error while reading the ESP32."
}

/**
 * PPG from an ESP32 plugged into THIS computer, read in the browser (Web Serial) and uploaded to the
 * Component 1 server, which processes it like a USB recording. Shown only when the server enables uploads.
 */
export function BrowserPpgCapture({
  sessionId,
  baud,
  hasRecordings,
  onSaved,
}: {
  sessionId: string
  baud: number
  hasRecordings: boolean
  onSaved: () => void
}) {
  const [port, setPort] = React.useState<SerialPortLike | null>(null)
  const [phase, setPhase] = React.useState<Phase>("idle")
  const [progress, setProgress] = React.useState<CaptureProgress | null>(null)
  const [seconds, setSeconds] = React.useState(20)
  const [error, setError] = React.useState<string | null>(null)
  const [probe, setProbe] = React.useState<{ rows: number; perSecond: number } | null>(null)
  const [result, setResult] = React.useState<C1RecordingResult | null>(null)
  // A captured recording is kept until the server confirms it, so a failed upload can be retried as-is.
  const [pending, setPending] = React.useState<C1PpgUploadBody | null>(null)
  const busyRef = React.useRef(false) // blocks a second click before React re-renders
  const abortRef = React.useRef<AbortController | null>(null)

  React.useEffect(() => () => abortRef.current?.abort(), [])

  if (!isWebSerialSupported()) {
    return (
      <Notice tone="caution" title="This browser cannot read the ESP32">
        Live PPG on this website uses Web Serial, available in desktop Chrome or Microsoft Edge over HTTPS. Open this page in one
        of those browsers, or choose Continue without PPG (the report will list PPG as missing).
      </Notice>
    )
  }

  const busy = BUSY.includes(phase)

  const run = async (task: () => Promise<void>) => {
    if (busyRef.current) return
    busyRef.current = true
    setError(null)
    try {
      await task()
    } finally {
      busyRef.current = false
    }
  }

  const connect = () =>
    run(async () => {
      try {
        const chosen = await requestEsp32Port() // direct result of the click: the browser shows its port chooser
        if (chosen) {
          setPort(chosen)
          setPhase("idle")
        }
      } catch (err) {
        setError(errorText(err))
      }
    })

  const capture = async (duration: number) => {
    if (!port) throw new SerialCaptureError("Choose Connect ESP32 first.")
    const controller = new AbortController()
    abortRef.current = controller
    setProgress(null)
    try {
      return await captureFromPort(port, {
        seconds: duration,
        baudRate: baud,
        signal: controller.signal,
        onProgress: (update) => {
          setProgress(update)
          setPhase(update.phase)
        },
      })
    } finally {
      abortRef.current = null
    }
  }

  const testSignal = () =>
    run(async () => {
      setProbe(null)
      try {
        const recorded = await capture(PROBE_SECONDS)
        setProbe({ rows: recorded.samples.length, perSecond: Math.round((recorded.samples.length / PROBE_SECONDS) * 10) / 10 })
        setPhase("probe_ok")
      } catch (err) {
        setPhase(err instanceof DOMException && err.name === "AbortError" ? "cancelled" : "failed")
        setError(err instanceof DOMException ? null : errorText(err))
      }
    })

  const upload = async (body: C1PpgUploadBody) => {
    setPhase("uploading")
    try {
      setResult(await component1Api.uploadPpg(sessionId, body))
      setPending(null)
      setPhase("saved")
      onSaved()
    } catch (err) {
      setPhase("failed")
      setError(`${errorText(err)} The recording is kept in this page: choose Retry upload.`)
    }
  }

  const record = () =>
    run(async () => {
      setResult(null)
      try {
        const recorded = await capture(seconds)
        const body: C1PpgUploadBody = {
          upload_id: crypto.randomUUID().replace(/-/g, ""),
          seconds,
          samples_csv: samplesCsv(recorded.samples),
          metrics_csv: metricsCsv(recorded.metrics),
        }
        setPending(body)
        await upload(body)
      } catch (err) {
        setPhase(err instanceof DOMException && err.name === "AbortError" ? "cancelled" : "failed")
        setError(err instanceof DOMException ? null : errorText(err))
      }
    })

  const retryUpload = () => run(async () => (pending ? upload(pending) : undefined))

  const status = headline(phase, error)
  const lastMetric = progress?.lastMetric ?? null

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
        <Usb className="size-4" aria-hidden />
        <span>
          ESP32 on this computer ({baud} baud):{" "}
          <strong className={port ? "text-slate-800" : "text-slate-500"}>{port ? `connected — ${portLabel(port)}` : "not connected"}</strong>
        </span>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => void connect()}>
          {port ? "Change ESP32 port" : "Connect ESP32"}
        </Button>
        <Button size="sm" variant="outline" disabled={busy || !port} onClick={() => void testSignal()}>
          Test live signal (4 s, not saved)
        </Button>
      </div>
      {!port && (
        <p className="text-xs text-slate-500">
          Plug the ESP32 into this computer, choose Connect ESP32 and select it in the browser&apos;s list. Close Arduino Serial Monitor first.
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-slate-600">
          Duration
          <select className={fieldClass} value={seconds} disabled={busy} onChange={(event) => setSeconds(Number(event.target.value))}>
            {[10, 20, 30].map((value) => (
              <option key={value} value={value}>
                {value} seconds
              </option>
            ))}
          </select>
        </label>
        <Button disabled={busy || !port} onClick={() => void record()}>
          <Activity /> {hasRecordings ? "Record another (retake)" : "Record PPG"}
        </Button>
        {(phase === "opening" || phase === "starting" || phase === "receiving") && (
          <Button variant="outline" onClick={() => abortRef.current?.abort()}>
            <Square /> Cancel (nothing saved)
          </Button>
        )}
        {pending && phase === "failed" && (
          <Button variant="outline" onClick={() => void retryUpload()}>
            <RotateCcw /> Retry upload
          </Button>
        )}
      </div>

      {status && (
        <Notice tone={status.tone} title={status.text}>
          {progress && phase !== "failed" && (
            <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
              <span>Elapsed: {progress.elapsedS} s</span>
              <span>Valid RED/IR rows received: {progress.samples}</span>
              <span>Device metrics lines: {progress.metrics}</span>
              <span>Finger contact (device): {lastMetric === null ? "not reported yet" : lastMetric[4] ? "yes" : "no"}</span>
              <span>Last device HR: {lastMetric?.[1] ?? "—"} · SpO2: {lastMetric?.[2] ?? "—"}</span>
            </div>
          )}
          {phase === "probe_ok" && probe && (
            <p className="mt-1">{probe.rows} valid rows in {PROBE_SECONDS} s (~{probe.perSecond}/s).</p>
          )}
        </Notice>
      )}

      {result && <RecordingSummary result={result} />}
    </div>
  )
}
