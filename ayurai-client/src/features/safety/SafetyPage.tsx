import * as React from "react"
import { BarChart3, ShieldCheck, Sparkles } from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ScoreCaveat } from "@/components/shared/c2"
import { EmptyState, ErrorState, IdChip, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, dispositionSpec, safetySpec, sufficiencySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { component3Api } from "@/lib/api/component3"
import type { Component2Output, SafetyAssessmentReport } from "@/lib/api/types"
import { formatDateTime } from "@/lib/labels"
import {
  PatientContextForm,
  emptyPatientForm,
  validatePatientForm,
  type PatientFormState,
} from "./PatientContextForm"
import { ReferenceData } from "./ReferenceData"
import { SafetyGateCard } from "./SafetyGateCard"
import { ModelAblationWidget } from "./ModelAblationWidget"

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

function SafetyReportView({ report, record }: { report: SafetyAssessmentReport; record: CaseRecord }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold text-slate-700">Overall Safety Assessment</span>
          <StatusBadge size="md" spec={safetySpec(report.overall_safety_tier)} />
        </div>
        <p className="text-xs text-slate-500">
          Assessment <IdChip>{report.assessment_id}</IdChip> · {formatDateTime(report.timestamp)} · Practitioner Review Required:{" "}
          <strong className="text-slate-800">{report.practitioner_review_required ? "YES" : "NO"}</strong>
        </p>
      </div>

      {record.c3Build && (record.c3Build.notes.length > 0 || record.c3Build.excluded.length > 0) && (
        <Notice tone="neutral" title="Component 2 -> Component 3 Ingestion Pipeline">
          <ul className="list-disc pl-4 text-xs space-y-1">
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
        <div className="space-y-4">
          {report.evaluations.map((evaluation) => (
            <SafetyGateCard key={evaluation.candidate_id} evaluation={evaluation} />
          ))}
        </div>
      )}

      <ScoreCaveat>
        A Low Risk classification indicates no configured deterministic rule, latent GAT link, or patient vulnerability contraindication matched the entered patient context.
      </ScoreCaveat>
    </div>
  )
}

