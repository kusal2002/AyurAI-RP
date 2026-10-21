import * as React from "react"
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleHelp,
  Download,
  RefreshCw,
  FileText,
  RotateCcw,
  ShieldAlert,
  ShieldPlus,
} from "lucide-react"

import { ErrorState, KeyValueList, LoadingState, Notice, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { component1Api } from "@/lib/api/component1"
import type { C1EvidenceItem, Component1Json, Component1Report, Component1Session } from "@/lib/api/types"
import { formatDateTime } from "@/lib/labels"
import { cn } from "@/lib/utils"

type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string }

const tierSpecs: Record<string, StatusSpec> = {
  low: { label: "Low (experimental)", tone: "positive", icon: CheckCircle2 },
  moderate: { label: "Moderate (experimental)", tone: "caution", icon: AlertTriangle },
  high: { label: "High (experimental)", tone: "critical", icon: ShieldAlert },
  insufficient_evidence: { label: "Insufficient Evidence", tone: "neutral", icon: CircleHelp },
}

function tierSpec(tier: string | null | undefined): StatusSpec {
  return (tier && tierSpecs[tier]) || { label: "Not generated", tone: "neutral", icon: CircleDashed }
}

const stepSpecs: Record<string, StatusSpec> = {
  complete: { label: "Complete", tone: "positive", icon: CheckCircle2 },
  pending: { label: "Pending", tone: "neutral", icon: CircleDashed },
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "Component 1 returned an unexpected error."
}

function sessionIdOf(session: Component1Session) {
  return typeof session.session_id === "string" ? session.session_id : null
}

/** e.g. "demo_e37082b4 · 21 Oct 11:20 · Q ✓ · 5 images · PPG ✓ · Moderate" */
function sessionLabel(session: Component1Session, id: string) {
  const parts = [id]
  if (session.created_utc) parts.push(formatDateTime(session.created_utc))
  parts.push(session.questionnaire_available ? "Q ✓" : "no questionnaire")
  parts.push(`${session.image_count ?? 0} images`)
  parts.push(session.ppg_available ? "PPG ✓" : "no PPG")
  parts.push(session.risk_level ? tierSpec(session.risk_level).label.replace(" (experimental)", "") : "not analysed")
  return parts.join(" · ")
}

function jsonValue(value: unknown) {
  return JSON.stringify(value, null, 2)
}

