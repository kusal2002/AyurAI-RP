import * as React from "react"
import { Link } from "react-router"
import { FolderOpen, Info, Leaf, Play, Plus, Stethoscope } from "lucide-react"

import { EmptyState, ErrorState, IdChip, LoadingState, Panel } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { useTechnicalView } from "@/lib/access"
import { c1View, type Component2Output } from "@/lib/api/types"
import { formatDateTime } from "@/lib/labels"

/** Active-case selector shown at the top of case-level screens. */
export function CaseBar() {
  const { cases, activeCase, selectCase } = useWorkspace()
  const [technical] = useTechnicalView()
  if (cases.length === 0) return null

  return (
    <div className="mb-5 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <FolderOpen aria-hidden className="size-4 shrink-0 text-emerald-700" />
        <label className="flex min-w-0 items-center gap-2 text-xs text-slate-500">
          <span className="shrink-0">Active case</span>
          <select
            value={activeCase?.id ?? ""}
            onChange={(event) => selectCase(event.target.value)}
            className="h-8 min-w-0 rounded-lg border border-slate-200 bg-white px-2 text-sm font-semibold text-slate-800 focus:border-emerald-500 focus:outline-none"
          >
            {cases.map((record) => (
              <option key={record.id} value={record.id}>
                {record.caseRef} · {formatDateTime(record.createdAt)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {activeCase && technical && (
        <div className="flex flex-wrap items-center gap-2">
          {activeCase.c2.status === "success" && (
            <span className="text-xs text-slate-500">
              C2 request <IdChip>{activeCase.c2.data.request_id}</IdChip>
            </span>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Renders children only when the active case has a Component 2 output.
 * Otherwise shows the appropriate empty / loading / error state.
 */
export function WithReasoning({
  children,
}: {
  children: (output: Component2Output, record: CaseRecord) => React.ReactNode
}) {
  const { activeCase, runReasoning } = useWorkspace()

  if (!activeCase) {
    return (
      <Panel>
        <EmptyState
          icon={Stethoscope}
          title="No case in this session"
          description="Start a screening and enter the approved Component 1 summary to run Component 2 reasoning. Cases exist only in this browser tab."
          action={
            <Button className="bg-emerald-700 hover:bg-emerald-800" render={<Link to="/screening/new" />} nativeButton={false}>
              <Stethoscope /> New screening
            </Button>
          }
        />
      </Panel>
    )
  }

  const state = activeCase.c2
  if (state.status === "idle") {
    return (
      <Panel>
        <EmptyState
          icon={Leaf}
          title="Component 2 reasoning has not been run for this case"
          description="Run reasoning to request the Ayurvedic interpretation, evidence and candidates from the Component 2 service."
          action={
            <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={() => runReasoning(activeCase.id)}>
              <Play /> Run Component 2 reasoning
            </Button>
          }
        />
      </Panel>
    )
  }
  if (state.status === "loading") {
    return (
      <Panel>
        <LoadingState label="Waiting for the Component 2 reasoning service… The first request can take longer while the embedding model loads." />
      </Panel>
    )
  }
  // The service answered, but there was nothing it could analyse. That is
  // an expected outcome, not a failure, so explain it in plain words.
  if (state.status === "error" && state.error.kind === "validation" && activeCase.c1?.mapping) {
    return (
      <Panel>
        <NotAnalysed record={activeCase} />
      </Panel>
    )
  }
  if (state.status === "error") {
    return (
      <Panel>
        <ErrorState
          title="Component 2 reasoning output is unavailable"
          error={state.error}
          onRetry={() => runReasoning(activeCase.id)}
        />
        {activeCase.c1?.mapping && (
          <div className="mt-3 rounded-lg border border-slate-200 p-3 text-xs text-slate-600">
            <p className="font-semibold text-slate-700">Symptom mapping reported by Component 2</p>
            <p className="mt-1">
              Resolved:{" "}
              {activeCase.c1.mapping.resolved_symptoms.length
                ? activeCase.c1.mapping.resolved_symptoms.map((item) => `${item.input_name} → ${item.symptom_id}`).join(", ")
                : "none"}
            </p>
            {activeCase.c1.mapping.unresolved_symptoms.length > 0 && (
              <p className="mt-0.5 text-amber-800">
                Unresolved:{" "}
                {activeCase.c1.mapping.unresolved_symptoms
                  .map((item) => `${item.input_name} (${item.status.replace(/_/g, " ")})`)
                  .join(", ")}
              </p>
            )}
          </div>
        )}
        <p className="mt-3 text-xs text-slate-500">
          No interpretation, evidence or candidates are shown because the service did not return
          them. Nothing is substituted.
        </p>
      </Panel>
    )
  }
  return <>{children(state.data, activeCase)}</>
}

/** "S-GENERAL-WEAKNESS" -> "general weakness" */
function symptomLabel(symptomId: string): string {
  return symptomId.replace(/^S-/, "").replace(/-/g, " ").toLowerCase()
}

function NotAnalysed({ record }: { record: CaseRecord }) {
  const mapping = record.c1?.mapping
  const payload = record.c1?.payload
  if (!mapping) return null
  const reported = payload ? c1View(payload).symptoms : []
  const present = reported.filter((symptom) => symptom.present)
  const unknown = mapping.unresolved_symptoms.filter((item) => item.status === "not_found")
  const unclear = mapping.unresolved_symptoms.filter((item) => item.status === "ambiguous")

  let title = "This screening could not be analysed"
  let reason: React.ReactNode = "No symptom from the screening could be matched to the Ayurvedic knowledge base."
  if (mapping.status === "blocked") {
    title = "The screening's risk level is not recognised"
    reason = (
      <>
        The screening reports the risk level <strong>“{payload?.screening_result.risk_level ?? "unknown"}”</strong>.
        Ayurvedic analysis accepts only <strong>low</strong>, <strong>moderate</strong> or <strong>high</strong>.
      </>
    )
  } else if (present.length === 0) {
    title = "No symptoms to analyse"
    reason = "The patient has no symptoms marked as present. Ayurvedic analysis starts from the symptoms the patient has."
  } else if (unknown.length || unclear.length) {
    title = "The symptoms could not be matched"
    reason = "None of the patient's symptoms could be matched with certainty, so nothing was analysed rather than guessing."
  }

  return (
    <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-sm text-slate-700">
      <Info aria-hidden className="mt-0.5 size-5 shrink-0 text-amber-600" />
      <div className="space-y-3">
        <div>
          <p className="font-semibold text-slate-900">{title}</p>
          <p className="mt-1">{reason}</p>
        </div>

        {reported.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-600">Symptoms in this screening</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {reported.map((symptom) => (
                <li
                  key={symptom.name}
                  className={
                    symptom.present
                      ? "rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs text-emerald-800"
                      : "rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500"
                  }
                >
                  {symptom.name}: {symptom.present ? "present" : "not present"}
                </li>
              ))}
            </ul>
          </div>
        )}

        {(unknown.length > 0 || unclear.length > 0) && (
          <ul className="list-disc space-y-1 pl-5 text-xs">
            {unknown.map((item) => (
              <li key={item.input_name}>
                <strong>“{item.input_name}”</strong> is not in the knowledge base yet.
              </li>
            ))}
            {unclear.map((item) => (
              <li key={item.input_name}>
                <strong>“{item.input_name}”</strong> could mean{" "}
                {(item.candidate_ids ?? []).map(symptomLabel).join(" or ") || "more than one symptom"}. Please use the more
                specific name.
              </li>
            ))}
          </ul>
        )}

        <p className="text-xs text-slate-600">
          <strong>What to do:</strong> start a new screening that lists at least one symptom the patient has, using a
          specific name (for example “pallor”, “fatigue” or “dizziness”).
        </p>
        <Button
          size="sm"
          className="bg-emerald-700 hover:bg-emerald-800"
          render={<Link to="/screening/new" />}
          nativeButton={false}
        >
          <Plus /> New screening
        </Button>
      </div>
    </div>
  )
}
