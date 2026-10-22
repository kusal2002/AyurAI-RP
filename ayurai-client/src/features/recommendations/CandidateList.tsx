import * as React from "react"
import { Link } from "react-router"
import { AlertTriangle, ArrowRight, ChevronDown, CircleSlash } from "lucide-react"

import { EmptyState, FilterChips } from "@/components/shared/page"
import { StatusBadge, safetySpec, sufficiencySpec } from "@/components/shared/status"
import type { CaseRecord } from "@/context/workspace"
import { CandidateStatus, TypeMatch } from "@/features/ayurvedic-analysis/AnalysisSummary"
import type { Candidate, Component2Output } from "@/lib/api/types"
import { conceptNames, topCandidatePerCategory } from "@/lib/c2-derive"
import { describeFlag, humanizeCode } from "@/lib/labels"
import { cn } from "@/lib/utils"

/**
 * Clean list of suggested options for practitioners: name, type, evidence and
 * safety status, and on expanding, why it was suggested in plain words.
 * The full table (scores, IDs, claims, policies) is the technical view.
 */

type Filter = "all" | "review" | "safety"
type Scope = "top" | "all"

const MAX_PATHS = 3

/** Flags that describe the reasoning, not something the doctor must check. */
const INFORMATIONAL_FLAGS = new Set(["multiple_paths"])

function readableName(id: string, names: Map<string, string>) {
  return names.get(id) ?? humanizeCode(id.replace(/^[A-Z]{1,3}-/, ""))
}

