import * as React from "react"
import {
  Activity,
  Camera,
  CameraOff,
  Download,
  FlaskConical,
  History,
  Play,
  RotateCcw,
  ShieldAlert,
  Square,
  Usb,
} from "lucide-react"

import { IdChip, KeyValueList, LoadingState, Notice, Panel, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { component1Api } from "@/lib/api/component1"
import type {
  C1Answers,
  C1CaptureCounts,
  C1CaptureStatus,
  C1ImageChange,
  C1IntakeState,
  C1PpgJob,
  C1Patient,
  C1PatientDataStatus,
  C1PpgCaptureOptions,
  C1PpgJobStatus,
  C1Question,
  C1QuestionSet,
  C1RecordingResult,
  C1SavedImage,
  C1SavedRecording,
  Component1Report,
  Component1Session,
} from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { ReportView, downloadJson } from "@/features/screening/Component1SessionPanel"
import { BrowserPpgCapture, RecordingSummary } from "@/features/screening/BrowserPpgCapture"
import {
  PatientBanner,
  PatientDetailsForm,
  PdfReportButton,
  RegistrationUnavailable,
  newRequestId,
  patientFeaturesAvailable,
} from "@/features/screening/PatientRegistration"

const STEPS = ["Session", "Patient & consent", "Questionnaire", "Webcam", "PPG sensor", "Report"] as const
type Modality = keyof C1CaptureCounts
const MODALITIES: { key: Modality; label: string; hint: string }[] = [
  { key: "conjunctiva", label: "Conjunctiva", hint: "Gently pull down the lower eyelid; fill the frame with the inner eyelid." },
  { key: "nails", label: "Nail beds", hint: "Fingers flat, nails facing the camera, no polish." },
  { key: "tongue", label: "Tongue", hint: "Tongue extended, even lighting, no food colouring." },
]
const EMPTY_COUNTS: C1CaptureCounts = { conjunctiva: 0, nails: 0, tongue: 0 }
/** Answers that leave a safety question unresolved (neither a clear "yes" nor "no"). */
const UNRESOLVED = new Set(["not_sure", "prefer_not_to_answer"])

type StepStatus = "completed" | "current" | "pending" | "blocked" | "skipped"

const stepStyles: Record<StepStatus, string> = {
  current: "bg-emerald-600 text-white ring-emerald-600",
  completed: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  pending: "bg-white text-slate-500 ring-slate-200",
  blocked: "bg-rose-50 text-rose-700 ring-rose-200",
  skipped: "bg-slate-100 text-slate-500 ring-slate-200 line-through decoration-slate-400",
}

const stateLabels: Record<string, string> = {
  created: "created — questionnaire not saved",
  safety_referral: "safety referral",
  images_in_progress: "webcam images pending",
  ppg_in_progress: "PPG pending",
  ready_for_analysis: "ready for analysis",
  completed: "completed",
}

function message(error: unknown) {
  return error instanceof ApiError ? error.message : "Component 1 returned an unexpected error."
}

function humanize(value: string) {
  return value.replace(/_/g, " ")
}

function listToText(value: unknown, first: string, second: string) {
  if (!Array.isArray(value)) return ""
  return value
    .map((item) => {
      const record = item as Record<string, unknown>
      const details = record[second]
      return details && details !== "not_provided" ? `${String(record[first])} | ${String(details)}` : String(record[first])
    })
    .join("\n")
}

function QuestionField({
  question,
  value,
  onChange,
  invalid,
}: {
  question: C1Question
  value: string | number | undefined
  onChange: (value: string | number | undefined) => void
  invalid?: boolean
}) {
  return (
    <label className="block text-sm text-slate-800">
      <span className="font-medium">{question.prompt}</span>
      {question.type === "choice" ? (
        <select
          className={cn(fieldClass, invalid && "border-amber-400 ring-2 ring-amber-100")}
          value={value === undefined ? "" : String(value)}
          onChange={(event) => onChange(event.target.value || undefined)}
        >
          <option value="">Choose an answer…</option>
          {question.options?.map((option) => (
            <option key={option} value={option}>
              {humanize(option)}
            </option>
          ))}
        </select>
      ) : question.type === "integer" ? (
        <input
          className={fieldClass}
          type="number"
          min={0}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value === "" ? undefined : Number(event.target.value))}
        />
      ) : (
        <input
          className={fieldClass}
          value={value ?? ""}
          placeholder="Coded test answer (no identifying details)"
          onChange={(event) => onChange(event.target.value || undefined)}
        />
      )}
    </label>
  )
}

type PendingCapture = { blob: Blob; url: string; modality: Modality }

