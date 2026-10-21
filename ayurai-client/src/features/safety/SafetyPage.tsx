import * as React from "react"
import { AlertTriangle, ShieldCheck, Siren } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ScoreCaveat } from "@/components/shared/c2"
import { EmptyState, ErrorState, IdChip, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, dispositionSpec, safetySpec, sufficiencySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { component3Api } from "@/lib/api/component3"
import type { Component2Output, EvaluatedCandidateSafety, SafetyAssessmentReport } from "@/lib/api/types"
import { formatDateTime, formatScore } from "@/lib/labels"
import {
  PatientContextForm,
  emptyPatientForm,
  validatePatientForm,
  type PatientFormState,
} from "./PatientContextForm"
import { ReferenceData } from "./ReferenceData"

function useDrugSuggestions(enabled: boolean) {
  const [names, setNames] = React.useState<string[]>([])
  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    component3Api
      .drugs(controller.signal)
      .then((drugs) => setNames(drugs.map((drug) => drug.generic_name)))
      .catch(() => setNames([]))
    return () => controller.abort()
  }, [enabled])
  return names
}

function EvaluationCard({ evaluation }: { evaluation: EvaluatedCandidateSafety }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 p-4">
        <div>
          <p className="font-semibold text-slate-900">{evaluation.candidate_name}</p>
          <IdChip>{evaluation.candidate_id}</IdChip>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge size="md" spec={safetySpec(evaluation.safety_tier)} />
          {evaluation.escalate_to_practitioner && (
            <StatusBadge spec={{ label: "Escalate to practitioner", tone: "critical", icon: Siren }} />
          )}
        </div>
      </header>
      <div className="space-y-4 p-4">
        <p className="text-sm text-slate-700">{evaluation.summary_warning}</p>
        <p className="text-[11px] text-slate-500">
          Component 3 classification confidence: {formatScore(evaluation.confidence)} (as reported by the service; not
          clinically validated).
        </p>

        <section>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Interaction findings ({evaluation.interaction_findings.length})
          </h4>
          {evaluation.interaction_findings.length === 0 ? (
            <p className="text-xs text-slate-500">
              No interaction rule or prediction matched. This does not establish safety; it only means none of the
              configured rules matched the entered medications.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-xs">
                <thead>
                  <tr className="text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                    <th className="py-2 pr-3">Herb / constituent</th>
                    <th className="py-2 pr-3">Drug</th>
                    <th className="py-2 pr-3">Finding type</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2 pr-3">Mechanism</th>
                    <th className="py-2 pr-3">Evidence</th>
                    <th className="py-2">Sources</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {evaluation.interaction_findings.map((finding, index) => (
                    <tr key={index} className="align-top text-slate-700">
                      <td className="py-2 pr-3">{finding.herb_or_constituent}</td>
                      <td className="py-2 pr-3 font-medium">{finding.target_drug}</td>
                      <td className="py-2 pr-3">{finding.interaction_type}</td>
                      <td className="py-2 pr-3">{finding.severity}</td>
                      <td className="py-2 pr-3">{finding.mechanism}</td>
                      <td className="py-2 pr-3">
                        {finding.evidence_strength}
                        <br />
                        <span className="text-slate-500">score {formatScore(finding.prediction_confidence)}</span>
                      </td>
                      <td className="py-2">
                        {finding.source_refs.length === 0
                          ? "—"
                          : finding.source_refs.map((ref) => (
                              <span key={ref.source_id} className="block">
                                {ref.source_title}
                                {ref.pmid_or_ref ? ` (${ref.pmid_or_ref})` : ""} · {ref.citation_type}
                              </span>
                            ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <section>
            <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Contraindications triggered</h4>
            {evaluation.contraindications_triggered.length === 0 ? (
              <p className="text-xs text-slate-500">None triggered by the configured rules.</p>
            ) : (
              <ul className="space-y-1.5">
                {evaluation.contraindications_triggered.map((item) => (
                  <li key={item} className="flex gap-2 text-sm text-rose-800">
                    <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" /> {item}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section>
            <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Patient risk modifiers</h4>
            {evaluation.patient_risk_modifiers.length === 0 ? (
              <p className="text-xs text-slate-500">None reported.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {evaluation.patient_risk_modifiers.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {(evaluation.titration_plan || evaluation.surveillance) && (
          <details className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
            <summary className="cursor-pointer text-xs font-semibold text-amber-900">
              Guidance text generated by Component 3 (requires practitioner judgement)
            </summary>
            <p className="mt-2 text-xs text-amber-900">
              Shown exactly as returned by the safety service. It is rule-generated text, not a prescription or a
              validated treatment instruction.
            </p>
            <dl className="mt-2 space-y-1.5 text-xs text-slate-700">
              {evaluation.titration_plan?.recommended_dose_adjustment && (
                <div><dt className="font-semibold">Dose adjustment text</dt><dd>{evaluation.titration_plan.recommended_dose_adjustment}</dd></div>
              )}
              {evaluation.titration_plan?.separation_window && (
                <div><dt className="font-semibold">Separation window</dt><dd>{evaluation.titration_plan.separation_window}</dd></div>
              )}
              {evaluation.titration_plan?.duration_limit && (
                <div><dt className="font-semibold">Duration limit</dt><dd>{evaluation.titration_plan.duration_limit}</dd></div>
              )}
              {evaluation.surveillance && evaluation.surveillance.lab_monitoring.length > 0 && (
                <div><dt className="font-semibold">Lab monitoring</dt><dd>{evaluation.surveillance.lab_monitoring.join("; ")}</dd></div>
              )}
              {evaluation.surveillance && evaluation.surveillance.clinical_signs_to_watch.length > 0 && (
                <div><dt className="font-semibold">Signs to watch</dt><dd>{evaluation.surveillance.clinical_signs_to_watch.join("; ")}</dd></div>
              )}
            </dl>
          </details>
        )}
      </div>
    </article>
  )
}

function SafetyReportView({ report, record }: { report: SafetyAssessmentReport; record: CaseRecord }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-slate-600">Overall safety classification</span>
          <StatusBadge size="md" spec={safetySpec(report.overall_safety_tier)} />
        </div>
        <p className="text-xs text-slate-500">
          Assessment <IdChip>{report.assessment_id}</IdChip> · {formatDateTime(report.timestamp)} · practitioner review required:{" "}
          {report.practitioner_review_required ? "yes" : "no"}
        </p>
      </div>
      {record.c3Build && (record.c3Build.notes.length > 0 || record.c3Build.excluded.length > 0) && (
        <Notice tone="neutral" title="How the Component 2 output was sent to Component 3">
          <ul className="list-disc pl-4">
            {record.c3Build.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
            {record.c3Build.excluded.map((item) => (
              <li key={item.candidateId}>
                Excluded <code>{item.candidateId}</code>: {item.reason}
              </li>
            ))}
          </ul>
        </Notice>
      )}
      {report.evaluations.length === 0 ? (
        <EmptyState title="No candidate evaluations returned" />
      ) : (
        report.evaluations.map((evaluation) => <EvaluationCard key={evaluation.candidate_id} evaluation={evaluation} />)
      )}
      <ScoreCaveat>
        A Low Risk classification means no configured rule, prediction or contraindication matched the entered patient
        context. It is not proof of safety and does not approve a candidate.
      </ScoreCaveat>
    </div>
  )
}

function SafetyWorkspace({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const { runSafety } = useWorkspace()
  const forwarded = output.candidates.filter((candidate) => candidate.disposition === "forward_for_safety_assessment")
  const [selected, setSelected] = React.useState<string[]>(() => forwarded.map((candidate) => candidate.candidate_id))
  const [form, setForm] = React.useState<PatientFormState>(emptyPatientForm)
  const [errors, setErrors] = React.useState<ReturnType<typeof validatePatientForm>["errors"]>({})
  const drugSuggestions = useDrugSuggestions(true)
  const loading = record.c3.status === "loading"

  function toggle(id: string, checked: boolean) {
    setSelected((current) => (checked ? [...current, id] : current.filter((value) => value !== id)))
  }

  function submit() {
    const result = validatePatientForm(form)
    setErrors(result.errors)
    if (!result.context || selected.length === 0) return
    void runSafety(record.id, result.context, selected)
  }

  return (
    <div className="space-y-5">
      <Notice tone="caution" title="Safety gate">
        Component 2 ranking does not mean a candidate is safe or approved. Component 3 checks the selected candidates
        against the patient context; a practitioner must still review every result.
      </Notice>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Panel step={1} title="Candidates to assess" description="Forwarded candidates are pre-selected">
          {output.candidates.length === 0 ? (
            <EmptyState title="No candidates to assess" description="Component 2 produced no candidates for this case." />
          ) : (
            <ul className="space-y-2">
              {output.candidates.map((candidate) => {
                const checked = selected.includes(candidate.candidate_id)
                const withheld = candidate.disposition !== "forward_for_safety_assessment"
                return (
                  <li key={candidate.candidate_id}>
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(value) => toggle(candidate.candidate_id, value === true)}
                        disabled={loading}
                        className="mt-0.5"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold text-slate-800">
                          #{candidate.rank} {candidate.name ?? candidate.candidate_id}
                        </span>
                        <span className="mt-1 flex flex-wrap gap-1.5">
                          <StatusBadge spec={dispositionSpec(candidate.disposition)} />
                          <StatusBadge spec={sufficiencySpec(candidate.sufficiency.status)} />
                        </span>
                        {withheld && checked && (
                          <span className="mt-1 block text-xs text-amber-800">
                            Withheld by Component 2 — included for exploratory safety screening only.
                          </span>
                        )}
                        {!candidate.name && (
                          <span className="mt-1 block text-xs text-amber-800">
                            No display name: Component 3 cannot match rules for this candidate, so it will be excluded.
                          </span>
                        )}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          )}
          {selected.length === 0 && output.candidates.length > 0 && (
            <p className="mt-2 text-xs text-rose-700">Select at least one candidate.</p>
          )}
        </Panel>

        <Panel step={2} title="Patient context" description="Required by the Component 3 safety service">
          <Notice tone="caution" className="mb-4">
            This information is sent to the Component 3 service. Use synthetic or de-identified research data only.
            It is held in this page's memory and is not stored by the interface.
          </Notice>
          <PatientContextForm form={form} onChange={setForm} errors={errors} drugSuggestions={drugSuggestions} disabled={loading} />
          <div className="mt-5 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
            {Object.keys(errors).length > 0 && <span className="text-xs text-rose-700">Fix the highlighted fields.</span>}
            <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={submit} disabled={loading || selected.length === 0}>
              <ShieldCheck /> Run safety assessment
            </Button>
          </div>
        </Panel>
      </div>

      <Panel step={3} title="Safety assessment result" description="Component 3 output, shown as returned">
        {record.c3.status === "idle" && (
          <EmptyState icon={ShieldCheck} title="No safety assessment yet" description="Select candidates, complete the patient context and run the assessment." />
        )}
        {record.c3.status === "loading" && <LoadingState label="Waiting for the Component 3 safety service…" />}
        {record.c3.status === "error" && (
          <>
            <ErrorState title="Safety assessment unavailable" error={record.c3.error} />
            {record.c3Build && record.c3Build.excluded.length > 0 && (
              <ul className="mt-3 list-disc pl-5 text-xs text-slate-600">
                {record.c3Build.excluded.map((item) => (
                  <li key={item.candidateId}>
                    <code>{item.candidateId}</code>: {item.reason}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-slate-500">No safety classification is shown because the service did not return one.</p>
          </>
        )}
        {record.c3.status === "success" && <SafetyReportView report={record.c3.data} record={record} />}
      </Panel>
    </div>
  )
}

export function SafetyPage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 3 · Safety"
        title="Safety assessment"
        description="Herb–drug and herb–herb interactions, contraindications and patient-context risk modifiers for candidates produced by Component 2."
      />
      <CaseBar />
      <WithReasoning>{(output, record) => <SafetyWorkspace key={record.id} output={output} record={record} />}</WithReasoning>
      <div className="mt-6">
        <ReferenceData />
      </div>
    </>
  )
}
