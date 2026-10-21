import * as React from "react"
import { Link } from "react-router"
import { ChevronDown, ChevronRight, CircleSlash, ListOrdered } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ClaimCard, ConceptPath, ExplanationList, FlagList, ScoreCaveat } from "@/components/shared/c2"
import { EmptyState, FilterChips, IdChip, Notice, PageHeader, Panel } from "@/components/shared/page"
import {
  StatusBadge,
  abstentionSpec,
  dispositionSpec,
  safetySpec,
  sufficiencySpec,
  verificationSpec,
} from "@/components/shared/status"
import type { CaseRecord } from "@/context/workspace"
import type { Candidate, Component2Output } from "@/lib/api/types"
import { conceptNames } from "@/lib/c2-derive"
import { formatScore, rankingComponentLabels } from "@/lib/labels"
import { cn } from "@/lib/utils"

type Filter = "all" | "forwarded" | "withheld"

function reviewStatus(record: CaseRecord, candidateId: string) {
  const entries = record.feedback.filter((entry) => entry.request.candidate_ids.includes(candidateId))
  if (entries.length === 0) return "Not reviewed"
  const latest = entries[0]
  const outcome = latest.request.review_outcome.replace(/_/g, " ")
  if (latest.outcome.status === "recorded") return `Feedback recorded: ${outcome}`
  if (latest.outcome.status === "demo_not_sent") return `Demo feedback (not sent): ${outcome}`
  return "Feedback submission failed"
}