function WebcamStep({
  sessionId,
  images,
  counts,
  onChanged,
}: {
  sessionId: string
  images: C1SavedImage[]
  /** Saved-image counts reported by the server (session state and every upload/delete response). */
  counts: C1CaptureCounts
  onChanged: (change: C1ImageChange) => void
}) {
  const videoRef = React.useRef<HTMLVideoElement>(null)
  const streamRef = React.useRef<MediaStream | null>(null)
  const pendingUrlRef = React.useRef<string | null>(null)
  const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = React.useState("")
  const [live, setLive] = React.useState(false)
  const [modality, setModality] = React.useState<Modality>("conjunctiva")
  const [pending, setPending] = React.useState<PendingCapture | null>(null)
  const [retakeOf, setRetakeOf] = React.useState<C1SavedImage | null>(null)
  const [confirmDelete, setConfirmDelete] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    if (pendingUrlRef.current) URL.revokeObjectURL(pendingUrlRef.current)
  }, [])

  const labelOf = (key: Modality) => MODALITIES.find((item) => item.key === key)?.label ?? key
  const timeOf = (image: C1SavedImage) =>
    image.captured_utc ? new Date(image.captured_utc).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : ""

  const discardPending = () => {
    if (pendingUrlRef.current) URL.revokeObjectURL(pendingUrlRef.current)
    pendingUrlRef.current = null
    setPending(null)
  }

  const stop = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setLive(false)
  }

  const start = async (id = deviceId) => {
    setError(null)
    stop()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: id ? { deviceId: { exact: id }, width: { ideal: 1280 }, height: { ideal: 720 } } : { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setLive(true)
      const all = await navigator.mediaDevices.enumerateDevices()
      setDevices(all.filter((device) => device.kind === "videoinput"))
      setDeviceId(stream.getVideoTracks()[0]?.getSettings().deviceId ?? id)
    } catch {
      setError("Camera unavailable. Allow camera permission in the browser, close other apps using the webcam, or choose another camera.")
    }
  }

  /** Capture to a review panel; nothing is saved until the operator confirms the photo and its modality. */
  const capture = async () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement("canvas")
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext("2d")?.drawImage(video, 0, 0)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"))
    if (!blob) return
    discardPending()
    const url = URL.createObjectURL(blob)
    pendingUrlRef.current = url
    setPending({ blob, url, modality })
    setError(null)
  }

  const save = async () => {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      const change = await component1Api.uploadImage(sessionId, pending.modality, pending.blob, retakeOf?.image_id)
      discardPending()
      setRetakeOf(null)
      onChanged(change)
    } catch (err) {
      setError(`${message(err)}${retakeOf ? " The original image was kept." : ""}`)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (imageId: string) => {
    setBusy(true)
    setError(null)
    try {
      const change = await component1Api.deleteImage(sessionId, imageId)
      setConfirmDelete(null)
      if (retakeOf?.image_id === imageId) setRetakeOf(null)
      onChanged(change)
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  const beginRetake = (image: C1SavedImage) => {
    discardPending()
    setConfirmDelete(null)
    setRetakeOf(image)
    setModality(image.modality)
    if (!live) void start()
  }

  const hint = MODALITIES.find((item) => item.key === modality)?.hint

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 text-xs font-medium text-slate-600">
          Camera
          <select
            className={fieldClass}
            value={deviceId}
            onChange={(event) => {
              setDeviceId(event.target.value)
              void start(event.target.value)
            }}
          >
            {devices.length === 0 && <option value="">Default camera (start preview to list)</option>}
            {devices.map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Camera ${index + 1}`}
              </option>
            ))}
          </select>
        </label>
        {live ? (
          <Button variant="outline" onClick={stop}>
            <CameraOff /> Stop preview
          </Button>
        ) : (
          <Button variant="outline" onClick={() => void start()}>
            <Camera /> Start preview
          </Button>
        )}
      </div>

      {retakeOf && (
        <Notice tone="info" title={`Retaking a ${labelOf(retakeOf.modality)} image`}>
          The original ({timeOf(retakeOf)}) stays saved until the replacement is saved.
          <button type="button" className="ml-2 underline" onClick={() => { discardPending(); setRetakeOf(null) }}>
            Cancel retake
          </button>
        </Notice>
      )}

      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Body region">
        {MODALITIES.map((item) => (
          <button
            key={item.key}
            type="button"
            role="radio"
            aria-checked={modality === item.key}
            onClick={() => setModality(item.key)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold",
              modality === item.key ? "border-emerald-600 bg-emerald-50 text-emerald-900" : "border-slate-200 text-slate-600",
            )}
          >
            {item.label} · {counts[item.key]}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500">{hint}</p>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-950">
        <video ref={videoRef} className="aspect-video w-full object-contain" muted playsInline />
      </div>
      {!pending && (
        <Button disabled={!live || busy} onClick={() => void capture()}>
          <Camera /> {retakeOf ? `Capture replacement` : `Capture ${labelOf(modality)}`}
        </Button>
      )}

      {pending && (
        <div className="grid gap-4 rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 sm:grid-cols-[minmax(0,16rem)_1fr]">
          <img src={pending.url} alt="Captured photograph for review" className="w-full rounded-lg border border-slate-200" />
          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-800">Review before saving</p>
            <fieldset className="space-y-1.5 text-sm">
              <legend className="text-xs font-medium text-slate-600">This photograph shows:</legend>
              {MODALITIES.map((item) => (
                <label key={item.key} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="c1-review-modality"
                    checked={pending.modality === item.key}
                    onChange={() => setPending({ ...pending, modality: item.key })}
                  />
                  {item.label}
                </label>
              ))}
            </fieldset>
            {retakeOf && retakeOf.modality !== pending.modality && (
              <p className="text-xs text-amber-700">
                Saving as {labelOf(pending.modality)} replaces the original {labelOf(retakeOf.modality)} image.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy} onClick={() => void save()}>
                {busy ? "Saving…" : retakeOf ? "Save replacement" : "Save photo"}
              </Button>
              <Button variant="outline" disabled={busy} onClick={() => { discardPending(); void capture() }}>
                {retakeOf ? "Retake again" : "Retake"}
              </Button>
              <Button variant="outline" disabled={busy} onClick={discardPending}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
      {error && <Notice tone="critical">{error}</Notice>}

      {images.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-600">Saved photographs for this session ({images.length})</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {images.map((image) => (
              <figure
                key={image.image_id}
                className={cn(
                  "relative overflow-hidden rounded-lg border",
                  retakeOf?.image_id === image.image_id ? "border-sky-400 ring-2 ring-sky-200" : "border-slate-200",
                )}
              >
                {image.available ? (
                  <img src={component1Api.imageUrl(sessionId, image.image_id)} alt={`${labelOf(image.modality)} photograph`} className="aspect-square w-full object-cover" />
                ) : (
                  <div className="flex aspect-square items-center justify-center bg-slate-50 text-[11px] text-slate-500">file missing</div>
                )}
                <button
                  type="button"
                  aria-label={`Remove ${labelOf(image.modality)} image ${timeOf(image)}`}
                  title="Remove image"
                  disabled={busy}
                  onClick={() => setConfirmDelete(image.image_id)}
                  className="absolute top-1 right-1 flex size-6 items-center justify-center rounded-full bg-white/90 text-sm font-bold text-rose-700 shadow ring-1 ring-slate-200 hover:bg-rose-50"
                >
                  ✕
                </button>
                <figcaption className="space-y-1 px-1.5 py-1 text-[11px] text-slate-600">
                  <span className="block font-semibold">{labelOf(image.modality)}</span>
                  <span className="block text-slate-500">{timeOf(image)}</span>
                  {confirmDelete === image.image_id ? (
                    <span className="block space-y-1">
                      <span className="block text-rose-700">Remove this {labelOf(image.modality)} image?</span>
                      <span className="flex gap-1">
                        <button type="button" className="rounded border border-slate-300 px-1.5" onClick={() => setConfirmDelete(null)}>
                          Cancel
                        </button>
                        <button type="button" disabled={busy} className="rounded bg-rose-600 px-1.5 text-white" onClick={() => void remove(image.image_id)}>
                          Remove image
                        </button>
                      </span>
                    </span>
                  ) : (
                    <button type="button" disabled={busy} className="text-emerald-700 underline" onClick={() => beginRetake(image)}>
                      Retake
                    </button>
                  )}
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const RUNNING: C1PpgJob["state"][] = ["opening", "port_open", "receiving", "processing"]

function jobHeadline(job: C1PpgJob, port: string): { text: string; tone: "info" | "caution" | "critical" | "neutral" } {
  switch (job.state) {
    case "opening":
      return { text: `Opening ${port}…`, tone: "info" }
    case "port_open":
      return { text: `${port} open — waiting for valid RED/IR samples (the ESP32 restarts when the port opens)`, tone: "info" }
    case "receiving":
      return { text: "Receiving live RED/IR samples", tone: "info" }
    case "processing":
      return { text: "Recording finished — running technical-quality checks and saving to SQLite", tone: "info" }
    case "saved":
      return { text: "Recording saved", tone: "neutral" }
    case "probe_ok":
      return { text: "Live signal confirmed (check only — nothing saved)", tone: "neutral" }
    case "cancelled":
      return { text: "Recording cancelled — nothing was saved", tone: "caution" }
    case "failed":
      return { text: job.error ?? "Recording failed", tone: "critical" }
    default:
      return { text: "Not started", tone: "neutral" }
  }
}

function PpgStep({
  sessionId,
  questions,
  consented,
  status,
  recordings,
  onStatus,
  onSaved,
}: {
  sessionId: string
  questions: C1Question[]
  consented: boolean
  status: C1CaptureStatus | null
  recordings: C1SavedRecording[]
  onStatus: (status: C1CaptureStatus) => void
  onSaved: () => void
}) {
  const [answers, setAnswers] = React.useState<Record<string, string>>({})
  const [redoComfort, setRedoComfort] = React.useState(false)
  const [port, setPort] = React.useState<C1PpgJobStatus | null>(null)
  const [job, setJob] = React.useState<C1PpgJob | null>(null)
  const [seconds, setSeconds] = React.useState(20)
  const [error, setError] = React.useState<string | null>(null)
  const [options, setOptions] = React.useState<C1PpgCaptureOptions | null>(null)
  const pollRef = React.useRef<number | null>(null)

  React.useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current)
  }, [])

  // Which capture paths this server offers: its own USB port (localhost) and/or browser Web Serial upload.
  React.useEffect(() => {
    const controller = new AbortController()
    component1Api.ppgCaptureOptions(controller.signal).then(setOptions).catch(() => undefined)
    return () => controller.abort()
  }, [])

  if (!consented) {
    return <Notice tone="neutral">PPG consent was not given in the questionnaire, so this step is skipped. The report will list PPG as missing.</Notice>
  }

  const comfortSaved = status?.ppg_pending_finger_comfort_check === false && !redoComfort
  const cleared = Boolean(status?.ppg_acquisition_allowed) && comfortSaved
  const configured = port?.configured_port ?? "COM11"
  const running = job ? RUNNING.includes(job.state) : false
  // Older APIs have no capture-options route: keep the server USB controls, as before.
  const serverSerial = options?.server_serial_enabled !== false
  const browserUpload = options?.browser_upload_enabled === true

  const checkPort = async () => {
    setError(null)
    try {
      const current = await component1Api.ppgJob()
      setPort(current)
      if (RUNNING.includes(current.job.state)) startPolling()
    } catch (err) {
      setError(message(err))
    }
  }

  const submitComfort = async () => {
    setError(null)
    try {
      onStatus((await component1Api.comfortCheck(sessionId, answers)).status)
      setRedoComfort(false)
      await checkPort()
    } catch (err) {
      setError(message(err))
    }
  }

  const startPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current)
    pollRef.current = window.setInterval(async () => {
      try {
        const current = await component1Api.ppgJob()
        setPort(current)
        setJob(current.job)
        if (!RUNNING.includes(current.job.state)) {
          if (pollRef.current) window.clearInterval(pollRef.current)
          pollRef.current = null
          if (current.job.state === "saved") onSaved()
        }
      } catch (err) {
        setError(message(err))
      }
    }, 500)
  }

  const begin = async (action: () => Promise<C1PpgJob>) => {
    setError(null)
    try {
      setJob(await action())
      startPolling()
    } catch (err) {
      setError(message(err))
    }
  }

  const answered = questions.every((question) => answers[question.id])
  const headline = job ? jobHeadline(job, configured) : null
  const result = job?.state === "saved" ? (job.result as C1RecordingResult) : null
  const probe = job?.state === "probe_ok" ? (job.result as { valid_rows: number; rows_per_second: number }) : null

  return (
    <div className="space-y-4">
      {comfortSaved ? (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className={cleared ? "text-emerald-700" : "text-rose-700"}>
            Finger-comfort check saved: {cleared ? "PPG cleared" : `PPG blocked (${status?.ppg_comfort_blocking_ids?.join(", ") || "consent"})`}
          </span>
          <Button size="sm" variant="outline" disabled={running} onClick={() => setRedoComfort(true)}>
            Redo comfort check
          </Button>
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-700">Finger-comfort check at the sensor (required before any recording).</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {questions.map((question) => (
              <QuestionField
                key={question.id}
                question={question}
                value={answers[question.id]}
                onChange={(value) =>
                  setAnswers((current) => {
                    const next = { ...current }
                    if (value === undefined) delete next[question.id]
                    else next[question.id] = String(value)
                    return next
                  })
                }
              />
            ))}
          </div>
          <Button variant="outline" disabled={!answered} onClick={() => void submitComfort()}>
            Save comfort check
          </Button>
          {!answered && <p className="text-xs text-slate-500">Answer all {questions.length} comfort questions to continue.</p>}
        </>
      )}

      {comfortSaved && !cleared && (
        <Notice tone="caution" title="PPG not cleared">
          The comfort check blocks recording. Continue without PPG; the report will list PPG as missing.
        </Notice>
      )}
      {status?.ppg_optical_obstruction_reported && (
        <Notice tone="caution">Optical obstruction reported (e.g. nail polish); signal quality may be reduced.</Notice>
      )}

      {cleared && browserUpload && options && (
        <BrowserPpgCapture sessionId={sessionId} baud={options.baud} hasRecordings={recordings.length > 0} onSaved={onSaved} />
      )}

      {cleared && !serverSerial && !browserUpload && (
        <Notice tone="neutral" title="PPG capture is not available on this server">
          Continue without PPG; the report will list PPG as missing.
        </Notice>
      )}

      {cleared && serverSerial && browserUpload && (
        <p className="text-xs text-slate-500">Or record through the Component 1 server&apos;s own USB port (local setup):</p>
      )}

      {cleared && serverSerial && (
        <div className="space-y-3 rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
            <Usb className="size-4" aria-hidden />
            {port ? (
              <span>
                {configured} @ {port.configured_baud} baud:{" "}
                <strong className={port.port_listed ? "text-slate-800" : "text-rose-700"}>
                  {port.port_listed ? "port listed by Windows (not yet opened)" : "port not found"}
                </strong>
              </span>
            ) : (
              <span>Sensor port not checked yet.</span>
            )}
            <Button size="sm" variant="outline" disabled={running} onClick={() => void checkPort()}>
              Check port
            </Button>
            <Button size="sm" variant="outline" disabled={running} onClick={() => void begin(component1Api.probePpg)}>
              Test live signal (4 s, not saved)
            </Button>
          </div>
          {port && !port.port_listed && (
            <p className="text-xs text-slate-500">Plug in the ESP32 USB cable, then choose Check port.</p>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs font-medium text-slate-600">
              Duration
              <select className={fieldClass} value={seconds} disabled={running} onChange={(event) => setSeconds(Number(event.target.value))}>
                {[10, 20, 30].map((value) => (
                  <option key={value} value={value}>
                    {value} seconds
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={running} onClick={() => void begin(() => component1Api.recordPpg(sessionId, seconds))}>
              <Activity /> {recordings.length ? "Record another (retake)" : "Record PPG"}
            </Button>
            {running && job?.kind === "recording" && job.state !== "processing" && (
              <Button variant="outline" onClick={() => void component1Api.cancelPpg()}>
                <Square /> Cancel (nothing saved)
              </Button>
            )}
          </div>

          {job && headline && (
            <Notice tone={headline.tone} title={headline.text}>
              <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {job.kind === "recording" && job.seconds && (
                  <span>Elapsed: {job.elapsed_s ?? 0} / {job.seconds} s</span>
                )}
                <span>Valid RED/IR rows received: {job.samples ?? 0}</span>
                <span>Device metrics lines: {job.metrics ?? 0}</span>
                <span>
                  Finger contact (device):{" "}
                  {job.finger_present === null || job.finger_present === undefined ? "not reported yet" : job.finger_present ? "yes" : "no"}
                </span>
                <span>Last device HR: {job.last_hr_bpm ?? "—"} · SpO2: {job.last_spo2_percent ?? "—"}</span>
              </div>
              {probe && <p className="mt-1">{probe.valid_rows} valid rows in 4 s (~{probe.rows_per_second}/s).</p>}
            </Notice>
          )}
        </div>
      )}

      {error && <Notice tone="critical">{error}</Notice>}

      {result && <RecordingSummary result={result} />}

      {recordings.length > 0 && (
        <div className="text-xs text-slate-600">
          <p className="font-semibold text-slate-700">Saved recordings for {sessionId} (the newest is used in fusion):</p>
          <ul className="mt-1 space-y-0.5">
            {recordings.map((recording) => (
              <li key={recording.recording_id}>
                #{recording.recording_id} · {recording.sample_count} samples · {humanize(recording.quality_status)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function Component1IntakeWizard() {
  const [step, setStep] = React.useState(0)
  const [sessionId, setSessionId] = React.useState("")
  const [questionSet, setQuestionSet] = React.useState<C1QuestionSet | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [savedSessions, setSavedSessions] = React.useState<Component1Session[] | null>(null)
  const [resumeId, setResumeId] = React.useState("")

  const [ageYears, setAgeYears] = React.useState(25)
  const [ageMonths, setAgeMonths] = React.useState(0)
  const [sex, setSex] = React.useState("not_recorded")
  const [pregnancy, setPregnancy] = React.useState("not_applicable")
  const [consent, setConsent] = React.useState<"" | "yes" | "no">("")
  const [consentPpg, setConsentPpg] = React.useState(false)
  const [consentImages, setConsentImages] = React.useState(false)
  const [guardian, setGuardian] = React.useState(false)

  const [answers, setAnswers] = React.useState<C1Answers>({})
  const [followups, setFollowups] = React.useState<C1Question[] | null>(null)
  const [noMeds, setNoMeds] = React.useState(false)
  const [meds, setMeds] = React.useState("")
  const [herbals, setHerbals] = React.useState("")
  const [noAllergies, setNoAllergies] = React.useState(false)
  const [allergies, setAllergies] = React.useState("")
  const [status, setStatus] = React.useState<C1CaptureStatus | null>(null)
  const [questionnaireSaved, setQuestionnaireSaved] = React.useState(false)

  const [intake, setIntake] = React.useState<C1IntakeState | null>(null)
  const [counts, setCounts] = React.useState<C1CaptureCounts>(EMPTY_COUNTS)
  const [report, setReport] = React.useState<Component1Report | null>(null)
  const [imagesChanged, setImagesChanged] = React.useState(false)
  // Patient registration (name + phone): only through protected Component 1 routes, never in URLs or session IDs.
  const [patientStatus, setPatientStatus] = React.useState<C1PatientDataStatus | null>(null)
  const [patient, setPatient] = React.useState<C1Patient | null>(null)
  const registrationId = React.useRef(newRequestId()) // one per registration form: a retry never creates a second session
  const patientFeatures = patientFeaturesAvailable(patientStatus)

  React.useEffect(() => {
    const controller = new AbortController()
    component1Api.patientDataStatus(controller.signal).then(setPatientStatus).catch(() => undefined)
    return () => controller.abort()
  }, [])

  const ageTotal = ageYears * 12 + ageMonths
  const isChild = ageTotal < 216
  const pregnant = pregnancy === "pregnant"
  const profile = { age_months: ageTotal, sex, pregnancy_status: pregnancy }
  // Same rules as the Component 1 API (intake._profile): from age 15 the WHO Hb cut-off depends on sex.
  const sexRequired = ageTotal >= 180
  const profileIssues = [
    ...(sexRequired && sex === "not_recorded"
      ? ["Select the patient's sex (required from age 15). “Intersex” or “Prefer not to answer” are accepted."]
      : []),
    ...(sex === "male" && pregnant ? ["“Male” cannot be combined with pregnancy status “Pregnant”. Correct one of the two fields."] : []),
  ]
  const noAdultCutoff = sexRequired && !pregnant && (sex === "intersex" || sex === "prefer_not_to_answer")
  const commonQuestions = questionSet
    ? pregnant
      ? [...questionSet.common.slice(0, 4), questionSet.pregnancy_safety, ...questionSet.common.slice(4)]
      : questionSet.common
    : []
  // Same rule as the questionnaire engine: PR06 is a safety question only in pregnancy.
  const safetyIds = (questionSet?.safety_ids ?? []).filter((id) => id !== "PR06" || pregnant)
  const questionText = (id: string) => commonQuestions.find((question) => question.id === id)?.prompt ?? id
  const urgentIds = safetyIds.filter((id) => answers[id] === "yes")
  const unresolvedIds = safetyIds.filter((id) => UNRESOLVED.has(String(answers[id])))
  const unansweredCommon = commonQuestions.filter((question) => answers[question.id] === undefined)
  const referral = report?.outcome === "safety_referral"

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setImagesChanged(false)
    setStep(0)
    setSessionId("")
    setAnswers({})
    setFollowups(null)
    setStatus(null)
    setQuestionnaireSaved(false)
    setReport(null)
    setIntake(null)
    setCounts(EMPTY_COUNTS)
    setConsent("")
    setConsentPpg(false)
    setConsentImages(false)
    setGuardian(false)
    setNoMeds(false)
    setMeds("")
    setHerbals("")
    setNoAllergies(false)
    setAllergies("")
    setError(null)
    setSavedSessions(null)
    setPatient(null)
    registrationId.current = newRequestId()
  }

  const setAnswer = (id: string, value: string | number | undefined) =>
    setAnswers((current) => {
      const next = { ...current }
      if (value === undefined) delete next[id]
      else next[id] = value
      return next
    })

  const refreshIntake = async (id = sessionId) => {
    const state = await component1Api.intakeState(id)
    setIntake(state)
    setCounts(state.captures)
    return state
  }

  const startSession = () =>
    run(async () => {
      const [created, questions] = await Promise.all([component1Api.createSession(), component1Api.questions()])
      setSessionId(created.session_id)
      setQuestionSet(questions)
      await refreshIntake(created.session_id)
      setStep(1)
    })

  /** Registers name + phone and creates the session in one request (same request ID on retry: no duplicate session). */
  const registerAndStart = (fullName: string, phone: string) =>
    run(async () => {
      const [registered, questions] = await Promise.all([
        component1Api.registerPatient({ request_id: registrationId.current, full_name: fullName, phone }),
        component1Api.questions(),
      ])
      setPatient(registered.patient)
      setSessionId(registered.session_id)
      setQuestionSet(questions)
      await refreshIntake(registered.session_id)
      setStep(1)
    })

  const listSessions = () =>
    run(async () => {
      const list = (await component1Api.sessions()).sessions ?? []
      setSavedSessions(list)
      setResumeId(list.find((session) => session.workflow_state !== "completed")?.session_id ?? list[0]?.session_id ?? "")
    })

  /** Reload a saved session from the backend (after a page refresh) without creating a new one. */
  const resume = () =>
    run(async () => {
      const [state, questions] = await Promise.all([component1Api.intakeState(resumeId), component1Api.questions()])
      setQuestionSet(questions)
      setSessionId(state.session_id)
      setIntake(state)
      setCounts(state.captures)
      const q = state.questionnaire
      if (q) {
        const saved = q.answers
        const months = q.profile.age_months ?? 0
        setAgeYears(Math.floor(months / 12))
        setAgeMonths(months % 12)
        setSex(q.profile.sex_reported_for_demo ?? q.profile.sex ?? "not_recorded")
        setPregnancy(q.profile.pregnancy_status ?? "not_applicable")
        setConsent(saved.REG05 === "yes" ? "yes" : "")
        setConsentPpg(saved.REG06 === "yes")
        setConsentImages(saved.REG07 === "yes")
        setGuardian(saved.CH02 === "yes")
        setAnswers(
          Object.fromEntries(
            Object.entries(saved).filter(
              ([key, value]) => (typeof value === "string" || typeof value === "number") && !/^(REG0[2567]|CH02|C1[567])$/.test(key),
            ),
          ) as C1Answers,
        )
        setMeds(listToText(saved.MED01, "name", "dose_or_details"))
        setHerbals(listToText(saved.MED02, "name", "dose_or_details"))
        setAllergies(listToText(saved.ALG01, "substance", "reaction_or_details"))
        setNoMeds(saved.C15 === "no" && saved.C16 === "no")
        setNoAllergies(saved.C17 === "no")
        setStatus(q.status)
        setQuestionnaireSaved(q.completion_status !== "safety_referral")
        setFollowups(null)
      }
      const target: Record<string, number> = {
        created: 1,
        images_in_progress: 3,
        ppg_in_progress: 4,
        ready_for_analysis: 5,
        completed: 5,
        safety_referral: 5,
      }
      setReport(
        state.workflow_state === "completed" || state.workflow_state === "safety_referral"
          ? await component1Api.report(state.session_id)
          : null,
      )
      // Sessions from before registration existed have no details (404): they stay coded sessions.
      setPatient(patientFeatures ? await component1Api.patient(state.session_id).then((r) => r.patient).catch(() => null) : null)
      setStep(target[state.workflow_state] ?? 1)
    })

  const loadFollowups = () =>
    run(async () => {
      setFollowups((await component1Api.followups(profile, answers)).followups)
    })

  const referToClinician = () =>
    run(async () => {
      const result = await component1Api.referral(sessionId, {
        profile,
        consent: consent === "yes",
        consent_ppg: consentPpg,
        consent_images: consentImages,
        guardian_permission: guardian,
        answers,
      })
      setReport(result)
      setQuestionnaireSaved(false)
      await refreshIntake()
      setStep(5)
    })

  const saveQuestionnaire = () =>
    run(async () => {
      const result = await component1Api.saveQuestionnaire(sessionId, {
        profile,
        consent: consent === "yes",
        consent_ppg: consentPpg,
        consent_images: consentImages,
        guardian_permission: guardian,
        answers,
        medications: noMeds ? "" : meds,
        herbals: noMeds ? "" : herbals,
        allergies: noAllergies ? "" : allergies,
        no_medications: noMeds,
        no_allergies: noAllergies,
      })
      setStatus(result.status)
      setQuestionnaireSaved(true)
      await refreshIntake()
      setStep(result.status.image_acquisition_allowed ? 3 : consentPpg ? 4 : 5)
    })

  const analyze = () =>
    run(async () => {
      setReport(await component1Api.analyze(sessionId))
      setImagesChanged(false)
      await refreshIntake()
    })

  const commonDone = commonQuestions.length > 0 && unansweredCommon.length === 0
  const medsDone = noMeds ? !meds.trim() && !herbals.trim() : Boolean(meds.trim() || herbals.trim())
  const allergiesDone = noAllergies ? !allergies.trim() : Boolean(allergies.trim())
  const consentDone = consent === "yes" && (!isChild || guardian)
  const imageCount = counts.conjunctiva + counts.nails + counts.tongue
  const recordings = intake?.ppg_recordings ?? []
  const imagesAllowed = Boolean(status?.image_acquisition_allowed)

  const stepStatus = (index: number): { status: StepStatus; reason?: string } => {
    if (index === step) return { status: "current" }
    if (referral) {
      if (index <= 2 || index === 5) return { status: "completed" }
      return { status: "blocked", reason: "Safety referral: routine acquisition stopped" }
    }
    switch (index) {
      case 0:
        return { status: sessionId ? "completed" : "pending" }
      case 1:
        return sessionId
          ? { status: (consentDone && profileIssues.length === 0) || questionnaireSaved ? "completed" : "pending" }
          : { status: "blocked", reason: "Start a session first" }
      case 2:
        if (questionnaireSaved) return { status: "completed" }
        if (profileIssues.length > 0) return { status: "blocked", reason: "Correct the patient details" }
        return consentDone ? { status: "pending" } : { status: "blocked", reason: "Consent required" }
      case 3:
        if (!questionnaireSaved) return { status: "blocked", reason: "Save the questionnaire first" }
        if (!imagesAllowed) return { status: "skipped", reason: "No image consent" }
        return { status: imageCount ? "completed" : "pending" }
      case 4:
        if (!questionnaireSaved) return { status: "blocked", reason: "Save the questionnaire first" }
        if (!consentPpg) return { status: "skipped", reason: "No PPG consent" }
        if (status?.ppg_pending_finger_comfort_check === false && !status.ppg_acquisition_allowed)
          return { status: "skipped", reason: "Blocked by the finger-comfort check" }
        return { status: recordings.length ? "completed" : "pending" }
      default:
        if (!questionnaireSaved) return { status: "blocked", reason: "Save the questionnaire first" }
        return { status: report ? "completed" : "pending" }
    }
  }

  return (
    <Panel
      title="AyurAI Clinical Screening"
      description="New coded session → consent and adaptive questionnaire → safety decision → webcam images → PPG → quality checks, trained models and reliability-aware fusion → clinician report."
      actions={
        sessionId ? (
          <Button variant="outline" size="sm" onClick={reset}>
            <RotateCcw /> New / switch patient
          </Button>
        ) : undefined
      }
    >
      <Notice tone="neutral" icon={FlaskConical} className="mb-4">
        <strong className="font-semibold">Research prototype</strong> — Experimental AI-assisted anaemia screening. Clinician
        review required.
      </Notice>

      {sessionId && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-700">Current patient session:</span>
          <IdChip>{sessionId}</IdChip>
          {intake && <span>· {stateLabels[intake.workflow_state] ?? intake.workflow_state}</span>}
          <span>· everything below is saved to this session only</span>
        </div>
      )}
      {sessionId && patientFeatures && <PatientBanner sessionId={sessionId} patient={patient} onChanged={setPatient} />}

      <ol className="mb-5 flex flex-wrap gap-2" aria-label="Intake steps">
        {STEPS.map((label, index) => {
          const { status: state, reason } = stepStatus(index)
          const navigable = sessionId !== "" && state !== "blocked" && !(referral && index !== 5)
          return (
            <li key={label}>
              <button
                type="button"
                disabled={!navigable}
                title={reason ?? state}
                aria-current={state === "current" ? "step" : undefined}
                onClick={() => setStep(index)}
                className={cn("rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset", stepStyles[state], !navigable && "cursor-not-allowed")}
              >
                {index + 1}. {label}
                <span className="ml-1 font-normal opacity-80">· {reason ? `${state}: ${reason}` : state}</span>
              </button>
            </li>
          )
        })}
      </ol>

      {step === 0 && (
        <div className="space-y-4">
          {patientFeatures ? (
            <section className="space-y-3 rounded-xl border border-slate-200 p-4" aria-label="Patient registration">
              <h3 className="text-xs font-semibold text-slate-500 uppercase">Patient registration</h3>
              <p className="text-sm text-slate-700">
                Enter the patient&apos;s details first. They are stored separately from the screening data and are never used in the
                session ID or file names.
              </p>
              <PatientDetailsForm submitLabel="Register patient and start session" busy={busy} onSubmit={registerAndStart} />
            </section>
          ) : (
            <div className="space-y-2">
              <RegistrationUnavailable status={patientStatus} />
              <p className="text-sm text-slate-700">Creates one coded session folder used by every step; no name or identifier is collected.</p>
              <Button disabled={busy} onClick={() => void startSession()}>
                <Play /> Start new screening session
              </Button>
            </div>
          )}
          <div className="space-y-2 rounded-xl border border-slate-200 p-4">
            <p className="text-sm text-slate-700">Continue an unfinished session (for example after a page refresh) — no new session is created.</p>
            {savedSessions === null ? (
              <Button variant="outline" disabled={busy} onClick={() => void listSessions()}>
                <History /> Find saved sessions
              </Button>
            ) : savedSessions.length === 0 ? (
              <p className="text-xs text-slate-500">No saved sessions found.</p>
            ) : (
              <div className="flex flex-wrap items-end gap-3">
                <label className="min-w-72 text-xs font-medium text-slate-600">
                  Saved session
                  <select className={fieldClass} value={resumeId} onChange={(event) => setResumeId(event.target.value)}>
                    {savedSessions.map((session) => (
                      <option key={session.session_id} value={session.session_id}>
                        {session.session_id} · {stateLabels[session.workflow_state ?? ""] ?? session.workflow_state} · {session.image_count ?? 0} images
                      </option>
                    ))}
                  </select>
                </label>
                <Button variant="outline" disabled={busy || !resumeId} onClick={() => void resume()}>
                  Resume this session
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Fictional test participants only: real patient data must not be entered until the questionnaire and research
            protocol are approved.{" "}
            {patientFeatures
              ? "Name and phone are kept in separate protected storage; the clinical answers below stay linked only to the coded session ID."
              : "No names or identifiers are collected."}
          </p>
          {questionnaireSaved && (
            <Notice tone="info">The questionnaire for this session is already saved; changing these details requires saving it again in step 3.</Notice>
          )}
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="text-xs font-medium text-slate-600">
              Age (years)
              <input className={fieldClass} type="number" min={0} max={120} value={ageYears} onChange={(e) => setAgeYears(Math.max(0, Number(e.target.value) || 0))} />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Extra months
              <input className={fieldClass} type="number" min={0} max={11} value={ageMonths} onChange={(e) => setAgeMonths(Math.min(11, Math.max(0, Number(e.target.value) || 0)))} />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Sex (patient-reported)
              <select className={fieldClass} value={sex} onChange={(e) => setSex(e.target.value)}>
                {["not_recorded", "female", "male", "intersex", "prefer_not_to_answer"].map((value) => (
                  <option key={value} value={value}>{humanize(value)}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Pregnancy status
              <select className={fieldClass} value={pregnancy} onChange={(e) => setPregnancy(e.target.value)}>
                {["not_applicable", "pregnant", "not_pregnant", "unknown", "prefer_not_to_answer"].map((value) => (
                  <option key={value} value={value}>{humanize(value)}</option>
                ))}
              </select>
            </label>
          </div>
          {profileIssues.length > 0 && (
            <Notice tone="caution">
              {profileIssues.map((issue) => <p key={issue}>{issue}</p>)}
            </Notice>
          )}
          {noAdultCutoff && (
            <Notice tone="info">
              No WHO adult haemoglobin cut-off exists for this sex value, so nail Hb regression estimates will not be used in the
              screening result. Image classification and questionnaire evidence are still used.
            </Notice>
          )}

          <fieldset className="space-y-2 rounded-xl border border-slate-200 p-4 text-sm text-slate-800">
            <legend className="px-1 text-xs font-semibold text-slate-500 uppercase">Consent</legend>
            <p>Has the procedure been explained, and does the patient agree to the questionnaire and screening tests?</p>
            <div className="flex gap-4">
              {(["yes", "no"] as const).map((value) => (
                <label key={value} className="flex items-center gap-2">
                  <input type="radio" name="c1-consent" checked={consent === value} onChange={() => setConsent(value)} /> {value === "yes" ? "Yes" : "No"}
                </label>
              ))}
            </div>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={consentImages} onChange={(e) => setConsentImages(e.target.checked)} />
              Separately allow webcam photographs (conjunctiva, nails, tongue)
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={consentPpg} onChange={(e) => setConsentPpg(e.target.checked)} />
              Separately allow finger PPG recording
            </label>
            {isChild && (
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={guardian} onChange={(e) => setGuardian(e.target.checked)} />
                Guardian permission confirmed (required under 18)
              </label>
            )}
          </fieldset>
          {consent === "no" && <Notice tone="neutral">Consent declined. The interview stops here and nothing is saved.</Notice>}
          <Button disabled={!consentDone || profileIssues.length > 0} onClick={() => setStep(2)}>
            Next: questionnaire
          </Button>
          {!consentDone && consent !== "no" && (
            <p className="text-xs text-slate-500">
              {consent === "" ? "Record the patient's consent answer to continue." : "Confirm guardian permission for a patient under 18."}
            </p>
          )}
          {consentDone && profileIssues.length > 0 && (
            <p className="text-xs text-slate-500">Correct the patient details above to continue.</p>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <section className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-500 uppercase">Safety and common symptoms</h3>
            <p className="text-xs text-slate-500">
              Questions marked ⚠ are immediate-safety questions. “Yes” to a symptom question (e.g. tiredness, breathlessness on activity)
              is screening evidence and does not stop the screening.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {commonQuestions.map((question) => (
                <div key={question.id}>
                  {safetyIds.includes(question.id) && <span className="text-xs font-semibold text-rose-700">⚠ Immediate safety</span>}
                  <QuestionField
                    question={question}
                    value={answers[question.id]}
                    invalid={answers[question.id] === undefined && followups === null && unansweredCommon.length < commonQuestions.length}
                    onChange={(value) => {
                      setAnswer(question.id, value)
                      setFollowups(null)
                    }}
                  />
                </div>
              ))}
            </div>

            {urgentIds.length > 0 ? (
              <Notice tone="critical" icon={ShieldAlert} title="Urgent safety answer — routine screening stops">
                <p>
                  {urgentIds.map(questionText).join(" · ")} — answered “yes”. Webcam and PPG acquisition are not allowed. Refer the
                  patient for immediate clinician assessment. The answers already given are saved with the referral record; no AI
                  anaemia-risk classification is produced.
                </p>
                <Button size="sm" className="mt-2" disabled={busy} onClick={() => void referToClinician()}>
                  Stop and refer to clinician
                </Button>
              </Notice>
            ) : unresolvedIds.length > 0 ? (
              <Notice tone="caution" title="Safety answer needs clarification">
                <p>
                  {unresolvedIds.map(questionText).join(" · ")} — not resolved ({unresolvedIds.map((id) => humanize(String(answers[id]))).join(", ")}).
                  Clarify the answer as “yes” or “no” with the patient. If it cannot be clarified, stop and refer: routine
                  screening cannot continue with an unresolved safety question.
                </p>
                <Button size="sm" variant="outline" className="mt-2" disabled={busy} onClick={() => void referToClinician()}>
                  Cannot clarify — stop and refer to clinician
                </Button>
              </Notice>
            ) : followups === null ? (
              <div className="space-y-1">
                <Button variant="outline" disabled={!commonDone || busy} onClick={() => void loadFollowups()}>
                  Next: adaptive follow-up questions
                </Button>
                {!commonDone && (
                  <p className="text-xs text-amber-700">
                    {unansweredCommon.length} question(s) still unanswered: {unansweredCommon.map((q) => q.prompt).join(" · ")}. Choose
                    “not sure” or “prefer not to answer” if the patient cannot answer — these are recorded as unknown, never as “no”.
                  </p>
                )}
              </div>
            ) : null}
          </section>

          {followups !== null && urgentIds.length === 0 && unresolvedIds.length === 0 && (
            <>
              <section className="space-y-3">
                <h3 className="text-xs font-semibold text-slate-500 uppercase">
                  Adaptive follow-ups ({followups.length}) — selected by the rule engine from the answers above
                </h3>
                {followups.length === 0 && <p className="text-xs text-slate-500">No follow-ups apply.</p>}
                <div className="grid gap-3 sm:grid-cols-2">
                  {followups.map((question) => (
                    <QuestionField key={question.id} question={question} value={answers[question.id]} onChange={(value) => setAnswer(question.id, value)} />
                  ))}
                </div>
                <p className="text-xs text-slate-500">Follow-ups are optional; unanswered ones are stored as not answered.</p>
              </section>

              <section className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 text-sm">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase">Current medicines</h3>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={noMeds} onChange={(e) => setNoMeds(e.target.checked)} /> No current medicines,
                    supplements or herbal products
                  </label>
                  <textarea className={cn(fieldClass, "h-16 py-2")} disabled={noMeds} placeholder="name | dose, frequency (one per line)" value={meds} onChange={(e) => setMeds(e.target.value)} />
                  <textarea className={cn(fieldClass, "h-16 py-2")} disabled={noMeds} placeholder="Ayurvedic / herbal: name | details" value={herbals} onChange={(e) => setHerbals(e.target.value)} />
                </div>
                <div className="space-y-2 text-sm">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase">Allergies</h3>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={noAllergies} onChange={(e) => setNoAllergies(e.target.checked)} /> No known allergies
                  </label>
                  <textarea className={cn(fieldClass, "h-16 py-2")} disabled={noAllergies} placeholder="substance | reaction (one per line)" value={allergies} onChange={(e) => setAllergies(e.target.value)} />
                </div>
              </section>

              <div className="space-y-1">
                <Button disabled={busy || !medsDone || !allergiesDone} onClick={() => void saveQuestionnaire()}>
                  {questionnaireSaved ? "Save changes and continue" : "Save questionnaire and continue"}
                </Button>
                {(!medsDone || !allergiesDone) && (
                  <p className="text-xs text-amber-700">
                    {!medsDone && "Answer the medicines question (list them, or tick “No current medicines”). "}
                    {!allergiesDone && "Answer the allergies question (list them, or tick “No known allergies”)."}
                  </p>
                )}
              </div>
            </>
          )}

          {questionnaireSaved && followups === null && urgentIds.length === 0 && unresolvedIds.length === 0 && (
            <Notice tone="info">
              This session's questionnaire is saved. Continue to the next step, or load the follow-ups to edit and save again.
              <div className="mt-2">
                <Button size="sm" onClick={() => setStep(imagesAllowed ? 3 : consentPpg ? 4 : 5)}>
                  Continue
                </Button>
              </div>
            </Notice>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          {imagesAllowed ? (
            <WebcamStep
              sessionId={sessionId}
              images={intake?.images ?? []}
              counts={counts}
              onChanged={(change) => {
                setCounts(change.captures)
                setIntake((current) => (current ? { ...current, images: change.images, captures: change.captures } : current))
                if (report) {
                  setReport(null) // earlier results no longer describe the saved images
                  setImagesChanged(true)
                }
                void refreshIntake().catch(() => undefined)
              }}
            />
          ) : (
            <Notice tone="neutral">Webcam capture is not permitted by the questionnaire consent. The report will list images as missing.</Notice>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => setStep(4)}>{imageCount ? `Next: PPG (${imageCount} images saved)` : "Continue without images"}</Button>
            {imagesAllowed && (
              <span className="text-xs text-slate-500">
                Saved: {MODALITIES.map((item) => `${item.label} ${counts[item.key]}`).join(" · ")}. Missing regions are reported as missing, never as normal.
              </span>
            )}
          </div>
        </div>
      )}

      {step === 4 && questionSet && (
        <div className="space-y-4">
          <PpgStep
            sessionId={sessionId}
            questions={questionSet.ppg_comfort}
            consented={consentPpg}
            status={status}
            recordings={recordings}
            onStatus={setStatus}
            onSaved={() => void refreshIntake()}
          />
          <Button
            onClick={() =>
              void run(async () => {
                await refreshIntake() // a recording may have finished after leaving the PPG panel
                setStep(5)
              })
            }
          >
            {recordings.length ? "Next: analyse and report" : "Continue without PPG"}
          </Button>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-4">
          {!report && (
            <>
              {imagesChanged && (
                <Notice tone="caution" title="Images changed — re-run analysis">
                  Images were added, removed or replaced after the last analysis. The previous results are outdated and are
                  no longer shown; run the analysis again to update them.
                </Notice>
              )}
              <KeyValueList
                items={[
                  { label: "Session", value: sessionId },
                  { label: "Questionnaire", value: questionnaireSaved ? "saved" : "not saved" },
                  ...MODALITIES.map((item) => ({ label: `${item.label} images saved`, value: String(counts[item.key]) })),
                  {
                    label: "PPG recordings saved",
                    value: recordings.length
                      ? `${recordings.length} (newest: ${recordings[recordings.length - 1].sample_count} samples, ${humanize(recordings[recordings.length - 1].quality_status)})`
                      : "none",
                  },
                ]}
              />
              {(imageCount === 0 || recordings.length === 0) && (
                <Notice tone="caution" title="Incomplete evidence">
                  Missing: {[imageCount === 0 && "webcam images", recordings.length === 0 && "PPG"].filter(Boolean).join(" and ")}. Analysis will
                  report these as missing and may return “Insufficient Evidence” — it never treats missing evidence as normal.
                </Notice>
              )}
              <p className="text-sm text-slate-700">
                Runs image technical-quality checks, the existing trained models on accepted images, then reliability-aware fusion with
                the questionnaire and PPG evidence. The record is saved to this session's folder.
              </p>
              <Button disabled={busy || !questionnaireSaved} onClick={() => void analyze()}>
                <Play /> {busy ? "Analysing… (models load on first run)" : "Analyse and generate clinician report"}
              </Button>
              {busy && <LoadingState label="Running quality checks, models and fusion…" lines={2} />}
            </>
          )}
          {report && (
            <>
              <div className="flex flex-wrap justify-end gap-2">
                {!referral && (
                  <Button variant="outline" size="sm" disabled={busy} onClick={() => void analyze()}>
                    <RotateCcw /> Re-run analysis
                  </Button>
                )}
                <Button variant="outline" size="sm" disabled={report.analysis_outdated} onClick={() => void run(async () => downloadJson(`${sessionId}-screening-result.json`, await component1Api.screeningResult(sessionId)))}>
                  <Download /> {referral ? "Referral record JSON" : "C1 screening JSON"}
                </Button>
                {!referral && (
                  <Button variant="outline" size="sm" disabled={report.analysis_outdated} onClick={() => void run(async () => downloadJson(`${sessionId}-c2-payload.json`, await component1Api.c2Payload(sessionId)))}>
                    <Download /> Component 2 payload
                  </Button>
                )}
                {patientFeatures && <PdfReportButton sessionId={sessionId} disabled={report.analysis_outdated} />}
              </div>
              <ReportView report={report} />
            </>
          )}
        </div>
      )}

      {error && <Notice tone="critical" className="mt-4">{error}</Notice>}
      {step > 1 && !referral && (
        <button type="button" className="mt-4 text-xs text-slate-500 underline" onClick={() => setStep(step - 1)}>
          ← Back (answers and saved evidence are kept)
        </button>
      )}
    </Panel>
  )
}
