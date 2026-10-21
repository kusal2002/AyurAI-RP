import * as React from "react"
import { Link } from "react-router"
import { Ban, CheckCircle2, ClipboardCheck, FilePenLine, Lock, Send, TriangleAlert, XCircle } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { FlagList } from "@/components/shared/c2"
import { EmptyState, IdChip, KeyValueList, Notice, PageHeader, Panel, fieldClass } from "@/components/shared/page"
import { StatusBadge, decisionSpec, safetySpec, sufficiencySpec } from "@/components/shared/status"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useAuth } from "@/context/auth"
import { useWorkspace, type CaseRecord, type FeedbackRecord } from "@/context/workspace"
import { errorMessage, isAbortError } from "@/lib/api/client"
import { component4Api, type Decision, type DecisionValue } from "@/lib/api/component4"
import type {
  Component2Output,
  IssueCategory,
  PractitionerFeedbackRequest,
  ReviewOutcome,
  ReviewerRole,
} from "@/lib/api/types"
import { indexClaims } from "@/lib/c2-derive"
import { formatDateTime, formatScore, humanizeCode } from "@/lib/labels"

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/

const outcomes: { value: ReviewOutcome; label: string }[] = [
  { value: "agree", label: "Agree" },
  { value: "disagree", label: "Disagree" },
  { value: "needs_more_evidence", label: "Needs more evidence" },
  { value: "uncertain", label: "Uncertain" },
]

const issues: IssueCategory[] = [
  "none",
  "missing_evidence",
  "contradicting_evidence",
  "incorrect_relationship",
  "incorrect_concept_mapping",
  "provenance_problem",
  "source_misinterpreted",
  "out_of_scope",
  "other",
]

const roles: { value: ReviewerRole; label: string }[] = [
  { value: "ayurvedic_practitioner", label: "Ayurvedic practitioner" },
  { value: "researcher", label: "Researcher" },
  { value: "supervisor", label: "Supervisor" },
]

function CaseSummary({ output, record }: { output: Component2Output; record: CaseRecord }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Panel title="Component 1 · Screening" actions={<Link className="text-xs font-semibold text-emerald-700" to="/screenings">Records</Link>}>
        <KeyValueList
          items={[
            { label: "Risk tier", value: <span className="capitalize">{output.upstream.risk_tier}</span> },
            { label: "Calibrated confidence", value: formatScore(output.upstream.calibrated_confidence) },
            { label: "Symptoms mapped", value: `${output.symptom_mappings.filter((m) => m.found).length} of ${output.symptom_mappings.length}` },
            { label: "Origin", value: record.c1?.origin === "c1_payload" ? "Imported C1 payload" : "Manual entry" },
          ]}
        />
      </Panel>
      <Panel title="Component 2 · Reasoning" actions={<Link className="text-xs font-semibold text-emerald-700" to="/analysis">Analysis</Link>}>
        <div className="space-y-2">
          <StatusBadge spec={decisionSpec(output.decision)} />
          <StatusBadge spec={sufficiencySpec(output.sufficiency_status)} />
          <KeyValueList
            items={[
              { label: "Interpreted concepts", value: output.interpretation.length },
              { label: "Candidates", value: output.candidates.length },
              {
                label: "Forwarded to safety",
                value: output.candidates.filter((c) => c.disposition === "forward_for_safety_assessment").length,
              },
              { label: "With conflicting evidence", value: output.candidates.filter((c) => c.contradicting_evidence_ids.length > 0).length },
            ]}
          />
        </div>
      </Panel>
      <Panel title="Component 3 · Safety" actions={<Link className="text-xs font-semibold text-emerald-700" to="/safety">Safety</Link>}>
        {record.c3.status === "success" ? (
          <div className="space-y-2">
            <StatusBadge spec={safetySpec(record.c3.data.overall_safety_tier)} />
            <KeyValueList
              items={[
                { label: "Candidates evaluated", value: record.c3.data.evaluations.length },
                { label: "Escalations", value: record.c3.data.evaluations.filter((e) => e.escalate_to_practitioner).length },
                {
                  label: "Contraindications",
                  value: record.c3.data.evaluations.reduce((sum, e) => sum + e.contraindications_triggered.length, 0),
                },
              ]}
            />
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            {record.c3.status === "error" ? "Safety assessment failed." : "Not yet assessed."} Review cannot rely on
            Component 2 ranking alone.
          </p>
        )}
      </Panel>
    </div>
  )
}

