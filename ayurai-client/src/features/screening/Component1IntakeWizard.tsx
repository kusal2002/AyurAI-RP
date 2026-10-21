import * as React from "react"
import { Activity, Camera, CameraOff, Download, FlaskConical, Play, RotateCcw, Usb } from "lucide-react"

import { IdChip, KeyValueList, LoadingState, Notice, Panel, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { component1Api } from "@/lib/api/component1"
import type {
  C1Answers,
  C1CaptureCounts,
  C1CaptureStatus,
  C1PpgSummary,
  C1Question,
  C1QuestionSet,
  C1SerialPorts,
  Component1Report,
} from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { ReportView, downloadJson } from "@/features/screening/Component1SessionPanel"

const STEPS = ["Session", "Patient & consent", "Questionnaire", "Webcam", "PPG sensor", "Report"] as const
type Modality = keyof C1CaptureCounts
const MODALITIES: { key: Modality; label: string; hint: string }[] = [
  { key: "conjunctiva", label: "Conjunctiva", hint: "Gently pull down the lower eyelid; fill the frame with the inner eyelid." },
  { key: "nails", label: "Nail beds", hint: "Fingers flat, nails facing the camera, no polish." },
  { key: "tongue", label: "Tongue", hint: "Tongue extended, even lighting, no food colouring." },
]

function message(error: unknown) {
  return error instanceof ApiError ? error.message : "Component 1 returned an unexpected error."
}

function humanize(value: string) {
  return value.replace(/_/g, " ")
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: C1Question
  value: string | number | undefined
  onChange: (value: string | number | undefined) => void
}) {
  return (
    <label className="block text-sm text-slate-800">
      <span className="font-medium">{question.prompt}</span>
      {question.type === "choice" ? (
        <select
          className={fieldClass}
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
          placeholder="Fictional answer"
          onChange={(event) => onChange(event.target.value || undefined)}
        />
      )}
    </label>
  )
}

