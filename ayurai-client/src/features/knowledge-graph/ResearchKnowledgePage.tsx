import * as React from "react"
import { ArrowRight, RefreshCw } from "lucide-react"

import {
  EmptyState,
  ErrorState,
  FilterChips,
  IdChip,
  LoadingState,
  Notice,
  PageHeader,
  Panel,
  SearchInput,
} from "@/components/shared/page"
import { StatusBadge, evidenceRoleSpecs, provisionalSpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import type { ErrorInfo } from "@/context/workspace"
import { isAbortError, isApiError } from "@/lib/api/client"
import { component2Api } from "@/lib/api/component2"
import type { ResearchClaimRow, ResearchEvidence, ResearchKnowledgeResponse } from "@/lib/api/types"
import { conceptTypeLabels, humanizeCode, predicateLabels } from "@/lib/labels"

type LoadState =
  | { status: "idle" | "loading" }
  | { status: "success"; data: ResearchKnowledgeResponse }
  | { status: "error"; error: ErrorInfo }

function toError(error: unknown): ErrorInfo {
  if (isApiError(error)) return { kind: error.kind, message: error.message, details: error.details }
  return { kind: "unknown", message: "An unexpected error occurred.", details: [] }
}

function EvidenceQuote({ evidence }: { evidence: ResearchEvidence }) {
  const role = evidence.evidence_role ? evidenceRoleSpecs[evidence.evidence_role] : undefined
  return (
    <li className="rounded-lg border border-slate-200 px-3 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {role && <StatusBadge spec={role} />}
        <IdChip>{evidence.evidence_id}</IdChip>
        {evidence.citation && <span className="text-[11px] text-slate-500">{evidence.citation}</span>}
      </div>
      {evidence.text && <p className="mt-1.5 text-sm leading-6 text-slate-800">“{evidence.text}”</p>}
      <p className="mt-1 text-[11px] text-slate-500">
        {evidence.source_name ?? evidence.source_id}
        {evidence.source_language ? ` · ${evidence.source_language}` : ""}
        {evidence.licence_note ? ` · ${evidence.licence_note}` : ""}
      </p>
    </li>
  )
}

function ClaimRow({ row }: { row: ResearchClaimRow }) {
  const { claim } = row
  return (
    <li className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <IdChip>{claim.claim_id}</IdChip>
          {claim.claim_category && (
            <span className="text-[11px] text-slate-500">{humanizeCode(claim.claim_category)}</span>
          )}
        </div>
        <StatusBadge spec={provisionalSpec} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-slate-800">{row.subject_name}</span>
        <span className="text-[11px] text-slate-500">
          {row.subject_type ? conceptTypeLabels[row.subject_type] ?? row.subject_type : ""}
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
          <ArrowRight aria-hidden className="size-3.5" />
          {predicateLabels[claim.predicate] ?? claim.predicate}
        </span>
        <span className="font-medium text-slate-800">{row.object_name}</span>
        <span className="text-[11px] text-slate-500">
          {row.object_type ? conceptTypeLabels[row.object_type] ?? row.object_type : ""}
        </span>
      </div>
      {claim.statement && <p className="mt-1.5 text-xs leading-5 text-slate-600">{claim.statement}</p>}
      {claim.uncertainty_notes && claim.uncertainty_notes.length > 0 && (
        <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-[11px] text-amber-800">
          {claim.uncertainty_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <ul className="mt-2 space-y-1.5">
        {row.evidence.map((evidence) => (
          <EvidenceQuote key={evidence.evidence_id} evidence={evidence} />
        ))}
      </ul>
      {row.qualifying_evidence.length > 0 && (
        <div className="mt-2">
          <p className="text-[11px] font-semibold text-sky-800">
            Modern evidence that qualifies this claim (kept separate; not support)
          </p>
          <ul className="mt-1 space-y-1.5">
            {row.qualifying_evidence.map((evidence) => (
              <EvidenceQuote key={evidence.evidence_id} evidence={evidence} />
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}

export function ResearchKnowledgePage() {
  const [state, setState] = React.useState<LoadState>({ status: "loading" })
  const [category, setCategory] = React.useState("all")
  const [query, setQuery] = React.useState("")
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    const controller = new AbortController()
    component2Api
      .researchKnowledge(controller.signal)
      .then((data) => setState({ status: "success", data }))
      .catch((error: unknown) => {
        if (isAbortError(error)) return
        setState({ status: "error", error: toError(error) })
      })
    return () => controller.abort()
  }, [tick])

  const reload = () => {
    setState({ status: "loading" })
    setTick((value) => value + 1)
  }

  const data = state.status === "success" ? state.data : null
  const rows = React.useMemo(() => data?.claims ?? [], [data])
  const references = data?.reference_evidence ?? []
  const categories = React.useMemo(
    () => Array.from(new Set(rows.map((row) => row.claim.claim_category ?? "uncategorised"))).sort(),
    [rows],
  )
  const needle = query.trim().toLowerCase()
  const visible = rows.filter(
    (row) =>
      (category === "all" || (row.claim.claim_category ?? "uncategorised") === category) &&
      (!needle ||
        [row.subject_name, row.object_name, row.claim.statement, row.claim.claim_id]
          .some((value) => value?.toLowerCase().includes(needle))),
  )

  return (
    <>
      <PageHeader
        eyebrow="Component 2 · Research pathway"
        title="Research knowledge (unverified)"
        description="Provisional claims drafted with AI assistance from classical Ayurvedic texts, each with its exact quoted passage. They are isolated from approved knowledge and are used only when reasoning runs in research scope."
        actions={
          <Button variant="outline" size="sm" onClick={reload}>
            <RefreshCw /> Reload
          </Button>
        }
      />

      <Notice tone="caution" title={provisionalSpec.label} className="mb-5">
        {state.status === "success"
          ? state.data.notice
          : "These records have not been reviewed by a practitioner. They are not approved knowledge and not clinical evidence of efficacy."}
      </Notice>

      {state.status === "loading" || state.status === "idle" ? (
        <LoadingState label="Loading provisional knowledge" />
      ) : state.status === "error" ? (
        <ErrorState error={state.error} title="Could not load research knowledge" onRetry={reload} />
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <Panel
            title={`Provisional claims (${visible.length} of ${rows.length})`}
            description="Traditional claims with primary-text and translation quotes"
          >
            <div className="mb-3 space-y-2">
              <SearchInput value={query} onChange={setQuery} placeholder="Search concepts or statements" label="Search provisional claims" />
              <FilterChips
                label="Claim category"
                value={category}
                onChange={setCategory}
                options={[{ value: "all", label: "All" }, ...categories.map((value) => ({ value, label: humanizeCode(value) }))]}
              />
            </div>
            {visible.length === 0 ? (
              <EmptyState title="No provisional claims match" />
            ) : (
              <ul className="space-y-3">
                {visible.map((row) => (
                  <ClaimRow key={row.claim.claim_id} row={row} />
                ))}
              </ul>
            )}
          </Panel>
          <Panel
            title={`Modern reference statements (${references.length})`}
            description="Modern literature kept separate from traditional claims; it qualifies, never supports them"
          >
            <ul className="space-y-2">
              {references.map((evidence) => (
                <EvidenceQuote key={evidence.evidence_id} evidence={evidence} />
              ))}
            </ul>
          </Panel>
        </div>
      )}
    </>
  )
}
