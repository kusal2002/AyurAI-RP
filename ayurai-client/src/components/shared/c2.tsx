import * as React from "react"
import { ArrowRight, ExternalLink, Info, TriangleAlert } from "lucide-react"

import { IdChip } from "@/components/shared/page"
import { FilterChips, Notice } from "@/components/shared/page"
import {
  StatusBadge,
  evidenceRoleSpecs,
  provisionalSpec,
  relationshipSpecs,
  verificationSpec,
} from "@/components/shared/status"
import type {
  ClaimStep,
  Component2Output,
  EvidenceReference,
  ExplanationStatement,
  KnowledgeScope,
} from "@/lib/api/types"
import {
  conceptTypeLabels,
  describeFlag,
  evidenceTypeLabels,
  formatScore,
  humanizeCode,
  predicateLabels,
} from "@/lib/labels"
import { cn } from "@/lib/utils"

export function FlagList({
  flags,
  emptyText = "None reported.",
  tone = "caution",
}: {
  flags: string[]
  emptyText?: string
  tone?: "caution" | "neutral"
}) {
  if (flags.length === 0) return <p className="text-xs text-slate-500">{emptyText}</p>
  return (
    <ul className="space-y-1.5">
      {flags.map((flag) => {
        const { label, target } = describeFlag(flag)
        return (
          <li key={flag} className="flex items-start gap-2 text-sm text-slate-700">
            <TriangleAlert
              aria-hidden
              className={cn("mt-0.5 size-4 shrink-0", tone === "caution" ? "text-amber-600" : "text-slate-400")}
            />
            <span className="min-w-0">
              {label}
              {target && (
                <>
                  {" "}
                  <IdChip>{target}</IdChip>
                </>
              )}
              <span className="sr-only"> (code {flag})</span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function ExplanationList({ statements }: { statements: ExplanationStatement[] }) {
  if (statements.length === 0) {
    return <p className="text-xs text-slate-500">The service returned no explanation statements.</p>
  }
  return (
    <ol className="space-y-3">
      {statements.map((statement, index) => (
        <li key={`${statement.kind}-${index}`} className="rounded-xl border border-slate-200 p-3">
          <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">
            {humanizeCode(statement.kind)}
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-800">{statement.text}</p>
          {(statement.claim_ids.length > 0 || statement.evidence_ids.length > 0) && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
              {statement.claim_ids.length > 0 && <span>Claims:</span>}
              {statement.claim_ids.map((id) => (
                <IdChip key={id}>{id}</IdChip>
              ))}
              {statement.evidence_ids.length > 0 && <span className="ml-1">Evidence:</span>}
              {statement.evidence_ids.map((id) => (
                <IdChip key={id}>{id}</IdChip>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

export function ConceptLabel({
  id,
  type,
  names,
}: {
  id: string
  type?: string | null
  names: Map<string, string>
}) {
  const name = names.get(id)
  return (
    <span className="inline-flex min-w-0 flex-col">
      <span className="truncate text-sm font-medium text-slate-800">{name ?? id}</span>
      <span className="truncate text-[11px] text-slate-500">
        {[type ? conceptTypeLabels[type] ?? type : null, name ? id : null].filter(Boolean).join(" · ")}
      </span>
    </span>
  )
}

/** Joins the known parts; renders nothing when none are known. */
export function SourceLine({ parts }: { parts: (string | null | undefined)[] }) {
  const text = parts.filter(Boolean).join(" · ")
  return text ? <p className="text-xs text-slate-500">{text}</p> : null
}

export function EvidenceReferenceRow({
  reference,
  onSelect,
}: {
  reference: EvidenceReference
  onSelect?: (evidenceId: string) => void
}) {
  const spec = relationshipSpecs[reference.relationship]
  return (
    <li className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge spec={spec} />
          <IdChip>{reference.evidence_id}</IdChip>
          {reference.knowledge_status === "provisional" && <StatusBadge spec={provisionalSpec} />}
          {reference.evidence_role && evidenceRoleSpecs[reference.evidence_role] && (
            <StatusBadge spec={evidenceRoleSpecs[reference.evidence_role]} />
          )}
          {!reference.provenance_complete && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-800">
              <TriangleAlert aria-hidden className="size-3.5" /> Incomplete provenance
            </span>
          )}
        </div>
        {reference.title && <p className="mt-1 text-sm text-slate-800">{reference.title}</p>}
        <SourceLine
          parts={[
            reference.source_name,
            reference.evidence_type ? evidenceTypeLabels[reference.evidence_type] ?? reference.evidence_type : null,
          ]}
        />
      </div>
      {onSelect && (
        <button
          type="button"
          onClick={() => onSelect(reference.evidence_id)}
          className="text-xs font-semibold text-emerald-700 hover:text-emerald-900"
        >
          Inspect
        </button>
      )}
    </li>
  )
}

export function ClaimCard({
  claim,
  names,
  onSelectEvidence,
  compact = false,
}: {
  claim: ClaimStep
  names: Map<string, string>
  onSelectEvidence?: (evidenceId: string) => void
  compact?: boolean
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <IdChip>{claim.claim_id}</IdChip>
        <span className="flex flex-wrap items-center gap-1.5">
          {claim.knowledge_status === "provisional" && <StatusBadge spec={provisionalSpec} />}
          <StatusBadge spec={verificationSpec(claim.verification_status)} />
        </span>
      </div>
      <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        <ConceptLabel id={claim.subject_id} type={claim.subject_type} names={names} />
        <span className="flex flex-col items-center text-[10px] font-semibold text-emerald-700 uppercase">
          <ArrowRight aria-hidden className="size-4" />
          <span className="max-w-[110px] text-center leading-tight normal-case">
            {predicateLabels[claim.predicate] ?? claim.predicate}
          </span>
        </span>
        <ConceptLabel id={claim.object_id} type={claim.object_type} names={names} />
      </div>
      {claim.statement && (
        <p className="mt-2 text-sm leading-6 text-slate-700">“{claim.statement}”</p>
      )}
      <p className="mt-1 text-[11px] text-slate-500">
        Claim statement as stored in the knowledge graph · retrieval similarity{" "}
        {formatScore(claim.retrieval_similarity)} (relevance only) · stored confidence{" "}
        {claim.stored_confidence === null ? "not set" : formatScore(claim.stored_confidence)}
      </p>
      {claim.uncertainty_notes && claim.uncertainty_notes.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[11px] text-amber-800">
          {claim.uncertainty_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {claim.evidence_lookup_failed && (
        <p className="mt-2 text-xs font-medium text-rose-700">Evidence lookup failed for this claim.</p>
      )}
      {!compact && (
        <div className="mt-3 space-y-1.5">
          {claim.supporting_evidence.length + claim.contradicting_evidence.length === 0 ? (
            <p className="flex items-center gap-1.5 text-xs text-amber-800">
              <TriangleAlert aria-hidden className="size-3.5" /> No evidence is linked to this claim.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {[...claim.supporting_evidence, ...claim.contradicting_evidence].map((reference) => (
                <EvidenceReferenceRow
                  key={`${reference.relationship}-${reference.evidence_id}`}
                  reference={reference}
                  onSelect={onSelectEvidence}
                />
              ))}
            </ul>
          )}
          {claim.qualifying_evidence && claim.qualifying_evidence.length > 0 && (
            <div className="pt-1">
              <p className="text-[11px] font-semibold text-sky-800">
                Modern evidence that qualifies this claim (kept separate; not support)
              </p>
              <ul className="mt-1 space-y-1.5">
                {claim.qualifying_evidence.map((reference) => (
                  <EvidenceReferenceRow
                    key={`Q-${reference.evidence_id}`}
                    reference={reference}
                    onSelect={onSelectEvidence}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function parseHttpUrl(url: string): URL | null {
  try {
    const parsed = new URL(url)
    return ["http:", "https:"].includes(parsed.protocol) ? parsed : null
  } catch {
    return null
  }
}

export function SourceLink({ url }: { url: string | null }) {
  if (!url) return <span className="text-slate-400">Not supplied</span>
  const safe = parseHttpUrl(url)
  if (!safe) {
    return <span className="break-all">{url}</span>
  }
  return (
    <a
      href={safe.toString()}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 break-all text-emerald-700 underline-offset-2 hover:underline"
    >
      {safe.hostname}
      <ExternalLink aria-hidden className="size-3.5" />
    </a>
  )
}

export function ScoreCaveat({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-[11px] leading-5 text-slate-500">
      <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

/** Visual breadcrumb of a concept path as returned by the service. */
export function ConceptPath({ ids, names }: { ids: string[]; names: Map<string, string> }) {
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs">
      {ids.map((id, index) => (
        <li key={`${id}-${index}`} className="flex items-center gap-1">
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">
            {names.get(id) ?? id}
          </span>
          {index < ids.length - 1 && <ArrowRight aria-hidden className="size-3 text-slate-400" />}
        </li>
      ))}
    </ol>
  )
}

const scopeOptions: { value: KnowledgeScope; label: string }[] = [
  { value: "approved", label: "Approved knowledge only" },
  { value: "approved_and_provisional", label: "Research: include unverified drafts" },
]

/** Knowledge-scope selector for the next reasoning run (approved by default). */
export function KnowledgeScopeToggle({
  value,
  onChange,
}: {
  value: KnowledgeScope
  onChange: (value: KnowledgeScope) => void
}) {
  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-slate-700">Knowledge scope for Component 2</p>
        <FilterChips label="Knowledge scope" options={scopeOptions} value={value} onChange={onChange} />
      </div>
      {value === "approved_and_provisional" && (
        <p className="text-[11px] leading-5 text-amber-800">
          Research mode also reads AI-assisted draft claims quoted from classical texts. Every such item is labelled
          “{provisionalSpec.label}”, can never make a candidate sufficient, and is not clinical evidence.
        </p>
      )}
    </div>
  )
}

/** Output-level banner shown whenever an output was produced in research scope. */
export function ResearchScopeBanner({ output, className }: { output: Component2Output; className?: string }) {
  if (output.knowledge_scope !== "approved_and_provisional") return null
  const provisionalUsed = output.uncertainty_flags.includes("provisional_unverified_knowledge_used")
  return (
    <Notice tone="caution" title={`Research scope · ${provisionalSpec.label}`} className={className}>
      {provisionalUsed
        ? "This output uses provisional, AI-assisted draft claims that no practitioner has reviewed. They are quoted from the cited sources but are not approved knowledge; affected candidates are withheld pending review."
        : "This output was run in research scope; no provisional record was used."}
    </Notice>
  )
}