function WebcamStep({
  sessionId,
  initialCounts,
  onCounts,
}: {
  sessionId: string
  initialCounts: C1CaptureCounts
  onCounts: (counts: C1CaptureCounts) => void
}) {
  const videoRef = React.useRef<HTMLVideoElement>(null)
  const streamRef = React.useRef<MediaStream | null>(null)
  const thumbsRef = React.useRef<string[]>([])
  const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = React.useState("")
  const [live, setLive] = React.useState(false)
  const [modality, setModality] = React.useState<Modality>("conjunctiva")
  const [thumbs, setThumbs] = React.useState<{ url: string; modality: Modality }[]>([])
  const [counts, setCounts] = React.useState<C1CaptureCounts>(initialCounts)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    const urls = thumbsRef.current
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

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

  const capture = async () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement("canvas")
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext("2d")?.drawImage(video, 0, 0)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"))
    if (!blob) return
    setBusy(true)
    setError(null)
    try {
      const result = await component1Api.uploadImage(sessionId, modality, blob)
      const url = URL.createObjectURL(blob)
      thumbsRef.current.push(url)
      setThumbs((current) => [...current, { url, modality }])
      setCounts(result.captures)
      onCounts(result.captures)
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
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
      <Button disabled={!live || busy} onClick={() => void capture()}>
        <Camera /> {busy ? "Saving…" : `Capture ${MODALITIES.find((item) => item.key === modality)?.label}`}
      </Button>
      {error && <Notice tone="critical">{error}</Notice>}

      {thumbs.length > 0 && (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {thumbs.map((thumb) => (
            <figure key={thumb.url} className="overflow-hidden rounded-lg border border-slate-200">
              <img src={thumb.url} alt={`${thumb.modality} capture`} className="aspect-square w-full object-cover" />
              <figcaption className="px-1.5 py-1 text-[11px] text-slate-500 capitalize">{thumb.modality}</figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  )
}

function PpgStep({
  sessionId,
  questions,
  consented,
}: {
  sessionId: string
  questions: C1Question[]
  consented: boolean
}) {
  const [answers, setAnswers] = React.useState<Record<string, string>>({})
  const [status, setStatus] = React.useState<C1CaptureStatus | null>(null)
  const [ports, setPorts] = React.useState<C1SerialPorts | null>(null)
  const [seconds, setSeconds] = React.useState(20)
  const [elapsed, setElapsed] = React.useState<number | null>(null)
  const [summary, setSummary] = React.useState<C1PpgSummary | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  if (!consented) {
    return <Notice tone="neutral">PPG consent was not given in the questionnaire. Skip this step.</Notice>
  }

  const submitComfort = async () => {
    setError(null)
    try {
      setStatus((await component1Api.comfortCheck(sessionId, answers)).status)
      setPorts(await component1Api.serialPorts())
    } catch (err) {
      setError(message(err))
    }
  }

  const record = async () => {
    setError(null)
    setSummary(null)
    const started = Date.now()
    setElapsed(0)
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 500)
    try {
      setSummary(await component1Api.recordPpg(sessionId, seconds))
    } catch (err) {
      setError(message(err))
    } finally {
      window.clearInterval(timer)
      setElapsed(null)
    }
  }

  const detected = ports?.ports.some((port) => port.device === ports.configured_port)
  const answered = questions.every((question) => answers[question.id])

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-700">Finger-comfort check at the sensor (required before recording).</p>
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

      {status && !status.ppg_acquisition_allowed && (
        <Notice tone="caution" title="PPG not cleared">
          Recording is blocked by the comfort check ({status.ppg_comfort_blocking_ids?.join(", ") || "consent"}). Skip this step.
        </Notice>
      )}
      {status?.ppg_optical_obstruction_reported && (
        <Notice tone="caution">Optical obstruction reported (e.g. nail polish); signal quality may be reduced.</Notice>
      )}

      {status?.ppg_acquisition_allowed && ports && (
        <div className="space-y-3 rounded-xl border border-slate-200 p-4">
          <p className="flex items-center gap-2 text-sm text-slate-700">
            <Usb className="size-4" aria-hidden />
            ESP32-S3 + MAX30102 on {ports.configured_port} @ {ports.configured_baud} baud:{" "}
            <strong className={detected ? "text-emerald-700" : "text-rose-700"}>{detected ? "detected" : "not detected"}</strong>
          </p>
          {!detected && (
            <p className="text-xs text-slate-500">
              Plug in the sensor, or close Arduino Serial Monitor / the Streamlit Live PPG page if they hold the port.
            </p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs font-medium text-slate-600">
              Duration
              <select className={fieldClass} value={seconds} onChange={(event) => setSeconds(Number(event.target.value))}>
                {[10, 20, 30].map((value) => (
                  <option key={value} value={value}>
                    {value} seconds
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={elapsed !== null} onClick={() => void record()}>
              <Activity /> {elapsed !== null ? `Recording… ${elapsed}s (keep finger still)` : "Record PPG"}
            </Button>
          </div>
        </div>
      )}

      {error && <Notice tone="critical">{error}</Notice>}
      {summary && (
        <KeyValueList
          items={[
            { label: "RED/IR samples", value: `${summary.sample_count} @ ${summary.observed_receive_rate_hz ?? "?"} Hz` },
            { label: "Technical status", value: humanize(summary.quality_status ?? "unknown") },
            { label: "Experimental HR", value: summary.median_experimental_hr_bpm != null ? `${summary.median_experimental_hr_bpm} bpm` : "—" },
            { label: "Experimental SpO2", value: summary.median_experimental_spo2_percent != null ? `${summary.median_experimental_spo2_percent}%` : "—" },
            { label: "Temperature", value: summary.median_temperature_c != null ? `${summary.median_temperature_c} °C` : "N/A (no sensor)" },
            { label: "Hb model applied", value: "No — live PPG Hb transfer is not validated" },
          ]}
        />
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
  const [stopped, setStopped] = React.useState(false)

  const [counts, setCounts] = React.useState<C1CaptureCounts>({ conjunctiva: 0, nails: 0, tongue: 0 })
  const [report, setReport] = React.useState<Component1Report | null>(null)

  const ageTotal = ageYears * 12 + ageMonths
  const isChild = ageTotal < 216
  const profile = { age_months: ageTotal, sex, pregnancy_status: pregnancy }
  const commonQuestions = questionSet
    ? pregnancy === "pregnant"
      ? [...questionSet.common.slice(0, 4), questionSet.pregnancy_safety, ...questionSet.common.slice(4)]
      : questionSet.common
    : []
  const safetyTriggered = questionSet?.safety_ids.some((id) => answers[id] !== undefined && answers[id] !== "no") ?? false

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.message.toLowerCase().includes("safety")) setStopped(true)
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setStep(0)
    setSessionId("")
    setAnswers({})
    setFollowups(null)
    setStatus(null)
    setStopped(false)
    setReport(null)
    setCounts({ conjunctiva: 0, nails: 0, tongue: 0 })
    setConsent("")
    setError(null)
  }

  const setAnswer = (id: string, value: string | number | undefined) =>
    setAnswers((current) => {
      const next = { ...current }
      if (value === undefined) delete next[id]
      else next[id] = value
      return next
    })

  const startSession = () =>
    run(async () => {
      const [created, questions] = await Promise.all([component1Api.createSession(), component1Api.questions()])
      setSessionId(created.session_id)
      setQuestionSet(questions)
      setStep(1)
    })

  const loadFollowups = () =>
    run(async () => {
      setFollowups((await component1Api.followups(profile, answers)).followups)
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
      setStep(3)
    })

  const analyze = () =>
    run(async () => {
      setReport(await component1Api.analyze(sessionId))
    })

  const commonDone = commonQuestions.length > 0 && commonQuestions.every((question) => answers[question.id] !== undefined)
  const medsDone = (noMeds ? !meds.trim() && !herbals.trim() : Boolean(meds.trim() || herbals.trim()))
  const allergiesDone = noAllergies ? !allergies.trim() : Boolean(allergies.trim())
  const consentDone = consent === "yes" && (!isChild || guardian)
  const imageCount = counts.conjunctiva + counts.nails + counts.tongue

  return (
    <Panel
      title="Component 1 · Clinical intake"
      description="New coded session → consent and adaptive questionnaire → webcam images → PPG → quality checks, trained models and reliability-aware fusion → clinician report."
      actions={
        sessionId ? (
          <Button variant="outline" size="sm" onClick={reset}>
            <RotateCcw /> New intake
          </Button>
        ) : undefined
      }
    >
      <Notice tone="caution" icon={FlaskConical} className="mb-4" title="Fictional demo data only">
        Do not enter real patient details. Question bank approval is pending; outputs are experimental screening evidence,
        not a diagnosis.
      </Notice>

      <ol className="mb-5 flex flex-wrap gap-2" aria-label="Intake steps">
        {STEPS.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? "step" : undefined}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset",
              index === step
                ? "bg-emerald-600 text-white ring-emerald-600"
                : index < step
                  ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                  : "bg-white text-slate-500 ring-slate-200",
            )}
          >
            {index + 1}. {label}
          </li>
        ))}
        {sessionId && <IdChip className="ml-auto">{sessionId}</IdChip>}
      </ol>

      {step === 0 && (
        <div className="space-y-3">
          <p className="text-sm text-slate-700">Creates a coded session folder; no name or identifier is collected.</p>
          <Button disabled={busy} onClick={() => void startSession()}>
            <Play /> Start new screening session
          </Button>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
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
          <Button disabled={!consentDone} onClick={() => setStep(2)}>
            Next: questionnaire
          </Button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          {stopped ? (
            <Notice tone="critical" title="Routine screening stopped">
              An urgent or unresolved safety answer requires immediate clinician review. No AI screening is produced and the
              questionnaire is not saved.
            </Notice>
          ) : (
            <>
              <section className="space-y-3">
                <h3 className="text-xs font-semibold text-slate-500 uppercase">Safety and common symptoms</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  {commonQuestions.map((question) => (
                    <QuestionField
                      key={question.id}
                      question={question}
                      value={answers[question.id]}
                      onChange={(value) => {
                        setAnswer(question.id, value)
                        setFollowups(null)
                      }}
                    />
                  ))}
                </div>
                {safetyTriggered && (
                  <Notice tone="critical" title="Safety concern">
                    A safety answer other than “no” stops routine screening. Request clinician review.
                    <div className="mt-2">
                      <Button size="sm" variant="outline" onClick={() => setStopped(true)}>
                        Stop and refer
                      </Button>
                    </div>
                  </Notice>
                )}
                {!safetyTriggered && followups === null && (
                  <Button variant="outline" disabled={!commonDone || busy} onClick={() => void loadFollowups()}>
                    Next: adaptive follow-up questions
                  </Button>
                )}
              </section>

              {followups !== null && !safetyTriggered && (
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

                  <Button disabled={busy || !medsDone || !allergiesDone} onClick={() => void saveQuestionnaire()}>
                    Save questionnaire and continue
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          {status?.image_acquisition_allowed ? (
            <WebcamStep sessionId={sessionId} initialCounts={counts} onCounts={setCounts} />
          ) : (
            <Notice tone="neutral">Webcam capture is not permitted by the questionnaire consent. Skip this step.</Notice>
          )}
          <div className="flex gap-2">
            <Button onClick={() => setStep(4)}>{imageCount ? `Next: PPG (${imageCount} images saved)` : "Skip to PPG"}</Button>
          </div>
        </div>
      )}

      {step === 4 && questionSet && (
        <div className="space-y-4">
          <PpgStep sessionId={sessionId} questions={questionSet.ppg_comfort} consented={consentPpg} />
          <Button onClick={() => setStep(5)}>Next: analyse and report</Button>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-4">
          {!report && (
            <>
              <p className="text-sm text-slate-700">
                Runs image technical-quality checks, the existing trained models on accepted images, then reliability-aware fusion
                with the questionnaire and PPG evidence.
              </p>
              <Button disabled={busy} onClick={() => void analyze()}>
                <Play /> {busy ? "Analysing… (models load on first run)" : "Analyse and generate clinician report"}
              </Button>
              {busy && <LoadingState label="Running quality checks, models and fusion…" lines={2} />}
            </>
          )}
          {report && (
            <>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => void run(async () => downloadJson(`${sessionId}-screening-result.json`, await component1Api.screeningResult(sessionId)))}>
                  <Download /> C1 screening JSON
                </Button>
                <Button variant="outline" size="sm" onClick={() => void run(async () => downloadJson(`${sessionId}-c2-payload.json`, await component1Api.c2Payload(sessionId)))}>
                  <Download /> Component 2 payload
                </Button>
              </div>
              <ReportView report={report} />
            </>
          )}
        </div>
      )}

      {error && !stopped && <Notice tone="critical" className="mt-4">{error}</Notice>}
      {step > 1 && step < 5 && !stopped && (
        <button type="button" className="mt-4 text-xs text-slate-500 underline" onClick={() => setStep(step - 1)}>
          ← Back
        </button>
      )}
    </Panel>
  )
}
