import * as React from "react"
import { Link } from "react-router"
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleSlash,
  ClipboardCheck,
  Leaf,
  ShieldCheck,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { ResearchScopeBanner } from "@/components/shared/c2"
import { StatusBadge, safetySpec, sufficiencySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import type { CaseRecord } from "@/context/workspace"
import { useAccess } from "@/lib/access"
import type { Candidate, Component2Output, SafetyAssessmentReport } from "@/lib/api/types"
import { conceptNames, topCandidatePerCategory } from "@/lib/c2-derive"
import { formatDateTime, humanizeCode } from "@/lib/labels"
import { cn } from "@/lib/utils"

/**
 * Clean clinical view of a Component 2 result, for Ayurvedic practitioners.
 * Shows only what a doctor needs to act; identifiers, claims, evidence policy
 * and retrieval settings stay in the technical view (supervisors, researchers).
 */


type Outcome = { title: string; text: string; icon: LucideIcon; className: string; iconClassName: string }

function outcomeFor(output: Component2Output): Outcome {
  if (output.abstention.abstain || output.decision === "abstain") {
    return {
      title: "No recommendation for this case",
      // The service's own explanation lists policy codes; it stays in the technical view.
      text: "There is not enough reliable evidence to suggest options. Please assess the patient directly.",
      icon: CircleSlash,
      className: "border-amber-200 bg-amber-50/70",
      iconClassName: "bg-amber-100 text-amber-700",
    }
  }
  if (output.decision === "caution") {
    return {
      title: "Options found, review with caution",
      text: "Some evidence is conflicting or unverified, or the screening result needs extra care. Check the notes below.",
      icon: AlertTriangle,
      className: "border-amber-200 bg-amber-50/70",
      iconClassName: "bg-amber-100 text-amber-700",
    }
  }
  return {
    title: "Options found for your review",
    text: "The evidence check passed. Review the suggested options and confirm or reject them.",
    icon: CheckCircle2,
    className: "border-emerald-200 bg-emerald-50/60",
    iconClassName: "bg-emerald-100 text-emerald-700",
  }
}

/** Evidence status codes in a doctor's words. */
const evidenceReasonText: Record<string, string> = {
  insufficient_evidence: "There is not enough supporting evidence.",
  conflicting_evidence: "Some evidence contradicts the suggested links.",
  unverified_claims: "Some of the knowledge used has not been verified yet.",
  out_of_scope: "The symptoms are outside what the knowledge base covers.",
}

/** Plain-language reasons behind a caution or abstention (no codes or IDs). */
function outcomeReasons(output: Component2Output): string[] {
  const evidence = [output.sufficiency_status, ...output.decision_reasons.map((reason) => reason.replace(/^evidence:/, ""))]
    .map((code) => evidenceReasonText[code])
    .filter((text): text is string => Boolean(text))
  // Screening-risk notes (for example a high anaemia risk tier) are already written for clinicians
  return Array.from(new Set([...output.risk_context.escalation, ...evidence])).slice(0, 4)
}

function Card({
  title,
  icon: Icon,
  actions,
  children,
  className,
}: {
  title: string
  icon?: LucideIcon
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={cn("rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/30", className)}>
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {Icon && <Icon aria-hidden className="size-4 text-emerald-700" />}
          {title}
        </h2>
        {actions}
      </header>
      {children}
    </section>
  )
}

function OutcomeCard({ output }: { output: Component2Output }) {
  const outcome = outcomeFor(output)
  const reasons = outcomeReasons(output)
  const Icon = outcome.icon
  return (
    <section className={cn("rounded-2xl border p-5", outcome.className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", outcome.iconClassName)}>
            <Icon aria-hidden className="size-5" />
          </span>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-900">{outcome.title}</h2>
            <p className="mt-0.5 text-sm text-slate-700">{outcome.text}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
          Evidence <StatusBadge spec={sufficiencySpec(output.sufficiency_status)} />
        </div>
      </div>
      {reasons.length > 0 && (
        <ul className="mt-4 space-y-1 border-t border-black/5 pt-3 text-sm text-slate-700">
          {reasons.map((reason) => (
            <li key={reason} className="flex gap-2">
              <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-500" />
              {reason}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function SymptomsCard({ output }: { output: Component2Output }) {
  const found = output.symptom_mappings.filter((mapping) => mapping.found)
  const missing = output.symptom_mappings.filter((mapping) => !mapping.found)
  return (
    <Card title="Symptoms considered" icon={ClipboardCheck}>
      {found.length === 0 ? (
        <p className="text-sm text-slate-500">No symptom matched the knowledge base.</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {found.map((mapping) => (
            <li key={mapping.symptom_id} className="rounded-full bg-emerald-50 px-3 py-1 text-sm text-emerald-900 ring-1 ring-emerald-100">
              {mapping.name ?? humanizeCode(mapping.symptom_id)}
            </li>
          ))}
        </ul>
      )}
      {missing.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          Not in the knowledge base, so not used:{" "}
          {missing.map((mapping) => mapping.name ?? humanizeCode(mapping.symptom_id.replace(/^S-/, ""))).join(", ")}
        </p>
      )}
    </Card>
  )
}

const assessmentGroups: { type: string; label: string }[] = [
  { type: "Roga", label: "Condition (Roga)" },
  { type: "Dosha", label: "Dosha" },
  { type: "Dhatu", label: "Dhatu" },
  { type: "TherapeuticPrinciple", label: "Treatment principle" },
]

function AssessmentCard({ output }: { output: Component2Output }) {
  const groups = assessmentGroups
    .map((group) => ({ ...group, concepts: output.interpretation.filter((concept) => concept.concept_type === group.type) }))
    .filter((group) => group.concepts.length > 0)

  return (
    <Card title="Ayurvedic assessment" icon={Leaf}>
      {groups.length === 0 ? (
        <p className="text-sm text-slate-500">The knowledge base did not link these symptoms to any Ayurvedic concept.</p>
      ) : (
        <dl className="space-y-3">
          {groups.map((group) => (
            <div key={group.type}>
              <dt className="mb-1 text-xs font-medium text-slate-500">{group.label}</dt>
              <dd className="flex flex-wrap gap-1.5">
                {group.concepts.map((concept) => {
                  const conflicting = concept.contradicting_evidence_ids.length > 0
                  return (
                    <span
                      key={concept.concept_id}
                      title={conflicting ? "Some evidence contradicts this" : undefined}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm ring-1",
                        conflicting ? "bg-amber-50 text-amber-900 ring-amber-200" : "bg-slate-50 text-slate-800 ring-slate-200",
                      )}
                    >
                      {conflicting && <AlertTriangle aria-hidden className="size-3.5 text-amber-600" />}
                      {concept.name ?? humanizeCode(concept.concept_id)}
                      {conflicting && <span className="sr-only">(some evidence contradicts this)</span>}
                    </span>
                  )
                })}
              </dd>
            </div>
          ))}
        </dl>
      )}
      <p className="mt-4 text-xs text-slate-500">Links found in the Ayurvedic knowledge base, not a diagnosis.</p>
    </Card>
  )
}

const categoryLabels: Record<Candidate["category"], string> = {
  Herb: "Herb",
  Formulation: "Formulation",
  Diet: "Diet",
  Lifestyle: "Lifestyle",
}

function safetyFor(report: SafetyAssessmentReport | null, candidateId: string) {
  return report?.evaluations.find((evaluation) => evaluation.candidate_id === candidateId)
}

/** "Matches Pittaja Pandu": why a candidate is listed before the general remedies. */
export function TypeMatch({ candidate, names }: { candidate: Candidate; names: Map<string, string> }) {
  const matched = candidate.matched_subtypes ?? []
  if (matched.length === 0) return null
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-800 ring-1 ring-emerald-100">
      Matches {matched.map((id) => names.get(id) ?? humanizeCode(id)).join(", ")}
    </span>
  )
}

export function CandidateStatus({ candidate }: { candidate: Candidate }) {
  return candidate.disposition === "withheld_pending_review" ? (
    <span className="text-xs font-medium text-amber-800">Needs your review</span>
  ) : (
    <span className="text-xs text-slate-500">Sent to safety check</span>
  )
}

function OptionsCard({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const report = record.c3.status === "success" ? record.c3.data : null
  const shown = topCandidatePerCategory(output)
  const abstained = output.abstention.abstain
  const names = React.useMemo(() => conceptNames(output), [output])

  return (
    <Card
      title="Suggested options"
      actions={
        output.candidates.length > 0 && (
          <Link to="/candidates" className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-900">
            {abstained ? "View withheld options" : `View all ${output.candidates.length}`} <ArrowRight aria-hidden className="size-3.5" />
          </Link>
        )
      }
    >
      {abstained || shown.length === 0 ? (
        <p className="text-sm text-slate-500">
          {abstained ? "No option is suggested, because the evidence check was not met." : "No option was found for these symptoms."}
        </p>
      ) : (
        <ol className="divide-y divide-slate-100">
          {shown.map((candidate) => {
            const safety = safetyFor(report, candidate.candidate_id)
            return (
              <li key={candidate.candidate_id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                    {candidate.rank}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900">
                      {candidate.name ?? humanizeCode(candidate.candidate_id)}
                      {candidate.botanical_name && (
                        <span className="ml-1.5 font-normal text-slate-500 italic">{candidate.botanical_name}</span>
                      )}
                    </p>
                    <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      {categoryLabels[candidate.category] ?? candidate.category}
                      <TypeMatch candidate={candidate} names={names} />
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {safety ? <StatusBadge spec={safetySpec(safety.safety_tier)} /> : <CandidateStatus candidate={candidate} />}
                  <StatusBadge spec={sufficiencySpec(candidate.sufficiency.status)} />
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}

function NextSteps({ record }: { record: CaseRecord }) {
  const { allows } = useAccess()
  const safety = record.c3
  const reviewed = record.feedback.filter((entry) => entry.outcome.status === "recorded").length

  return (
    <Card title="Next steps">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 p-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ShieldCheck aria-hidden className="size-4 text-emerald-700" /> 1. Safety check
            </p>
            <div className="mt-1.5 text-sm text-slate-600">
              {safety.status === "success" ? (
                <span className="flex flex-wrap items-center gap-2">
                  Result <StatusBadge spec={safetySpec(safety.data.overall_safety_tier)} />
                </span>
              ) : safety.status === "loading" ? (
                "Running…"
              ) : safety.status === "error" ? (
                <span className="text-rose-700">The safety check failed. Try again.</span>
              ) : (
                "Not done yet. Check herb–drug interactions before using any option."
              )}
            </div>
          </div>
          <Button variant="outline" size="sm" className="self-start" render={<Link to="/safety" />} nativeButton={false}>
            {safety.status === "success" ? "View safety check" : "Start safety check"}
          </Button>
        </div>
        {allows(["practitioner", "supervisor"]) && (
          <div className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 p-4">
            <div>
              <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <ClipboardCheck aria-hidden className="size-4 text-emerald-700" /> 2. Your review
              </p>
              <p className="mt-1.5 text-sm text-slate-600">
                {reviewed > 0
                  ? `${reviewed} review${reviewed === 1 ? "" : "s"} recorded for this case.`
                  : "Approve, change or reject the suggested options."}
              </p>
            </div>
            <Button size="sm" className="self-start bg-emerald-700 hover:bg-emerald-800" render={<Link to="/review" />} nativeButton={false}>
              Open review
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}

export function AnalysisSummary({ output, record }: { output: Component2Output; record: CaseRecord }) {
  return (
    <div className="space-y-5">
      <ResearchScopeBanner output={output} />
      <OutcomeCard output={output} />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <SymptomsCard output={output} />
        <AssessmentCard output={output} />
      </div>
      <OptionsCard output={output} record={record} />
      <NextSteps record={record} />
      <p className="text-xs text-slate-500">
        Decision support only: not a diagnosis or a prescription, and no dosage is given. Every option needs a
        practitioner's review. Analysed {formatDateTime(output.generated_at)}.
      </p>
    </div>
  )
}
