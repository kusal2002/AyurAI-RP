import * as React from "react"
import { ArrowRight, CheckCircle2, CircleDashed, Clock, Database, RefreshCw, XCircle } from "lucide-react"

import { ErrorState, KeyValueList, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, type StatusSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth"
import { toErrorInfo, useWorkspace, type ErrorInfo } from "@/context/workspace"
import { isAbortError } from "@/lib/api/client"
import { component4Api, type FaklStatus } from "@/lib/api/component4"
import { C4SignInRequired } from "@/features/federation/shared"

const ready: StatusSpec = { label: "Ready", tone: "positive", icon: CheckCircle2 }
const notReady: StatusSpec = { label: "Not yet", tone: "caution", icon: XCircle }
const planned: StatusSpec = { label: "Planned", tone: "neutral", icon: CircleDashed }

/** The FAKL design, one step per card (proposal SO3). */
const steps = [
  {
    title: "Practitioner feedback",
    owner: "Component 2",
    text: "At each clinic, practitioners agree or disagree with knowledge-graph claims (e.g. symptom → Pitta imbalance) while reviewing cases.",
  },
  {
    title: "Local update at the clinic",
    owner: "Clinic node",
    text: "Each clinic turns its own feedback into a change (Δ) in confidence per claim, computed locally from its agree / disagree counts.",
  },
  {
    title: "Privacy before sharing",
    owner: "Component 4",
    text: "Only per-claim Δ values and counts leave the clinic — never feedback text, reviewers or patients. Small counts are suppressed and DP noise can be added, as in model training.",
  },
  {
    title: "Federated combination",
    owner: "Component 4 server",
    text: "The server combines the clinics' Δ values per claim, weighted by how much feedback each clinic contributed (FedAvg-style).",
  },
  {
    title: "Updated shared knowledge",
    owner: "Component 4 → graph",
    text: "The federated confidence is stored separately from Component 2's own claim fields, so its reasoning data is never overwritten, and every update is audited.",
  },
]

type LoadState = { status: "loading" } | { status: "error"; error: ErrorInfo } | { status: "success"; data: FaklStatus }

function ReadinessCheck() {
  const [state, setState] = React.useState<LoadState>({ status: "loading" })
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    const controller = new AbortController()
    component4Api
      .faklStatus(controller.signal)
      .then((data) => setState({ status: "success", data }))
      .catch((error) => {
        if (!isAbortError(error)) setState({ status: "error", error: toErrorInfo(error) })
      })
    return () => controller.abort()
  }, [tick])

  const reload = () => {
    setState({ status: "loading" })
    setTick((value) => value + 1)
  }

  if (state.status === "loading") return <LoadingState label="Checking Component 2's knowledge graph (read-only)…" />
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />

  const { data } = state
  const counts = data.counts
  const items: { label: string; ok: boolean | null; detail: string }[] = [
    {
      label: "Connection to Component 2's graph (read-only)",
      ok: data.connected,
      detail: data.connected ? "Connected with a read-only session; nothing is written." : data.error ?? "Not connected.",
    },
    {
      label: "Claims with a confidence value",
      ok: counts ? counts.claims_with_confidence > 0 : null,
      detail: counts ? `${counts.claims_with_confidence} of ${counts.claims} claims have a confidence value.` : "—",
    },
    {
      label: "Practitioner feedback linked to claims",
      ok: counts ? counts.feedback_links > 0 : null,
      detail: counts ? `${counts.feedback} feedback records, ${counts.feedback_links} links to claims.` : "—",
    },
    {
      label: "Feedback says which clinic it came from",
      ok: counts ? counts.feedback_with_clinic > 0 : null,
      detail: counts
        ? `${counts.feedback_with_clinic} of ${counts.feedback} feedback records carry a clinic_id (needed to federate per clinic).`
        : "—",
    },
  ]

  return (
    <div className="space-y-4">
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
        {items.map((item) => (
          <li key={item.label} className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[minmax(0,1fr)_120px] md:items-center">
            <div>
              <p className="text-sm font-semibold text-slate-800">{item.label}</p>
              <p className="text-xs text-slate-500">{item.detail}</p>
            </div>
            <StatusBadge spec={item.ok === null ? planned : item.ok ? ready : notReady} />
          </li>
        ))}
      </ul>
      <Button variant="outline" size="sm" onClick={reload}>
        <RefreshCw /> Check again
      </Button>
    </div>
  )
}

export function FaklPage() {
  const { user } = useAuth()
  const { mode } = useWorkspace()

  return (
    <>
      <PageHeader
        eyebrow="Component 4 · Knowledge federation (FAKL)"
        title="Federated Ayurvedic Knowledge Learning"
        description="Federating practitioner-driven updates to the Ayurvedic knowledge graph across clinics, without sharing feedback text or patient data (proposal SO3)."
      />

      <Notice tone="info" icon={Clock} className="mb-5" title="Design stage — implementation scheduled Dec 2026 – Feb 2027">
        This page shows the FAKL design and a live, read-only check of whether its data source is ready. No knowledge-graph
        federation runs yet, and no results are shown or simulated.
      </Notice>

      <Panel className="mb-5" title="How FAKL will work" description="The same idea as federated model training, applied to the knowledge graph's claim confidences.">
        <ol className="grid grid-cols-1 gap-3 lg:grid-cols-5">
          {steps.map((step, index) => (
            <li key={step.title} className="relative rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex size-7 items-center justify-center rounded-full bg-emerald-700 text-xs font-bold text-white">
                  {index + 1}
                </span>
                <span className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">{step.owner}</span>
              </div>
              <p className="text-sm font-semibold text-slate-800">{step.title}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{step.text}</p>
              {index < steps.length - 1 && (
                <ArrowRight aria-hidden className="absolute top-1/2 -right-3 hidden size-4 -translate-y-1/2 text-slate-300 lg:block" />
              )}
            </li>
          ))}
        </ol>
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel
          title="Data-source readiness (live)"
          description="Read-only check of Component 2's Neo4j graph. Only counts are returned — no claim or feedback content."
          actions={<Database aria-hidden className="size-4 text-slate-400" />}
        >
          {mode !== "live" || !user ? <C4SignInRequired what="The readiness check" /> : <ReadinessCheck />}
        </Panel>

        <Panel title="Plan">
          <KeyValueList
            items={[
              { label: "1. Prototype", value: "Local Neo4j (Docker) with synthetic claims in Component 2's schema" },
              { label: "2. Privacy", value: "Suppress small counts; optional DP noise on per-claim Δ" },
              { label: "3. Integration", value: "Read Component 2's graph read-only once it has claims and clinic-tagged feedback" },
              { label: "4. Evaluation", value: "Compare federated confidences with pooled (centralised) feedback" },
              { label: "Timeline", value: "Dec 2026 – Feb 2027 (proposal work breakdown)" },
            ]}
          />
        </Panel>
      </div>
    </>
  )
}