function RankingBreakdownView({ candidate }: { candidate: Candidate }) {
  const entries = Object.entries(candidate.ranking.components)
  const maxAbs = Math.max(0.01, ...entries.map(([, value]) => Math.abs(value)))
  return (
    <div>
      <ul className="space-y-1.5">
        {entries.map(([key, value]) => (
          <li key={key} className="grid grid-cols-[150px_minmax(0,1fr)_48px] items-center gap-2 text-xs">
            <span className="text-slate-600">{rankingComponentLabels[key] ?? key}</span>
            <span className="relative h-2 rounded-full bg-slate-100" aria-hidden>
              <span
                className={cn("absolute inset-y-0 left-0 rounded-full", value < 0 ? "bg-rose-400" : "bg-emerald-500")}
                style={{ width: `${(Math.abs(value) / maxAbs) * 100}%` }}
              />
            </span>
            <span className="text-right font-mono text-slate-700">{value.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-slate-500">Policy: {candidate.ranking.policy_id}</p>
    </div>
  )
}

function CandidateDetail({
  candidate,
  output,
  record,
}: {
  candidate: Candidate
  output: Component2Output
  record: CaseRecord
}) {
  const names = React.useMemo(() => conceptNames(output), [output])
  const safety =
    record.c3.status === "success"
      ? record.c3.data.evaluations.find((evaluation) => evaluation.candidate_id === candidate.candidate_id)
      : undefined

  return (
    <div className="grid grid-cols-1 gap-5 bg-slate-50/60 p-4 lg:grid-cols-2">
      <div className="space-y-4">
        <section>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Reasoning rationale</h4>
          <ExplanationList statements={candidate.rationale} />
        </section>
        <section>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Experimental ranking breakdown</h4>
          <RankingBreakdownView candidate={candidate} />
        </section>
        <section>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Uncertainty, conflicts and gaps</h4>
          <FlagList flags={[...candidate.conflict_flags, ...candidate.sufficiency.uncertainty_flags, ...candidate.sufficiency.evidence_gaps]} />
          <p className="mt-2 text-[11px] text-slate-500">Sufficiency policy: {candidate.sufficiency.policy_id}</p>
        </section>
        <section>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Safety (Component 3)</h4>
          {safety ? (
            <div className="space-y-1">
              <StatusBadge spec={safetySpec(safety.safety_tier)} />
              <p className="text-xs text-slate-600">{safety.summary_warning}</p>
            </div>
          ) : (
            <p className="text-xs text-slate-500">
              Not assessed. Contraindications and interactions are identified by Component 3, not by Component 2.
            </p>
          )}
        </section>
      </div>
      <div className="space-y-4">
        <h4 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
          Reasoning paths ({candidate.paths.length})
        </h4>
        {candidate.paths.map((path, index) => (
          <div key={index} className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold text-slate-600">Path {index + 1}</p>
            <ConceptPath ids={path.concept_ids} names={names} />
            <div className="space-y-2">
              {path.claims.map((claim) => (
                <ClaimCard key={claim.claim_id} claim={claim} names={names} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function CandidateTable({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const [filter, setFilter] = React.useState<Filter>("all")
  const [expanded, setExpanded] = React.useState<string | null>(output.candidates[0]?.candidate_id ?? null)

  const candidates = output.candidates.filter((candidate) =>
    filter === "all"
      ? true
      : filter === "forwarded"
        ? candidate.disposition === "forward_for_safety_assessment"
        : candidate.disposition === "withheld_pending_review",
  )

  return (
    <div className="space-y-4">
      {output.abstention.abstain && (
        <Notice tone="caution" title="Component 2 abstained">
          <StatusBadge spec={abstentionSpec} className="mb-1" />
          <p>
            No candidate met the evidence policy. Any candidates listed below are shown for transparency only and
            are not recommendations.
          </p>
        </Notice>
      )}
      {output.decision === "caution" && (
        <Notice tone="caution" title="Decision: caution">
          {output.risk_context.escalation.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5">
              {output.risk_context.escalation.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : (
            <p>Some evidence is conflicting or unverified. Review the withheld candidates and their evidence.</p>
          )}
          <p className="mt-1.5 text-xs">The order and dispositions below are not changed by risk rules.</p>
        </Notice>
      )}
      <Notice tone="neutral">
        These are system-generated candidates, not practitioner-approved recommendations. No dosage, treatment
        instruction or efficacy estimate is produced. The ranking score is an experimental engineering score from
        a provisional policy, not a probability of clinical success.
      </Notice>

      <Panel
        title={`${candidates.length} of ${output.candidates.length} candidates`}
        actions={
          <FilterChips
            label="Disposition"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "All" },
              { value: "forwarded", label: "Forwarded" },
              { value: "withheld", label: "Withheld" },
            ]}
          />
        }
        bodyClassName="p-0"
      >
        {output.candidates.length === 0 ? (
          <EmptyState icon={CircleSlash} title="No candidates generated" description="Component 2 did not find a valid candidate path. No candidates are substituted." />
        ) : candidates.length === 0 ? (
          <EmptyState icon={ListOrdered} title="No candidates match this filter" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead>
                <tr className="bg-slate-50/70 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="w-10 px-3 py-3"><span className="sr-only">Expand</span></th>
                  <th className="px-3 py-3">Rank</th>
                  <th className="px-3 py-3">Candidate</th>
                  <th className="px-3 py-3">Type</th>
                  <th className="px-3 py-3">Experimental score</th>
                  <th className="px-3 py-3">Evidence</th>
                  <th className="px-3 py-3">Sufficiency</th>
                  <th className="px-3 py-3">Disposition</th>
                  <th className="px-3 py-3">Verification</th>
                  <th className="px-4 py-3">Practitioner review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {candidates.map((candidate) => {
                  const open = expanded === candidate.candidate_id
                  return (
                    <React.Fragment key={candidate.candidate_id}>
                      <tr className={cn("align-top", open && "bg-emerald-50/30")}>
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            aria-expanded={open}
                            aria-label={`${open ? "Collapse" : "Expand"} details for ${candidate.name ?? candidate.candidate_id}`}
                            onClick={() => setExpanded(open ? null : candidate.candidate_id)}
                            className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                          >
                            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                          </button>
                        </td>
                        <td className="px-3 py-3 font-semibold text-slate-800">#{candidate.rank}</td>
                        <td className="px-3 py-3">
                          <p className="font-semibold text-slate-900">{candidate.name ?? candidate.candidate_id}</p>
                          <IdChip>{candidate.candidate_id}</IdChip>
                        </td>
                        <td className="px-3 py-3 text-xs text-slate-600">{candidate.category}</td>
                        <td className="px-3 py-3 font-mono text-xs">{formatScore(candidate.ranking.score)}</td>
                        <td className="px-3 py-3 text-xs">
                          <span className="text-emerald-800">{candidate.supporting_evidence_ids.length} supporting</span>
                          <br />
                          <span className={candidate.contradicting_evidence_ids.length ? "font-semibold text-rose-700" : "text-slate-500"}>
                            {candidate.contradicting_evidence_ids.length} contradicting
                          </span>
                        </td>
                        <td className="px-3 py-3"><StatusBadge spec={sufficiencySpec(candidate.sufficiency.status)} /></td>
                        <td className="px-3 py-3"><StatusBadge spec={dispositionSpec(candidate.disposition)} /></td>
                        <td className="px-3 py-3">
                          <div className="flex flex-col items-start gap-1">
                            {Array.from(new Set(candidate.verification_statuses)).map((status) => (
                              <StatusBadge key={status} spec={verificationSpec(status)} />
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">{reviewStatus(record, candidate.candidate_id)}</td>
                      </tr>
                      {open && (
                        <tr>
                          <td colSpan={10} className="p-0">
                            <CandidateDetail candidate={candidate} output={output} record={record} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="border-t border-slate-100 px-5 py-3">
          <ScoreCaveat>{output.score_semantics["ranking.score"] ?? "Experimental ranking score; not clinical confidence."}</ScoreCaveat>
        </div>
      </Panel>

      <div className="flex flex-wrap gap-2 text-sm">
        <Link to="/safety" className="font-semibold text-emerald-700 hover:text-emerald-900">
          Send forwarded candidates to the safety assessment →
        </Link>
      </div>
    </div>
  )
}

export function CandidatesPage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 2 · Recommendation"
        title="Recommendation candidates"
        description="Ranked herb, formulation, diet and lifestyle candidates with their evidence, rationale, uncertainty and review status."
      />
      <CaseBar />
      <WithReasoning>{(output, record) => <CandidateTable output={output} record={record} />}</WithReasoning>
    </>
  )
}