function WhySuggested({ candidate, names }: { candidate: Candidate; names: Map<string, string> }) {
  // Readable chains such as "pallor, fatigue → Pandu → Medication chosen according to the dosha".
  // Paths that differ only in their starting symptom are merged, and the option's own name
  // (always the last step) is left out, since it is already the row's title.
  const bySharedRoute = new Map<string, string[]>()
  for (const path of candidate.paths) {
    const ids = path.concept_ids.at(-1) === candidate.candidate_id ? path.concept_ids.slice(0, -1) : path.concept_ids
    if (ids.length === 0) continue
    const [start, ...route] = ids.map((id) => readableName(id, names))
    const key = route.join(" → ")
    bySharedRoute.set(key, Array.from(new Set([...(bySharedRoute.get(key) ?? []), start])))
  }
  const chains = Array.from(bySharedRoute, ([route, starts]) => [starts.join(", "), route].filter(Boolean).join(" → "))
  const concerns = Array.from(
    new Set(
      [...candidate.conflict_flags, ...candidate.sufficiency.uncertainty_flags, ...candidate.sufficiency.evidence_gaps]
        .filter((flag) => !INFORMATIONAL_FLAGS.has(flag))
        .map((flag) => describeFlag(flag).label),
    ),
  )
  return (
    <div className="grid grid-cols-1 gap-4 border-t border-slate-100 bg-slate-50/60 px-4 py-4 md:grid-cols-2">
      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Why it was suggested</p>
        {chains.length === 0 ? (
          <p className="text-sm text-slate-500">No reasoning path was returned.</p>
        ) : (
          <ul className="space-y-1">
            {chains.slice(0, MAX_PATHS).map((chain) => (
              <li key={chain} className="text-sm text-slate-800">
                {chain}
              </li>
            ))}
            {chains.length > MAX_PATHS && (
              <li className="text-xs text-slate-500">and {chains.length - MAX_PATHS} more link(s)</li>
            )}
          </ul>
        )}
      </div>
      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Points to check</p>
        {concerns.length === 0 ? (
          <p className="text-sm text-slate-500">None reported.</p>
        ) : (
          <ul className="space-y-1">
            {concerns.map((concern) => (
              <li key={concern} className="flex gap-2 text-sm text-slate-800">
                <AlertTriangle aria-hidden className="mt-0.5 size-3.5 shrink-0 text-amber-600" />
                {concern}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function CandidateList({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const [filter, setFilter] = React.useState<Filter>("all")
  const [scope, setScope] = React.useState<Scope>("top")
  const [open, setOpen] = React.useState<string | null>(null)
  const names = React.useMemo(() => conceptNames(output), [output])
  const report = record.c3.status === "success" ? record.c3.data : null

  // Default: only the best-ranked herb, formulation, diet and lifestyle option.
  const pool = scope === "top" ? topCandidatePerCategory(output) : output.candidates
  const candidates = pool.filter((candidate) =>
    filter === "all"
      ? true
      : filter === "review"
        ? candidate.disposition === "withheld_pending_review"
        : candidate.disposition === "forward_for_safety_assessment",
  )

  return (
    <div className="space-y-4">
      {output.abstention.abstain && (
        <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-slate-800">
          <CircleSlash aria-hidden className="mt-0.5 size-5 shrink-0 text-amber-600" />
          <p>
            <strong>No recommendation for this case.</strong> The evidence check was not met. Options below are shown
            for reference only and are not suggested.
          </p>
        </div>
      )}

      <section className="rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/30">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-900">
            {scope === "top"
              ? `Top option per category (${candidates.length} of ${output.candidates.length})`
              : `${candidates.length} option${candidates.length === 1 ? "" : "s"}`}
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <FilterChips
              label="View"
              value={scope}
              onChange={setScope}
              options={[
                { value: "top", label: "Top per category" },
                { value: "all", label: `All ${output.candidates.length}` },
              ]}
            />
            <FilterChips
              label="Show"
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All" },
                { value: "review", label: "Needs review" },
                { value: "safety", label: "Sent to safety check" },
              ]}
            />
          </div>
        </header>

        {output.candidates.length === 0 ? (
          <EmptyState icon={CircleSlash} title="No options found" description="No option was found for these symptoms." />
        ) : candidates.length === 0 ? (
          <EmptyState icon={CircleSlash} title="No options match this filter" />
        ) : (
          <ol className="divide-y divide-slate-100">
            {candidates.map((candidate) => {
              const expanded = open === candidate.candidate_id
              const safety = report?.evaluations.find((evaluation) => evaluation.candidate_id === candidate.candidate_id)
              return (
                <li key={candidate.candidate_id}>
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : candidate.candidate_id)}
                    className={cn(
                      "flex w-full flex-wrap items-center justify-between gap-3 px-5 py-3 text-left transition hover:bg-slate-50",
                      expanded && "bg-emerald-50/30",
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                        {candidate.rank}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold text-slate-900">
                          {candidate.name ?? humanizeCode(candidate.candidate_id)}
                          {candidate.botanical_name && (
                            <span className="ml-1.5 font-normal text-slate-500 italic">{candidate.botanical_name}</span>
                          )}
                        </span>
                        <span className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                          {candidate.category}
                          <TypeMatch candidate={candidate} names={names} />
                        </span>
                      </span>
                    </span>
                    <span className="flex flex-wrap items-center gap-2">
                      {safety ? <StatusBadge spec={safetySpec(safety.safety_tier)} /> : <CandidateStatus candidate={candidate} />}
                      <StatusBadge spec={sufficiencySpec(candidate.sufficiency.status)} />
                      <ChevronDown
                        aria-hidden
                        className={cn("size-4 text-slate-400 transition-transform", expanded && "rotate-180")}
                      />
                    </span>
                  </button>
                  {expanded && (
                    <>
                      <WhySuggested candidate={candidate} names={names} />
                      {safety?.summary_warning && (
                        <p className="border-t border-slate-100 bg-slate-50/60 px-5 py-3 text-sm text-slate-700">
                          <span className="font-medium">Safety note:</span> {safety.summary_warning}
                        </p>
                      )}
                    </>
                  )}
                </li>
              )
            })}
          </ol>
        )}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <p>Suggestions from the knowledge base, not prescriptions. No dosage is given; every option needs your review.</p>
        <Link to="/safety" className="inline-flex items-center gap-1 font-semibold text-emerald-700 hover:text-emerald-900">
          Go to safety check <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </div>
    </div>
  )
}