export function downloadJson(fileName: string, value: unknown) {
  const blob = new Blob([jsonValue(value)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

function humanize(value: string | null | undefined) {
  return value ? value.replace(/_/g, " ") : "—"
}

function signed(value: number | null | undefined) {
  return typeof value === "number" ? (value > 0 ? "+" : "") + value.toFixed(2) : "—"
}

function List({ items, empty }: { items?: string[]; empty: string }) {
  if (!items?.length) return <p className="text-xs text-slate-500">{empty}</p>
  return (
    <ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-slate-700">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h3>
      {children}
    </section>
  )
}

function EvidenceTable({ items }: { items: C1EvidenceItem[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full min-w-160 text-left text-xs">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2">Modality</th>
            <th className="px-3 py-2">Model / rule</th>
            <th className="px-3 py-2">Output</th>
            <th className="px-3 py-2">Evidence</th>
            <th className="px-3 py-2">Weight</th>
            <th className="px-3 py-2">Basis</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((item) => (
            <tr key={`${item.modality}-${item.source}`} className={item.reliability_weight > 0 ? "" : "text-slate-400"}>
              <td className="px-3 py-2 capitalize">{item.modality}</td>
              <td className="px-3 py-2 font-mono">{item.source}</td>
              <td className="px-3 py-2">
                {item.mean_output === null
                  ? "—"
                  : item.task === "hb_regression"
                    ? `${item.mean_output.toFixed(2)} g/dL`
                    : item.task === "classification"
                      ? `score ${item.mean_output.toFixed(2)}`
                      : `fraction ${item.mean_output.toFixed(2)}`}
              </td>
              <td className="px-3 py-2">{signed(item.evidence)}</td>
              <td className="px-3 py-2">{item.reliability_weight > 0 ? item.reliability_weight.toFixed(3) : "not weighted"}</td>
              <td className="px-3 py-2">{item.note ?? item.weight_basis}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const tierLadder = [
  { key: "low", label: "Low", dot: "bg-emerald-500", active: "border-emerald-400 bg-emerald-50 text-emerald-900 ring-2 ring-emerald-200" },
  { key: "moderate", label: "Moderate", dot: "bg-amber-500", active: "border-amber-400 bg-amber-50 text-amber-900 ring-2 ring-amber-200" },
  { key: "high", label: "High", dot: "bg-rose-500", active: "border-rose-400 bg-rose-50 text-rose-900 ring-2 ring-rose-200" },
  { key: "insufficient_evidence", label: "Insufficient Evidence", dot: "bg-slate-400", active: "border-slate-400 bg-slate-100 text-slate-900 ring-2 ring-slate-200" },
]

/** Semicircle gauge for the fusion reliability score (0-1). A heuristic, NOT a calibrated confidence. */
function ReliabilityGauge({ value }: { value: number | null | undefined }) {
  const score = typeof value === "number" ? Math.max(0, Math.min(1, value)) : null
  const band = score === null ? "Not available" : score < 0.4 ? "Low reliability" : score < 0.7 ? "Moderate reliability" : "Higher reliability"
  const color = score === null ? "#cbd5e1" : score < 0.4 ? "#f43f5e" : score < 0.7 ? "#f59e0b" : "#10b981"
  const angle = Math.PI * (1 - (score ?? 0))
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 70" className="w-48" role="img" aria-label={`Evidence reliability ${score === null ? "not available" : `${Math.round(score * 100)}%`}`}>
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#e2e8f0" strokeWidth="10" strokeLinecap="round" />
        {score !== null && score > 0 && (
          <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" pathLength={100} strokeDasharray={`${score * 100} 100`} />
        )}
        <line x1="60" y1="60" x2={60 + 38 * Math.cos(angle)} y2={60 - 38 * Math.sin(angle)} stroke="#0f766e" strokeWidth="3" strokeLinecap="round" />
        <circle cx="60" cy="60" r="4" fill="#0f766e" />
      </svg>
      <p className="-mt-1 text-3xl font-bold text-teal-800">{score === null ? "—" : `${Math.round(score * 100)}%`}</p>
      <p className="text-xs font-medium text-slate-700">{band}</p>
      <p className="mt-1 max-w-56 text-center text-[11px] leading-4 text-slate-500">
        Heuristic from image quality and held-out model performance — not a probability or calibrated confidence.
      </p>
    </div>
  )
}

function RiskOutputCard({ report }: { report: Component1Report }) {
  const tier = report.screening_result?.risk_level ?? null
  const reliability = report.fusion?.reliability_aware_fusion
  const weighted = (report.fusion?.evidence_items ?? [])
    .filter((item) => item.reliability_weight > 0 && item.evidence !== null)
    .sort((a, b) => b.reliability_weight - a.reliability_weight)
    .map((item) => {
      const evidence = item.evidence ?? 0
      const direction = evidence > 0.2 ? "towards anaemia" : evidence < -0.2 ? "against anaemia" : "neutral"
      return `${item.modality.charAt(0).toUpperCase()}${item.modality.slice(1)} · ${item.source} — ${direction} (weight ${item.reliability_weight.toFixed(2)})`
    })
  const reasons = [...(reliability?.insufficient_reasons ?? []).map((reason) => `Insufficient evidence: ${reason}`), ...weighted]

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-labelledby="c1-risk-output">
      <div className="border-b border-slate-100 bg-linear-to-r from-teal-50 to-emerald-50 px-5 py-4">
        <h3 id="c1-risk-output" className="text-lg font-bold text-teal-800">Risk output</h3>
        <p className="text-xs text-slate-600">Experimental anaemia screening tier — unvalidated; for clinician review, not a diagnosis.</p>
      </div>
      <div className="grid gap-6 p-5 md:grid-cols-2">
        <div className="flex items-center gap-5">
          <div className="flex size-24 shrink-0 items-center justify-center rounded-full bg-teal-50 ring-8 ring-teal-50/60">
            <ShieldPlus className="size-12 text-teal-700" aria-hidden />
          </div>
          <div className="w-full space-y-2">
            <p className="text-sm font-semibold text-teal-800">Risk tier</p>
            {tierLadder.map((item) => {
              const isActive = item.key === tier
              return (
                <div
                  key={item.key}
                  aria-current={isActive ? "true" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-full border px-4 py-2 text-sm font-semibold transition",
                    isActive ? item.active : "border-slate-200 bg-white text-slate-400",
                  )}
                >
                  <span className={cn("size-3.5 rounded-full", isActive ? item.dot : "bg-slate-200")} aria-hidden />
                  {item.label}
                  {isActive && <span className="ml-auto text-[11px] font-medium">this session</span>}
                </div>
              )
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-[auto_minmax(0,1fr)] md:grid-cols-1 xl:grid-cols-[auto_minmax(0,1fr)]">
          <div>
            <p className="mb-1 text-sm font-semibold text-teal-800">Evidence reliability</p>
            <ReliabilityGauge value={report.screening_result?.reliability_score ?? reliability?.reliability_score} />
          </div>
          <div>
            <p className="mb-1 text-sm font-semibold text-teal-800">Rationale</p>
            <div className="relative rounded-2xl border-2 border-teal-600/70 bg-white p-3">
              <div className="flex gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white">
                  <FileText className="size-4" aria-hidden />
                </span>
                {reasons.length ? (
                  <ul className="space-y-1.5 text-[11px] leading-4 text-slate-700">
                    {reasons.slice(0, 5).map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-500">No weighted evidence yet. Re-run fusion.</p>
                )}
              </div>
              <span className="absolute -bottom-2 left-6 size-3.5 rotate-45 border-r-2 border-b-2 border-teal-600/70 bg-white" aria-hidden />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export function ReportView({ report }: { report: Component1Report }) {
  const fusion = report.fusion ?? {}
  const reliability = fusion.reliability_aware_fusion
  const conventional = fusion.conventional_fusion
  const ppg = report.modalities?.ppg
  const regions = report.modalities?.images?.regions ?? {}
  const questionnaire = fusion.questionnaire_evidence
  const doctor = report.doctor_report ?? {}

  return (
    <div className="space-y-6">
      {(fusion.safety_flags?.length ?? 0) > 0 && (
        <Notice tone="critical" title="Safety flags">
          <List items={fusion.safety_flags} empty="" />
        </Notice>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-semibold text-slate-500 uppercase">Reliability-aware fusion</p>
          <StatusBadge spec={tierSpec(report.screening_result?.risk_level)} size="md" />
          <KeyValueList
            items={[
              { label: "Weighted evidence score", value: signed(reliability?.weighted_evidence_score) },
              { label: "Reliability score (heuristic, not a probability)", value: reliability?.reliability_score ?? "—" },
              { label: "Evidence conflict ratio", value: reliability?.conflict_ratio ?? "—" },
              { label: "Usable physiological modalities", value: reliability?.usable_physiological_modalities.join(", ") || "none" },
              { label: "Decision status", value: humanize(report.screening_result?.decision_status) },
            ]}
          />
          {(reliability?.insufficient_reasons.length ?? 0) > 0 && (
            <List items={reliability?.insufficient_reasons} empty="" />
          )}
        </div>
        <div className="space-y-3 rounded-xl border border-slate-200 p-4">
          <p className="text-xs font-semibold text-slate-500 uppercase">Conventional fusion (comparison baseline)</p>
          <StatusBadge spec={tierSpec(conventional?.tier)} size="md" />
          <KeyValueList
            items={[
              { label: "Method", value: humanize(conventional?.method) },
              { label: "Model outputs counted", value: conventional?.votes ?? "—" },
              { label: "Anaemia vote fraction", value: conventional?.anaemia_vote_fraction ?? "—" },
              { label: "Sources ignored by reliability-aware fusion", value: reliability?.excluded_sources.join(", ") || "none" },
            ]}
          />
        </div>
      </div>

      <Notice tone="caution" title="Experimental, unvalidated">
        Tiers come from pre-specified rules weighted by technical quality and held-out model performance. No dataset
        pairs all modalities, so the fused tier has no measured accuracy. {doctor.clinical_action}
      </Notice>

      <Section title="Model and rule evidence">
        {fusion.evidence_items?.length ? (
          <EvidenceTable items={fusion.evidence_items} />
        ) : (
          <p className="text-xs text-slate-500">No fusion v2 evidence yet. Choose “Re-run fusion”.</p>
        )}
        {fusion.hb_threshold_basis && <p className="text-xs text-slate-500">Hb cut-off: {fusion.hb_threshold_basis}</p>}
      </Section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Image technical quality">
          <KeyValueList
            items={
              Object.keys(regions).length
                ? Object.entries(regions).map(([name, region]) => ({
                    label: name,
                    value: `${region.technical_passes ?? 0}/${region.captures ?? 0} passed${region.cross_model_disagreement ? " · models disagree" : ""}`,
                  }))
                : [{ label: "Images", value: "none captured" }]
            }
          />
        </Section>
        <Section title="PPG (MAX30102)">
          <KeyValueList
            items={
              ppg?.available
                ? [
                    { label: "Samples", value: `${ppg.sample_count ?? 0} @ ${ppg.observed_receive_rate_hz ?? "?"} Hz` },
                    { label: "Technical status", value: humanize(ppg.quality_status) },
                    { label: "Quality windows", value: `${ppg.quality_windows_passed ?? 0}/${ppg.quality_windows_checked ?? 0}` },
                    { label: "Experimental HR", value: ppg.median_experimental_hr_bpm != null ? `${ppg.median_experimental_hr_bpm} bpm` : "—" },
                    { label: "Experimental SpO2", value: ppg.median_experimental_spo2_percent != null ? `${ppg.median_experimental_spo2_percent}%` : "—" },
                    { label: "Hb model applied", value: ppg.hb_model_applied ? "Yes" : "No (not validated for live data)" },
                  ]
                : [{ label: "PPG", value: "not recorded" }]
            }
          />
        </Section>
        <Section title="Questionnaire (rule-based)">
          <KeyValueList
            items={[
              { label: "Interview", value: humanize(report.questionnaire?.completion_status) },
              { label: "Symptoms answered", value: questionnaire?.answered_items ?? "—" },
              { label: "Present", value: questionnaire?.present_symptoms.map(humanize).join(", ") || "none" },
              { label: "Symptom fraction", value: questionnaire?.symptom_fraction ?? "—" },
            ]}
          />
        </Section>
      </div>

      <RiskOutputCard report={report} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Clinician summary">
          <p className="text-sm text-slate-800">{doctor.summary}</p>
          <List items={doctor.observations} empty="No observations." />
        </Section>
        <Section title="Recommendations">
          <List items={doctor.recommendations} empty="No recommendations." />
        </Section>
        <Section title="Rationale">
          <List items={fusion.rationale} empty="No rationale." />
        </Section>
        <Section title="Reliability flags and limitations">
          <List items={[...(doctor.reliability_flags ?? []), ...(doctor.limitations ?? [])]} empty="None." />
        </Section>
      </div>

      {report.storage && (
        <Section title="Saved screening record">
          <KeyValueList
            items={[
              { label: "Folder", value: <code className="text-xs break-all">{report.storage.folder}</code> },
              {
                label: "Record files",
                value: report.storage.record_saved
                  ? `Saved ${report.storage.record_saved_utc ? formatDateTime(report.storage.record_saved_utc) : ""}`
                  : "Not saved yet — run Analyse or Re-run fusion",
              },
              { label: "Files", value: report.storage.files.join(", ") || "—" },
              { label: "Images / PPG recordings", value: `${report.storage.image_files} / ${report.storage.ppg_recordings}` },
            ]}
          />
        </Section>
      )}

      <Section title="Workflow">
        <div className="flex flex-wrap gap-2">
          {report.workflow?.map((step) => (
            <span key={step.key} className="inline-flex items-center gap-1.5 text-xs text-slate-600">
              <StatusBadge spec={stepSpecs[step.status] ?? stepSpecs.pending} title={step.status} />
              {step.label}
            </span>
          ))}
        </div>
        {(report.missing_inputs?.length ?? 0) > 0 && (
          <p className="text-xs text-slate-500">Missing inputs: {report.missing_inputs?.join(", ")}</p>
        )}
      </Section>
    </div>
  )
}

export function Component1SessionPanel() {
  const [health, setHealth] = React.useState<LoadState<unknown>>({ status: "idle" })
  const [sessions, setSessions] = React.useState<LoadState<Component1Session[]>>({ status: "idle" })
  const [selectedId, setSelectedId] = React.useState("")
  const [report, setReport] = React.useState<LoadState<Component1Report>>({ status: "idle" })
  const [actionError, setActionError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const connect = async () => {
    setHealth({ status: "loading" })
    setSessions({ status: "loading" })
    try {
      const [healthResponse, sessionResponse] = await Promise.all([
        component1Api.health(),
        component1Api.sessions(),
      ])
      const list = Array.isArray(sessionResponse.sessions) ? sessionResponse.sessions : []
      setHealth({ status: "success", data: healthResponse })
      setSessions({ status: "success", data: list })
      setSelectedId((current) => current || (list[0] ? sessionIdOf(list[0]) : null) || "")
    } catch (error) {
      const message = errorMessage(error)
      setHealth({ status: "error", message })
      setSessions({ status: "error", message })
    }
  }

  const loadSession = async () => {
    if (!selectedId) return
    setReport({ status: "loading" })
    setActionError(null)
    try {
      setReport({ status: "success", data: await component1Api.report(selectedId) })
    } catch (error) {
      setReport({ status: "error", message: errorMessage(error) })
    }
  }

  const rerunFusion = async () => {
    if (!selectedId) return
    setBusy(true)
    setActionError(null)
    try {
      setReport({ status: "success", data: await component1Api.refresh(selectedId) })
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  const download = async (kind: "screening-result" | "c2-payload") => {
    if (!selectedId) return
    setActionError(null)
    try {
      const data: Component1Json =
        kind === "c2-payload"
          ? await component1Api.c2Payload(selectedId)
          : await component1Api.screeningResult(selectedId)
      downloadJson(`${selectedId}-${kind}.json`, data)
    } catch (error) {
      setActionError(errorMessage(error))
    }
  }

  const loaded = report.status === "success"

  return (
    <Panel
      title="Component 1 screening session"
      description="Clinician view of screening sessions saved in datasets/live_sessions. Choose Connect / refresh to list them."
      actions={
        <Button variant="outline" size="sm" onClick={() => void connect()}>
          <RefreshCw /> Connect / refresh
        </Button>
      }
    >
      <Notice tone="info" className="mb-4" title="Local Component 1 development connection">
        Reads fictional demo sessions saved in <code>datasets/live_sessions</code> from <code>/api/c1</code> through the Vite proxy at
        <code> http://127.0.0.1:8001</code>. New sessions are captured on the New screening page.
      </Notice>

      {health.status === "loading" || sessions.status === "loading" ? (
        <LoadingState label="Checking the local Component 1 API…" lines={2} />
      ) : sessions.status === "error" ? (
        <ErrorState
          error={{ kind: "network", message: sessions.message, details: [] }}
          title="Component 1 is unavailable"
          onRetry={() => void connect()}
        />
      ) : sessions.status === "success" ? (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-64 text-xs font-medium text-slate-600">
              Existing session
              <select
                className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm"
                value={selectedId}
                onChange={(event) => {
                  setSelectedId(event.target.value)
                  setReport({ status: "idle" })
                }}
              >
                <option value="">Choose a session…</option>
                {sessions.data.map((session, index) => {
                  const id = sessionIdOf(session)
                  return id ? <option key={`${id}-${index}`} value={id}>{sessionLabel(session, id)}</option> : null
                })}
              </select>
            </label>
            <Button disabled={!selectedId || report.status === "loading"} onClick={() => void loadSession()}>
              Load screening evidence
            </Button>
            <Button variant="outline" disabled={!selectedId || busy} onClick={() => void rerunFusion()}>
              <RotateCcw /> {busy ? "Re-running…" : "Re-run fusion"}
            </Button>
          </div>
          {sessions.data.length === 0 && (
            <p className="mt-3 text-sm text-slate-500">The Component 1 API returned no sessions.</p>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-500">Choose Connect / refresh to list local Component 1 sessions.</p>
      )}

      {actionError && (
        <div className="mt-4">
          <ErrorState error={{ kind: "network", message: actionError, details: [] }} title="Action failed" />
        </div>
      )}
      {report.status === "loading" && <div className="mt-5"><LoadingState label="Loading the Component 1 report…" /></div>}
      {report.status === "error" && (
        <div className="mt-5">
          <ErrorState error={{ kind: "network", message: report.message, details: [] }} title="Report unavailable" />
        </div>
      )}
      {loaded && (
        <div className="mt-5 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-800">
              {report.data.session_id}
              {report.data.generated_utc && (
                <span className="ml-2 font-normal text-slate-500">generated {formatDateTime(report.data.generated_utc)}</span>
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => void download("screening-result")}>
                <Download /> C1 screening JSON
              </Button>
              <Button variant="outline" size="sm" onClick={() => void download("c2-payload")}>
                <Download /> Component 2 payload
              </Button>
            </div>
          </div>
          <ReportView report={report.data} />
          <details>
            <summary className="cursor-pointer text-sm font-medium text-slate-700">Full report JSON</summary>
            <pre className="mt-2 max-h-96 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">
              {jsonValue(report.data)}
            </pre>
          </details>
        </div>
      )}
    </Panel>
  )
}