function SafetyWorkspace({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const { runSafety } = useWorkspace()
  const isDemo = record.source === "demo"
  const forwarded = output.candidates.filter((candidate) => candidate.disposition === "forward_for_safety_assessment")
  const [selected, setSelected] = React.useState<string[]>(() => forwarded.map((candidate) => candidate.candidate_id))
  const [form, setForm] = React.useState<PatientFormState>(
    isDemo
      ? { ...emptyPatientForm, patientId: "DEMO-PT-001", age: "40", gender: "Other", medications: [{ name: "Demo Drug X", drug_class: "", dosage: "" }] }
      : emptyPatientForm,
  )
  const [errors, setErrors] = React.useState<ReturnType<typeof validatePatientForm>["errors"]>({})
  const drugSuggestions = useDrugSuggestions(!isDemo)
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
      <Notice tone="caution" title="Component 3: Patient-Context-Aware Clinical Safety Gate">
        Component 2 ranking reflects Ayurvedic suitability only. Component 3 dynamically fuses the patient's organ functions, vulnerabilities, and concurrent medications with the knowledge graph to evaluate biological safety.
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
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50 transition-colors">
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
          {/* Quick-Load Clinical Presets for Demonstration */}
          <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-emerald-600" /> Demonstration Clinical Presets (1-Click Fill)
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  setForm({
                    patientId: "CASE-CKD-042",
                    age: "68",
                    gender: "Female",
                    pregnant: false,
                    trimester: "",
                    lactating: false,
                    egfr: "38",
                    ckdStage: "Stage G3b",
                    creatinine: "1.45",
                    hepatic: "None",
                    comorbidities: "Hypertension, Chronic Kidney Disease Stage 3b, Type 2 Diabetes",
                    allergies: "Penicillin",
                    medications: [
                      { name: "Warfarin", drug_class: "Anticoagulant", dosage: "5 mg QD" },
                      { name: "Metformin", drug_class: "Biguanide", dosage: "500 mg BID" },
                      { name: "Amlodipine", drug_class: "CCB", dosage: "5 mg QD" },
                    ],
                  })
                }
                className="text-[11px] font-semibold bg-white border border-slate-200 rounded px-2.5 py-1 text-slate-700 hover:bg-slate-100 transition-colors shadow-2xs"
              >
                1. Elderly CKD on Warfarin (High Risk)
              </button>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    patientId: "CASE-PREG-019",
                    age: "27",
                    gender: "Female",
                    pregnant: true,
                    trimester: "2",
                    lactating: false,
                    egfr: "115",
                    ckdStage: "Normal",
                    creatinine: "0.7",
                    hepatic: "None",
                    comorbidities: "Gestational Anemia",
                    allergies: "",
                    medications: [
                      { name: "Ferrous Sulfate", drug_class: "Iron Supplement", dosage: "200 mg QD" },
                    ],
                  })
                }
                className="text-[11px] font-semibold bg-white border border-slate-200 rounded px-2.5 py-1 text-slate-700 hover:bg-slate-100 transition-colors shadow-2xs"
              >
                2. Pregnant 2nd Trimester (Contraindication Check)
              </button>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    patientId: "CASE-NORM-008",
                    age: "35",
                    gender: "Male",
                    pregnant: false,
                    trimester: "",
                    lactating: false,
                    egfr: "105",
                    ckdStage: "Normal",
                    creatinine: "0.85",
                    hepatic: "None",
                    comorbidities: "",
                    allergies: "",
                    medications: [],
                  })
                }
                className="text-[11px] font-semibold bg-white border border-slate-200 rounded px-2.5 py-1 text-slate-700 hover:bg-slate-100 transition-colors shadow-2xs"
              >
                3. Uncomplicated Adult (Safe Profile)
              </button>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    patientId: "CASE-NEW-BRAHMI",
                    age: "58",
                    gender: "Male",
                    pregnant: false,
                    trimester: "",
                    lactating: false,
                    egfr: "68",
                    ckdStage: "Stage G2",
                    creatinine: "1.10",
                    hepatic: "None",
                    comorbidities: "GERD / Gastritis, Anemic Fatigue",
                    allergies: "",
                    medications: [
                      { name: "Omeprazole", drug_class: "Proton Pump Inhibitor", dosage: "20 mg QD" },
                    ],
                  })
                }
                className="text-[11px] font-semibold bg-emerald-50 border border-emerald-200 rounded px-2.5 py-1 text-emerald-800 hover:bg-emerald-100 transition-colors shadow-2xs"
              >
                4. Brand New Herb: Brahmi on Omeprazole (CYP2C19 Discovery)
              </button>
            </div>
          </div>

          <PatientContextForm form={form} onChange={setForm} errors={errors} drugSuggestions={drugSuggestions} disabled={loading} />
          <div className="mt-5 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
            {Object.keys(errors).length > 0 && <span className="text-xs text-rose-700">Fix the highlighted fields.</span>}
            <Button className="bg-emerald-700 hover:bg-emerald-800 text-white font-semibold" onClick={submit} disabled={loading || selected.length === 0}>
              <ShieldCheck /> {isDemo ? "Show demo safety report" : "Run Safety Assessment"}
            </Button>
          </div>
        </Panel>
      </div>

      <Panel step={3} title="Safety assessment result" description="Component 3 output, evaluated in real time">
        {record.c3.status === "idle" && (
          <EmptyState icon={ShieldCheck} title="No safety assessment yet" description="Select candidates, complete the patient context and run the assessment." />
        )}
        {record.c3.status === "loading" && <LoadingState label="Evaluating multi-hop pathways and context fusion network…" />}
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
  const { mode } = useWorkspace()
  const [activeView, setActiveView] = React.useState<"evaluation" | "ablation">("evaluation")

  return (
    <>
      <PageHeader
        eyebrow="Component 3 · Clinical Safety Gate"
        title="Safety Assessment & Decision Support"
        description="Patient-context-aware Ayurvedic herb-drug interaction prediction, biological contraindications, and personalized titration directives."
      />

      {/* Top Navigation Tabs */}
      <div className="mb-4 flex items-center justify-between border-b border-slate-200">
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => setActiveView("evaluation")}
            className={`pb-3 px-1 text-sm font-bold flex items-center gap-2 border-b-2 transition-colors ${
              activeView === "evaluation"
                ? "border-emerald-700 text-emerald-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <ShieldCheck className="size-4 text-emerald-600" /> Clinical Safety Gate Assessment
          </button>
          <button
            type="button"
            onClick={() => setActiveView("ablation")}
            className={`pb-3 px-1 text-sm font-bold flex items-center gap-2 border-b-2 transition-colors ${
              activeView === "ablation"
                ? "border-emerald-700 text-emerald-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <BarChart3 className="size-4 text-indigo-600" /> Empirical Model Ablation (M1–M4 Chapter 5)
          </button>
        </div>
      </div>

      {activeView === "evaluation" ? (
        <>
          <CaseBar />
          <WithReasoning>{(output, record) => <SafetyWorkspace key={record.id} output={output} record={record} />}</WithReasoning>
          <div className="mt-6">
            <ReferenceData enabled={mode === "live"} />
          </div>
        </>
      ) : (
        <div className="space-y-6">
          <ModelAblationWidget />
          <div className="mt-6">
            <ReferenceData enabled={mode === "live"} />
          </div>
        </div>
      )}
    </>
  )
}