function AttentionList({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const items: { label: string; flags: string[] }[] = [
    { label: "Abstention reasons", flags: output.abstention.reasons },
    { label: "Unmapped symptom IDs", flags: output.symptom_mappings.filter((m) => !m.found).map((m) => `unmapped:${m.symptom_id}`) },
    { label: "Conflicts", flags: Array.from(new Set(output.candidates.flatMap((c) => c.conflict_flags))) },
    { label: "Uncertainty", flags: output.uncertainty_flags },
    { label: "Evidence gaps", flags: output.evidence_gaps },
    {
      label: "Safety escalations",
      flags:
        record.c3.status === "success"
          ? record.c3.data.evaluations.filter((e) => e.escalate_to_practitioner).map((e) => `escalation:${e.candidate_name}`)
          : ["safety_assessment_not_available"],
    },
  ].filter((item) => item.flags.length > 0)

  if (items.length === 0) return <p className="text-sm text-slate-500">No conflicts, gaps or missing information were reported.</p>
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {items.map((item) => (
        <div key={item.label}>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">{item.label}</h4>
          <FlagList flags={item.flags} />
        </div>
      ))}
    </div>
  )
}

function MultiSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { id: string; label: string }[]
  value: string[]
  onChange: (value: string[]) => void
}) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-slate-700">{label}</legend>
      {options.length === 0 ? (
        <p className="mt-1 text-xs text-slate-500">None available.</p>
      ) : (
        <div className="mt-2 max-h-44 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
          {options.map((option) => (
            <label key={option.id} className="flex items-start gap-2 rounded px-1 py-1 text-xs text-slate-700 hover:bg-slate-50">
              <Checkbox
                checked={value.includes(option.id)}
                onCheckedChange={(checked) =>
                  onChange(checked === true ? [...value, option.id] : value.filter((id) => id !== option.id))
                }
                className="mt-0.5"
              />
              <span className="min-w-0 break-words">{option.label}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  )
}

function FeedbackForm({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const { submitFeedback } = useWorkspace()
  const claims = React.useMemo(() => Array.from(indexClaims(output).values()), [output])
  const [candidateIds, setCandidateIds] = React.useState<string[]>([])
  const [claimIds, setClaimIds] = React.useState<string[]>([])
  const [outcome, setOutcome] = React.useState<ReviewOutcome | "">("")
  const [issue, setIssue] = React.useState<IssueCategory>("none")
  const [rationale, setRationale] = React.useState("")
  const [terms, setTerms] = React.useState("")
  const [role, setRole] = React.useState<ReviewerRole | "">("")
  const [reviewerRef, setReviewerRef] = React.useState("")
  const [confirming, setConfirming] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [lastResult, setLastResult] = React.useState<FeedbackRecord | null>(null)
  const [showErrors, setShowErrors] = React.useState(false)

  const refinementTerms = terms.split(",").map((term) => term.trim()).filter(Boolean)
  const errors = {
    target: candidateIds.length === 0 && claimIds.length === 0 ? "Select at least one candidate or claim." : "",
    outcome: outcome ? "" : "Select a review outcome.",
    rationale: rationale.trim() ? (rationale.length > 2000 ? "Maximum 2000 characters." : "") : "Enter a rationale.",
    role: role ? "" : "Select your reviewer role.",
    reviewerRef: ID_PATTERN.test(reviewerRef.trim()) ? "" : "Use a pseudonymous reference (letters, digits, . _ : -).",
    terms:
      refinementTerms.length > 10 || refinementTerms.some((term) => term.length > 64)
        ? "Up to 10 terms of at most 64 characters."
        : "",
  }
  const valid = Object.values(errors).every((message) => !message)

  function buildRequest(): PractitionerFeedbackRequest {
    return {
      request_id: output.request_id,
      claim_ids: claimIds,
      candidate_ids: candidateIds,
      evidence_ids: [],
      review_outcome: outcome as ReviewOutcome,
      issue_category: issue,
      rationale: rationale.trim(),
      refinement_terms: refinementTerms,
      suggested_concept_ids: [],
      reviewer_role: role as ReviewerRole,
      reviewer_ref: reviewerRef.trim(),
    }
  }

  async function confirmSubmit() {
    setConfirming(false)
    setSubmitting(true)
    const result = await submitFeedback(record.id, buildRequest())
    setSubmitting(false)
    setLastResult(result)
    if (result.outcome.status !== "error") {
      setRationale("")
      setTerms("")
      setOutcome("")
      setShowErrors(false)
    }
  }

  const error = (key: keyof typeof errors) =>
    showErrors && errors[key] ? <p className="mt-1 text-xs text-rose-700">{errors[key]}</p> : null

  return (
    <>
      <div className="space-y-5">
        <Notice tone="info">
          Feedback is an append-only review record stored by Component 2 (<code>POST /api/v1/c2/feedback</code>). It never
          changes a claim or its verification status and does not approve anything.
        </Notice>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <MultiSelect
            label="Candidates reviewed"
            value={candidateIds}
            onChange={setCandidateIds}
            options={output.candidates.map((candidate) => ({
              id: candidate.candidate_id,
              label: `#${candidate.rank} ${candidate.name ?? candidate.candidate_id}`,
            }))}
          />
          <MultiSelect
            label="Claims reviewed"
            value={claimIds}
            onChange={setClaimIds}
            options={claims.map(({ claim }) => ({
              id: claim.claim_id,
              label: `${claim.claim_id} — ${claim.statement ?? claim.predicate}`,
            }))}
          />
        </div>
        {error("target")}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <fieldset>
            <legend className="text-sm font-medium text-slate-700">Review outcome</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {outcomes.map((option) => (
                <label key={option.value} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${outcome === option.value ? "border-emerald-600 bg-emerald-50 text-emerald-900" : "border-slate-200 text-slate-700"}`}>
                  <input type="radio" name="review-outcome" checked={outcome === option.value} onChange={() => setOutcome(option.value)} className="accent-emerald-700" />
                  {option.label}
                </label>
              ))}
            </div>
            {error("outcome")}
          </fieldset>
          <label className="text-sm font-medium text-slate-700">
            Issue category
            <select value={issue} onChange={(event) => setIssue(event.target.value as IssueCategory)} className={fieldClass}>
              {issues.map((value) => (
                <option key={value} value={value}>{humanizeCode(value)}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Rationale
          <textarea
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
            rows={4}
            maxLength={2000}
            className={`${fieldClass} h-auto py-2`}
            placeholder="Explain your assessment of the reasoning and evidence."
          />
          <span className="mt-1 flex justify-between text-xs font-normal text-slate-400">
            <span>Do not include patient-identifying information; the rationale is stored in the knowledge graph database.</span>
            <span>{rationale.length}/2000</span>
          </span>
          {error("rationale")}
        </label>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">
            Refinement terms
            <input value={terms} onChange={(event) => setTerms(event.target.value)} placeholder="Comma-separated (optional)" className={fieldClass} />
            {error("terms")}
          </label>
          <label className="text-sm font-medium text-slate-700">
            Reviewer role
            <select value={role} onChange={(event) => setRole(event.target.value as ReviewerRole)} className={fieldClass}>
              <option value="">Select…</option>
              {roles.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            {error("role")}
          </label>
          <label className="text-sm font-medium text-slate-700">
            Pseudonymous reviewer reference
            <input value={reviewerRef} onChange={(event) => setReviewerRef(event.target.value)} placeholder="e.g. REV-07" className={fieldClass} />
            {error("reviewerRef")}
          </label>
        </div>
        <p className="text-xs text-slate-500">
          The reviewer role and reference are self-declared. Component 2 has no authentication, so they are not verified credentials.
        </p>

        <div className="flex justify-end border-t border-slate-100 pt-4">
          <Button
            className="bg-emerald-700 hover:bg-emerald-800"
            disabled={submitting}
            onClick={() => {
              setShowErrors(true)
              if (valid) setConfirming(true)
            }}
          >
            <Send /> {submitting ? "Submitting…" : "Review and submit feedback"}
          </Button>
        </div>

        {lastResult && <FeedbackResult entry={lastResult} />}
      </div>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Submit practitioner feedback?</AlertDialogTitle>
            <AlertDialogDescription>
              {"This creates a permanent, append-only feedback record in the Component 2 knowledge graph database for reasoning request " + output.request_id + "."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <KeyValueList
            items={[
              { label: "Outcome", value: outcome ? humanizeCode(outcome) : "—" },
              { label: "Issue", value: humanizeCode(issue) },
              { label: "Candidates", value: candidateIds.join(", ") || "—" },
              { label: "Claims", value: claimIds.join(", ") || "—" },
              { label: "Reviewer", value: `${role ? humanizeCode(role) : "—"} · ${reviewerRef}` },
            ]}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-emerald-700 hover:bg-emerald-800" onClick={confirmSubmit}>
              Submit feedback
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function FeedbackResult({ entry }: { entry: FeedbackRecord }) {
  if (entry.outcome.status === "error") {
    return (
      <Notice tone="critical" title="Feedback was not recorded">
        {entry.outcome.error.message}
        {entry.outcome.error.details.length > 0 && (
          <ul className="mt-1 list-disc pl-4">
            {entry.outcome.error.details.map((detail) => <li key={detail}>{detail}</li>)}
          </ul>
        )}
      </Notice>
    )
  }
  const response = entry.outcome.response
  return (
    <Notice tone="info" icon={CheckCircle2} title="Feedback recorded by Component 2">
      Feedback <code>{response.feedback_id}</code> linked to {response.linked_claim_ids.length} claim(s).
      {response.unknown_claim_ids.length > 0 && ` Unknown claim IDs: ${response.unknown_claim_ids.join(", ")}.`} Claims
      modified: no. Refinement retrieval: {response.refinement_retrieval.mode.replace(/_/g, " ")}.
    </Notice>
  )
}

function ReviewHistory({ record }: { record: CaseRecord }) {
  if (record.feedback.length === 0) {
    return <EmptyState icon={ClipboardCheck} title="No review activity in this session" description="Submitted feedback appears here. Earlier feedback stored in Component 2 cannot be listed because there is no read endpoint." />
  }
  return (
    <ol className="space-y-2">
      {record.feedback.map((entry) => (
        <li key={entry.localId} className="rounded-lg border border-slate-200 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-slate-800">{humanizeCode(entry.request.review_outcome)}</span>
            <span className="text-xs text-slate-500">{formatDateTime(entry.submittedAt)}</span>
          </div>
          <p className="mt-1 text-xs text-slate-600">
            {humanizeCode(entry.request.issue_category)} · {humanizeCode(entry.request.reviewer_role)} {entry.request.reviewer_ref}
          </p>
          <p className="mt-1 text-xs">
            {entry.outcome.status === "recorded" && <span className="text-emerald-800">Recorded as <IdChip>{entry.outcome.response.feedback_id}</IdChip></span>}
            {entry.outcome.status === "error" && <span className="text-rose-700">Failed: {entry.outcome.error.message}</span>}
          </p>
        </li>
      ))}
    </ol>
  )
}

const decisionOptions: { value: DecisionValue; label: string; icon: typeof CheckCircle2 }[] = [
  { value: "approve", label: "Approve", icon: CheckCircle2 },
  { value: "request_changes", label: "Request changes", icon: FilePenLine },
  { value: "reject", label: "Reject", icon: XCircle },
]

/**
 * Final clinical decision, recorded by the Component 4 service (FR4).
 * Every decision is written to the hash-chained audit log by the backend.
 */
function DecisionPanel({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const { user } = useAuth()
  const [history, setHistory] = React.useState<Decision[]>([])
  const [choice, setChoice] = React.useState<DecisionValue | null>(null)
  const [rationale, setRationale] = React.useState("")
  const [confirming, setConfirming] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const canDecide = user !== null && user.role !== "researcher"
  const needsRationale = choice !== null && choice !== "approve"
  const rationaleMissing = needsRationale && !rationale.trim()

  // Load earlier decisions for this case (scoped to the user's clinic by the backend)
  React.useEffect(() => {
    if (!canDecide) return
    const controller = new AbortController()
    component4Api
      .listDecisions(record.caseRef, controller.signal)
      .then(setHistory)
      .catch((err) => {
        if (!isAbortError(err)) setError(errorMessage(err))
      })
    return () => controller.abort()
  }, [canDecide, record.caseRef])

  async function submit() {
    if (!choice) return
    setConfirming(false)
    setSubmitting(true)
    setError(null)
    try {
      const saved = await component4Api.createDecision({
        case_ref: record.caseRef,
        c2_request_id: output.request_id,
        c3_assessment_id: record.c3.status === "success" ? record.c3.data.assessment_id : null,
        decision: choice,
        rationale: rationale.trim(),
      })
      setHistory((current) => [saved, ...current])
      setChoice(null)
      setRationale("")
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (!canDecide) {
    return (
      <div className="space-y-4">
        <Notice tone="neutral" icon={Lock} title="Decision recording needs a signed-in practitioner">
          {user?.role === "researcher"
            ? "Researchers can view results but cannot approve, reject or request changes."
            : "Sign in to record a decision."}{" "}
          Nothing has been approved.
        </Notice>
        <div className="flex flex-wrap gap-2">
          {decisionOptions.map(({ value, label, icon: Icon }) => (
            <Button key={value} disabled variant="outline"><Icon /> {label}</Button>
          ))}
        </div>
      </div>
    )
  }

  const latest = history[0]
  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Final decision" className="flex flex-wrap gap-2">
        {decisionOptions.map(({ value, label, icon: Icon }) => (
          <Button
            key={value}
            role="radio"
            aria-checked={choice === value}
            variant={choice === value ? "default" : "outline"}
            className={choice === value ? "bg-emerald-700 hover:bg-emerald-800" : undefined}
            onClick={() => setChoice(value)}
          >
            <Icon /> {label}
          </Button>
        ))}
      </div>

      {choice && (
        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            Rationale {needsRationale ? "(required)" : "(optional)"}
          </span>
          <textarea
            className={`${fieldClass} h-24 py-2`}
            maxLength={2000}
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
          <span className="mt-1 block text-[11px] text-slate-400">
            Stored with the decision. Not copied into the audit log, which keeps identifiers only.
          </span>
        </label>
      )}

      {error && <Notice tone="critical">{error}</Notice>}

      <Button
        disabled={!choice || rationaleMissing || submitting}
        onClick={() => setConfirming(true)}
        className="bg-emerald-700 hover:bg-emerald-800"
      >
        <Send /> {submitting ? "Recording…" : "Record decision"}
      </Button>

      <p className="flex items-center gap-1.5 text-xs text-slate-500">
        {latest ? (
          <>
            <CheckCircle2 aria-hidden className="size-3.5 text-emerald-700" /> Current decision:{" "}
            <strong className="text-slate-700">{humanizeCode(latest.decision)}</strong> by {latest.reviewer},{" "}
            {formatDateTime(latest.created_at)}
          </>
        ) : (
          <>
            <Ban aria-hidden className="size-3.5" /> Current decision: none recorded.
          </>
        )}
      </p>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Record “{choice ? humanizeCode(choice) : ""}” for {record.caseRef}?</AlertDialogTitle>
            <AlertDialogDescription>
              The decision is stored by Component 4 under your account ({user?.username}) and written to the
              tamper-evident audit log. It cannot be edited afterwards; record a new decision to change it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={submit}>Record decision</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function ReviewWorkspace({ output, record }: { output: Component2Output; record: CaseRecord }) {
  return (
    <div className="space-y-5">
      <CaseSummary output={output} record={record} />
      <Panel title="Conflicts, uncertainty and missing information" actions={<TriangleAlert aria-hidden className="size-4 text-amber-600" />}>
        <AttentionList output={output} record={record} />
      </Panel>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Panel title="Practitioner feedback on the reasoning">
          <FeedbackForm key={record.id} output={output} record={record} />
        </Panel>
        <div className="space-y-5">
          <Panel title="Final clinical decision">
            <DecisionPanel output={output} record={record} />
          </Panel>
          <Panel title="Review history (this session)">
            <ReviewHistory record={record} />
          </Panel>
        </div>
      </div>
    </div>
  )
}

export function ReviewPage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 4 · Practitioner review"
        title="Practitioner review"
        description="Review the whole case — screening, Ayurvedic reasoning, evidence and safety — and record structured feedback. AI output is never approved automatically."
      />
      <CaseBar />
      <WithReasoning>{(output, record) => <ReviewWorkspace output={output} record={record} />}</WithReasoning>
    </>
  )
}
