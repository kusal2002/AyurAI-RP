import * as React from "react"
import {
  Activity,
  AlertTriangle,
  Beaker,
  CheckCircle2,
  Layers,
  Network,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from "lucide-react"

import { CaseBar, WithReasoning } from "@/components/shared/case"
import { ScoreCaveat } from "@/components/shared/c2"
import { EmptyState, ErrorState, IdChip, LoadingState, Notice, PageHeader, Panel } from "@/components/shared/page"
import { StatusBadge, dispositionSpec, safetySpec, sufficiencySpec } from "@/components/shared/status"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useWorkspace, type CaseRecord } from "@/context/workspace"
import { component3Api } from "@/lib/api/component3"
import type {
  C2SafetyEvaluationRequest,
  Component2Output,
  SafetyAssessmentReport,
} from "@/lib/api/types"
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
import { SafetyKnowledgeGraph } from "./SafetyKnowledgeGraph"

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

function SafetyReportView({ report, record }: { report: SafetyAssessmentReport; record?: CaseRecord }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold text-slate-700">Overall Safety Classification:</span>
          <StatusBadge size="md" spec={safetySpec(report.overall_safety_tier)} />
        </div>
        <p className="text-xs text-slate-500">
          Assessment <IdChip>{report.assessment_id}</IdChip> · {formatDateTime(report.timestamp)} · Doctor review:{" "}
          <span className="font-semibold">{report.practitioner_review_required ? "Mandatory" : "Optional"}</span>
        </p>
      </div>

      {record?.c3Build && (record.c3Build.notes.length > 0 || record.c3Build.excluded.length > 0) && (
        <Notice tone="neutral" title="How Component 2 output was forwarded to Component 3">
          <ul className="list-disc pl-4 text-xs">
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
        A Low Risk classification means no configured rule, neural prediction, or organ contraindication matched the entered patient
        context. It is not an absolute proof of safety and requires clinical practitioner sign-off.
      </ScoreCaveat>
    </div>
  )
}

function SafetyWorkspace({ output, record }: { output: Component2Output; record: CaseRecord }) {
  const { runSafety } = useWorkspace()
  // The case's related candidates (top per category) are all pre-selected.
  const [selected, setSelected] = React.useState<string[]>(() =>
    output.candidates.filter((c) => c.name).map((candidate) => candidate.candidate_id),
  )
  const [form, setForm] = React.useState<PatientFormState>(() => ({
    ...emptyPatientForm,
    patientId: record.caseRef ? `PT-${record.caseRef}` : `PT-001`,
    age: "52",
    gender: "Female",
    egfr: "75",
    ckdStage: "Normal",
    medications: [
      { name: "Metformin", drug_class: "Biguanide Antidiabetic", dosage: "500 mg daily", route: "Oral" },
    ],
    comorbidities: "Mild Hypertension, Type 2 Diabetes",
  }))
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
      <Notice tone="caution" title="Safety Gate Boundary (Component 3)">
        Component 2 ranking identifies Ayurvedic efficacy candidates, but does not verify clinical safety. Component 3 dynamically evaluates candidates against patient-specific biomarkers and concurrent pharmaceuticals.
      </Notice>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Panel step={1} title="Candidates to assess" description="The patient's related candidates are pre-selected">
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
          <Notice tone="caution" className="mb-3">
            Clinical context parameters are sent directly to the Component 3 neural fusion service.
          </Notice>
          <div className="mb-3 flex flex-wrap items-center gap-1.5 p-2 rounded-lg bg-slate-50 border border-slate-200">
            <span className="text-[11px] font-semibold text-slate-600 mr-1">Quick Clinical Profiles:</span>
            <button
              type="button"
              onClick={() =>
                setForm({
                  ...emptyPatientForm,
                  patientId: record.caseRef ? `PT-${record.caseRef}` : `PT-001`,
                  age: "72",
                  gender: "Female",
                  egfr: "38",
                  ckdStage: "Stage G3b",
                  medications: [
                    { name: "Warfarin", drug_class: "Anticoagulant", dosage: "5 mg daily", route: "Oral" },
                    { name: "Metformin", drug_class: "Biguanide Antidiabetic", dosage: "500 mg BID", route: "Oral" },
                  ],
                  comorbidities: "Hypertension, CKD",
                })
              }
              className="px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-800 border border-rose-200 hover:bg-rose-100"
            >
              Elderly CKD on Warfarin
            </button>
            <button
              type="button"
              onClick={() =>
                setForm({
                  ...emptyPatientForm,
                  patientId: record.caseRef ? `PT-${record.caseRef}` : `PT-001`,
                  age: "48",
                  gender: "Female",
                  egfr: "75",
                  ckdStage: "Normal",
                  medications: [
                    { name: "Metformin", drug_class: "Biguanide Antidiabetic", dosage: "500 mg daily", route: "Oral" },
                  ],
                  comorbidities: "Type 2 Diabetes",
                })
              }
              className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
            >
              Standard Adult (Metformin)
            </button>
          </div>
          <PatientContextForm form={form} onChange={setForm} errors={errors} drugSuggestions={drugSuggestions} disabled={loading} />
          <div className="mt-5 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
            {Object.keys(errors).length > 0 && <span className="text-xs text-rose-700">Fix the highlighted fields.</span>}
            <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={submit} disabled={loading || selected.length === 0}>
              <ShieldCheck className="size-4 mr-1.5" /> Run Safety Assessment
            </Button>
          </div>
        </Panel>
      </div>

      <Panel step={3} title="Safety assessment result" description="Component 3 live clinical output">
        {record.c3.status === "idle" && (
          <EmptyState icon={ShieldCheck} title="No safety assessment yet" description="Select candidates, complete the patient context and run the assessment." />
        )}
        {record.c3.status === "loading" && <LoadingState label="Waiting for Component 3 safety service…" />}
        {record.c3.status === "error" && (
          <>
            <ErrorState title="Safety assessment unavailable" error={record.c3.error} />
            <p className="mt-3 text-xs text-slate-500">Ensure the Component 3 FastAPI backend is running on port 8003.</p>
          </>
        )}
        {record.c3.status === "success" && <SafetyReportView report={record.c3.data} record={record} />}
      </Panel>
    </div>
  )
}

// ==========================================
// CLINICAL PRESETS FOR LIVE PANEL DEMO
// ==========================================

type DemoPreset = {
  id: string
  title: string
  subtitle: string
  tierLabel: "HIGH RISK" | "CAUTION" | "LOW RISK"
  tierTone: "critical" | "warning" | "positive"
  payload: C2SafetyEvaluationRequest
}

const DEMO_PRESETS: DemoPreset[] = [
  {
    id: "elderly_ckd_warfarin",
    title: "1. Elderly CKD on Warfarin",
    subtitle: "Age 72 · eGFR 38 (Stage G3b) · Warfarin + Metformin + Amlodipine · Candidate: Punarnavadi Mandura & Haridra",
    tierLabel: "HIGH RISK",
    tierTone: "critical",
    payload: {
      candidate_package: {
        case_id: "CASE-DEMO-001",
        anemia_risk_tier: "Moderate",
        anemia_confidence: 0.88,
        ayurvedic_interpretation: "Vata-Pitta Pandu Roga with Shotha (Edema)",
        symptom_summary: ["Fatigue", "Pallor", "Bilateral pedal edema", "Dyspnea on exertion"],
        candidates: [
          {
            id: "REC-PANDU-001",
            name: "Punarnavadi Mandura",
            category: "Formulation",
            botanical_name: "Boerhavia diffusa + Iron Calx",
            dose: "2 tablets twice daily after meals",
            reasoning_score: 0.92,
            rationale: "Classical Rasayana for Pandu accompanied by Shotha (edema). Contains Punarnava, Mandura Bhasma, Trikatu, and Triphala.",
            evidence_ids: ["AH-Ci-16-15", "Bhavaprakasha-Pandu-45"],
          },
          {
            id: "REC-PANDU-002",
            name: "Haridra Churna",
            category: "Herb",
            botanical_name: "Curcuma longa",
            dose: "500 mg twice daily with warm milk",
            reasoning_score: 0.81,
            rationale: "Deepana and Pachana herb recommended for clearing Rakta Dhatu impurities.",
            evidence_ids: ["AYUSH-MONO-CURCUMA"],
          },
        ],
        metadata: { demo_mode: true },
      },
      patient_context: {
        patient_id: "PT-DEMO-72",
        age: 72,
        gender: "Female",
        pregnancy_status: false,
        pregnancy_trimester: null,
        lactation_status: false,
        current_medications: [
          { name: "Warfarin", drug_class: "Anticoagulant", dosage: "5 mg daily", route: "Oral" },
          { name: "Metformin", drug_class: "Biguanide Antidiabetic", dosage: "500 mg BID", route: "Oral" },
          { name: "Amlodipine", drug_class: "Calcium Channel Blocker", dosage: "5 mg daily", route: "Oral" },
        ],
        comorbidities: ["Hypertension", "Type 2 Diabetes Mellitus", "Chronic Kidney Disease"],
        allergies: [],
        organ_function: {
          egfr: 38.0,
          ckd_stage: "Stage G3b",
          hepatic_impairment: "None",
          serum_creatinine: 1.85,
        },
        polypharmacy: false,
      },
    },
  },
  {
    id: "pregnant_anemia",
    title: "2. Pregnant (2nd Trimester, Severe Anemia)",
    subtitle: "Age 29 · 22 weeks gestation · Severe Gestational Anemia · Candidate: Dhatri Avaleha & Kanchanara",
    tierLabel: "CAUTION",
    tierTone: "warning",
    payload: {
      candidate_package: {
        case_id: "CASE-DEMO-002",
        anemia_risk_tier: "High",
        anemia_confidence: 0.94,
        ayurvedic_interpretation: "Garbhini Pandu (Gestational Pittaja Pandu)",
        symptom_summary: ["Severe dizziness", "Glossitis", "Koilonychia", "Extreme exhaustion"],
        candidates: [
          {
            id: "REC-PANDU-003",
            name: "Dhatri Avaleha",
            category: "Formulation",
            botanical_name: "Emblica officinalis confection",
            dose: "10 g twice daily with milk",
            reasoning_score: 0.95,
            rationale: "Rich in bioavailable Vitamin C and iron co-factors, gentle on gastric mucosa, recommended during pregnancy.",
            evidence_ids: ["Charaka-Sharira-8-32", "AH-Uttara-3"],
          },
          {
            id: "REC-PANDU-004",
            name: "Kanchanara Guggulu",
            category: "Formulation",
            botanical_name: "Bauhinia variegata + Commiphora mukul",
            dose: "1 tablet twice daily",
            reasoning_score: 0.74,
            rationale: "Exploratory candidate for glandular sluggishness.",
            evidence_ids: ["Bhavaprakasha-Galaganda-22"],
          },
        ],
        metadata: { demo_mode: true },
      },
      patient_context: {
        patient_id: "PT-DEMO-PREG-29",
        age: 29,
        gender: "Female",
        pregnancy_status: true,
        pregnancy_trimester: 2,
        lactation_status: false,
        current_medications: [
          { name: "Ferrous Fumarate", drug_class: "Iron Supplement", dosage: "200 mg daily", route: "Oral" },
          { name: "Folic Acid", drug_class: "Vitamin B9", dosage: "5 mg daily", route: "Oral" },
        ],
        comorbidities: ["Gestational Anemia"],
        allergies: [],
        organ_function: {
          egfr: 115.0,
          ckd_stage: "Normal",
          hepatic_impairment: "None",
          serum_creatinine: 0.7,
        },
        polypharmacy: false,
      },
    },
  },
  {
    id: "uncomplicated_adult",
    title: "3. Uncomplicated Young Adult",
    subtitle: "Age 26 · Normal eGFR 118 · No pharmaceuticals · Candidate: Amalaki Rasayana",
    tierLabel: "LOW RISK",
    tierTone: "positive",
    payload: {
      candidate_package: {
        case_id: "CASE-DEMO-003",
        anemia_risk_tier: "Low",
        anemia_confidence: 0.75,
        ayurvedic_interpretation: "Kaphaja Pandu Roga (Mild Nutritional)",
        symptom_summary: ["Mild lassitude", "Cold sensitivity"],
        candidates: [
          {
            id: "REC-PANDU-005",
            name: "Amalaki Rasayana",
            category: "Herb",
            botanical_name: "Phyllanthus emblica",
            dose: "3 g morning with warm water",
            reasoning_score: 0.91,
            rationale: "Tridoshic Rasayana that optimizes iron assimilation without metabolic burden.",
            evidence_ids: ["Charaka-Ci-1-1"],
          },
        ],
        metadata: { demo_mode: true },
      },
      patient_context: {
        patient_id: "PT-DEMO-26",
        age: 26,
        gender: "Male",
        pregnancy_status: false,
        pregnancy_trimester: null,
        lactation_status: false,
        current_medications: [],
        comorbidities: [],
        allergies: [],
        organ_function: {
          egfr: 118.0,
          ckd_stage: "Normal",
          hepatic_impairment: "None",
          serum_creatinine: 0.85,
        },
        polypharmacy: false,
      },
    },
  },
]

// ==========================================
// CUSTOM REAL-WORLD PATIENT TESTER
// ==========================================

function CustomPatientTester({
  onEvaluate,
  loading,
}: {
  onEvaluate: (payload: C2SafetyEvaluationRequest) => void
  loading: boolean
}) {
  const [age, setAge] = React.useState("68")
  const [gender, setGender] = React.useState("Male")
  const [egfr, setEgfr] = React.useState("34")
  const [ckdStage, setCkdStage] = React.useState("Stage G3b")
  const [pregnant, setPregnant] = React.useState(false)
  const [selectedHerb, setSelectedHerb] = React.useState("Yashtimadhu")
  const [selectedDrugs, setSelectedDrugs] = React.useState<string[]>(["Losartan"])
  const [customDrug, setCustomDrug] = React.useState("")
  const [comorbidities, setComorbidities] = React.useState<string[]>(["Hypertension"])

  const commonDrugs = [
    "Warfarin",
    "Losartan",
    "Metformin",
    "Omeprazole",
    "Levothyroxine",
    "Atorvastatin",
    "Clonazepam",
    "Aspirin",
    "Amlodipine",
    "Digoxin",
  ]

  const commonHerbs = [
    "Punarnava",
    "Mandura Bhasma",
    "Yashtimadhu",
    "Ashwagandha",
    "Haridra",
    "Amalaki",
    "Guduchi",
    "Brahmi",
    "Triphala",
    "Shatavari",
  ]

  function toggleDrug(drug: string) {
    setSelectedDrugs((prev) =>
      prev.includes(drug) ? prev.filter((d) => d !== drug) : [...prev, drug]
    )
  }

  function addCustomDrug() {
    if (customDrug.trim() && !selectedDrugs.includes(customDrug.trim())) {
      setSelectedDrugs((prev) => [...prev, customDrug.trim()])
      setCustomDrug("")
    }
  }

  function toggleComorbidity(condition: string) {
    setComorbidities((prev) =>
      prev.includes(condition) ? prev.filter((c) => c !== condition) : [...prev, condition]
    )
  }

  function handleEvaluate() {
    const payload: C2SafetyEvaluationRequest = {
      candidate_package: {
        case_id: "CASE-REAL-" + Math.floor(Math.random() * 9000 + 1000),
        anemia_risk_tier: "Moderate",
        anemia_confidence: 0.88,
        ayurvedic_interpretation: "Pandu Roga Clinical Intake",
        symptom_summary: ["Fatigue", "Pallor", "Exertional dyspnea"],
        candidates: [
          {
            id: "REC-" + selectedHerb.toUpperCase().replace(/\s+/g, "-"),
            name: selectedHerb,
            category: "Herb / Formulation",
            botanical_name: selectedHerb,
            dose: "Standard therapeutic dose",
            reasoning_score: 0.9,
            rationale: `Selected Ayurvedic formulation candidate (${selectedHerb}) for clinical intake.`,
            evidence_ids: ["AYUSH-CLINICAL-MONO"],
          },
        ],
        metadata: { source: "custom_patient_tester" },
      },
      patient_context: {
        patient_id: "PT-REAL-" + Math.floor(Math.random() * 9000 + 1000),
        age: Number(age) || 50,
        gender,
        pregnancy_status: pregnant,
        pregnancy_trimester: pregnant ? 2 : null,
        lactation_status: false,
        current_medications: selectedDrugs.map((d) => ({
          name: d,
          drug_class: "Pharmaceutical",
          dosage: "Standard Rx",
          route: "Oral",
        })),
        comorbidities,
        allergies: [],
        organ_function: {
          egfr: egfr ? Number(egfr) : null,
          ckd_stage: ckdStage,
          hepatic_impairment: "None",
          serum_creatinine: null,
        },
        polypharmacy: selectedDrugs.length >= 5,
      },
    }
    onEvaluate(payload)
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-800">
            Real Patient Clinical Parameters
          </h3>
          <p className="text-xs text-slate-500">
            Enter genuine patient demographics, renal/hepatic biomarkers, and active allopathic prescriptions.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Age */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Patient Age (Years)</label>
          <input
            type="number"
            min="1"
            max="110"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium focus:border-emerald-600 focus:outline-none"
          />
        </div>

        {/* Gender */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Biological Sex</label>
          <select
            value={gender}
            onChange={(e) => {
              setGender(e.target.value)
              if (e.target.value !== "Female") setPregnant(false)
            }}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium focus:border-emerald-600 focus:outline-none bg-white"
          >
            <option value="Male">Male</option>
            <option value="Female">Female</option>
          </select>
          {gender === "Female" && (
            <label className="mt-1.5 flex items-center gap-1.5 text-[11px] font-medium text-slate-600">
              <input
                type="checkbox"
                checked={pregnant}
                onChange={(e) => setPregnant(e.target.checked)}
                className="rounded border-slate-300 text-emerald-600"
              />
              Pregnant (Trimester 2)
            </label>
          )}
        </div>

        {/* eGFR */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">eGFR (mL/min/1.73m²)</label>
          <input
            type="number"
            min="5"
            max="140"
            value={egfr}
            onChange={(e) => setEgfr(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium focus:border-emerald-600 focus:outline-none"
            placeholder="e.g. 35"
          />
        </div>

        {/* CKD Stage */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">CKD Stage</label>
          <select
            value={ckdStage}
            onChange={(e) => setCkdStage(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium focus:border-emerald-600 focus:outline-none bg-white"
          >
            <option value="Normal">Normal (eGFR &ge; 90)</option>
            <option value="Stage G1">Stage G1 (eGFR &ge; 90 with damage)</option>
            <option value="Stage G2">Stage G2 (eGFR 60–89)</option>
            <option value="Stage G3a">Stage G3a (eGFR 45–59)</option>
            <option value="Stage G3b">Stage G3b (eGFR 30–44)</option>
            <option value="Stage G4">Stage G4 (eGFR 15–29)</option>
            <option value="Stage G5">Stage G5 (Kidney Failure &lt; 15)</option>
          </select>
        </div>
      </div>

      {/* Candidate Ayurvedic Herb Selection */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          Candidate Ayurvedic Formulation to Assess
        </label>
        <div className="flex flex-wrap gap-1.5">
          {commonHerbs.map((herb) => (
            <button
              key={herb}
              type="button"
              onClick={() => setSelectedHerb(herb)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                selectedHerb === herb
                  ? "bg-emerald-700 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {herb}
            </button>
          ))}
        </div>
      </div>

      {/* Concurrent Pharmaceutical Medications */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          Active Co-Medications (Select from Verified Formulary or Type Custom)
        </label>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {commonDrugs.map((drug) => {
            const isChecked = selectedDrugs.includes(drug)
            return (
              <button
                key={drug}
                type="button"
                onClick={() => toggleDrug(drug)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  isChecked
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {isChecked ? "✓ " : "+ "}
                {drug}
              </button>
            )
          })}
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={customDrug}
            onChange={(e) => setCustomDrug(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomDrug())}
            placeholder="Type other drug name (e.g. Ciprofloxacin) and press Enter..."
            className="flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium focus:border-emerald-600 focus:outline-none"
          />
          <Button size="sm" variant="outline" type="button" onClick={addCustomDrug} className="text-xs">
            Add Drug
          </Button>
        </div>
        {selectedDrugs.length > 0 && (
          <p className="mt-1.5 text-[11px] text-slate-500">
            Selected active medications ({selectedDrugs.length}):{" "}
            <span className="font-semibold text-indigo-900">{selectedDrugs.join(", ")}</span>
          </p>
        )}
      </div>

      {/* Comorbidities */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">Comorbidities & Risk Factors</label>
        <div className="flex flex-wrap gap-1.5">
          {["Hypertension", "Chronic Kidney Disease", "Peptic Ulcer Disease", "Type 2 Diabetes", "Bradycardia"].map((cond) => {
            const isChecked = comorbidities.includes(cond)
            return (
              <button
                key={cond}
                type="button"
                onClick={() => toggleComorbidity(cond)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  isChecked
                    ? "bg-rose-700 text-white shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {isChecked ? "✓ " : "+ "}
                {cond}
              </button>
            )
          })}
        </div>
      </div>

      {/* Run Evaluation Button */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
        <p className="text-[11px] text-slate-500">
          Calls FastAPI <code>POST /api/v1/c2/safety-evaluation</code> with live neural context fusion.
        </p>
        <Button
          type="button"
          onClick={handleEvaluate}
          disabled={loading}
          className="bg-emerald-700 hover:bg-emerald-800 text-white"
        >
          <ShieldCheck className="size-4 mr-1.5" />
          {loading ? "Evaluating Neural Model…" : "Evaluate Real Patient Safety"}
        </Button>
      </div>
    </div>
  )
}

function ClinicalDemonstrationSandbox() {
  const [sandboxMode, setSandboxMode] = React.useState<"presets" | "custom">("presets")
  const [activePresetId, setActivePresetId] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [report, setReport] = React.useState<SafetyAssessmentReport | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  async function evaluatePayload(payload: C2SafetyEvaluationRequest) {
    setLoading(true)
    setError(null)
    try {
      const response = await component3Api.evaluate(payload)
      setReport(response)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run safety evaluation against FastAPI (port 8003)")
    } finally {
      setLoading(false)
    }
  }

  function runPreset(preset: DemoPreset) {
    setActivePresetId(preset.id)
    evaluatePayload(preset.payload)
  }

  return (
    <div className="rounded-2xl border-2 border-emerald-500/20 bg-gradient-to-br from-emerald-50/40 via-white to-slate-50 p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-700 text-white shadow-xs">
              <Stethoscope className="size-4" />
            </span>
            <h2 className="text-base font-bold text-slate-900">
              Clinical Demonstration & Real Data Testing Sandbox
            </h2>
          </div>
          <p className="mt-1 text-xs text-slate-600">
            Evaluate candidate Ayurvedic formulations against patient-specific biomarkers and active pharmaceutical medications.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Sub-mode toggle */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            <button
              type="button"
              onClick={() => setSandboxMode("presets")}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                sandboxMode === "presets"
                  ? "bg-emerald-700 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              ⚡ 1-Click Clinical Cohorts
            </button>
            <button
              type="button"
              onClick={() => setSandboxMode("custom")}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                sandboxMode === "custom"
                  ? "bg-emerald-700 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              🔬 Test Custom Real Patient Data
            </button>
          </div>

          {report && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setReport(null)
                setActivePresetId(null)
              }}
              className="text-xs text-slate-600"
            >
              <RotateCcw className="size-3.5 mr-1" /> Reset
            </Button>
          )}
        </div>
      </div>

      {/* Sub-mode 1: 1-Click Presets */}
      {sandboxMode === "presets" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {DEMO_PRESETS.map((preset) => {
            const isSelected = activePresetId === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => runPreset(preset)}
                disabled={loading}
                className={`text-left p-4 rounded-xl border transition-all duration-150 ${
                  isSelected
                    ? "border-emerald-600 bg-white ring-2 ring-emerald-600/20 shadow-md"
                    : "border-slate-200 bg-white/90 hover:border-emerald-300 hover:bg-emerald-50/30 shadow-xs"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-bold text-slate-900">{preset.title}</span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      preset.tierLabel === "HIGH RISK"
                        ? "bg-rose-100 text-rose-800"
                        : preset.tierLabel === "CAUTION"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-emerald-100 text-emerald-800"
                    }`}
                  >
                    {preset.tierLabel}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 leading-relaxed">{preset.subtitle}</p>
                <div className="mt-3 flex items-center justify-between text-[11px] font-semibold text-emerald-700">
                  <span>{isSelected && loading ? "Evaluating neural model…" : "Simulate Case →"}</span>
                  <Play className={`size-3 ${isSelected ? "fill-emerald-700" : ""}`} />
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Sub-mode 2: Custom Real Patient Input */}
      {sandboxMode === "custom" && (
        <CustomPatientTester onEvaluate={evaluatePayload} loading={loading} />
      )}

      {/* Sandbox Evaluation Output */}
      {loading && (
        <div className="mt-5 p-8 rounded-xl bg-white border border-slate-200 text-center">
          <LoadingState label="Running Graph GAT + Context Fusion Layer (M4) on Port 8003…" />
        </div>
      )}

      {error && (
        <div className="mt-5 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
          <p className="font-semibold flex items-center gap-1.5 mb-1">
            <AlertTriangle className="size-4 text-rose-600" /> Evaluation Error
          </p>
          <p>{error}</p>
          <p className="mt-1 text-slate-500">Make sure FastAPI is active: <code>uvicorn app.main:app --port 8003</code></p>
        </div>
      )}

      {report && !loading && (
        <div className="mt-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
            <CheckCircle2 className="size-4 text-emerald-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Real-Time Clinical Safety Gate Assessment (Live API Response)
            </h3>
          </div>
          <SafetyReportView report={report} />
        </div>
      )}
    </div>
  )
}

// ==========================================
// MAIN SAFETY PAGE
// ==========================================

export function SafetyPage() {
  const { activeCase } = useWorkspace()
  const [activeTab, setActiveTab] = React.useState<"pipeline" | "graph" | "sandbox" | "ablation" | "reference">("pipeline")

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Component 3 · Clinical Safety Gate"
        title="Patient-Context-Aware Herb–Drug Safety Prediction"
        description="Evaluates candidate Ayurvedic formulations against patient-specific biomarkers (eGFR, CKD stage, age, polypharmacy) and pharmaceutical co-medications using Neo4j Knowledge Graphs and Neural Context Fusion (M4)."
      />

      {activeCase?.c2.status === "success" && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 shadow-xs">
          <div className="flex items-center gap-2.5">
            <span className="flex size-6 items-center justify-center rounded-full bg-emerald-700 text-white text-xs font-bold">✓</span>
            <div>
              <p className="text-xs font-bold text-emerald-950">
                Active Case Loaded: <code className="bg-emerald-100 px-1 py-0.5 rounded text-emerald-950 font-mono">{activeCase.caseRef}</code>
              </p>
              <p className="text-[11px] text-emerald-800">
                {activeCase.c2.data.candidates.length} related candidate(s) from Component 2 are ready for Component 3 safety evaluation.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => setActiveTab("pipeline")}
            className="text-xs bg-emerald-700 hover:bg-emerald-800 text-white"
          >
            Review Active Case Safety →
          </Button>
        </div>
      )}

      {/* Tab Selector */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          type="button"
          onClick={() => setActiveTab("pipeline")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "pipeline"
              ? "bg-emerald-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <Activity className="size-3.5" /> Active Patient Safety Gate (C1 → C2 → C3)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("graph")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "graph"
              ? "bg-emerald-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <Network className="size-3.5" /> Safety Knowledge Graph
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("sandbox")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "sandbox"
              ? "bg-emerald-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <Sparkles className="size-3.5" /> Clinical Presets & Real Data Sandbox
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("ablation")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "ablation"
              ? "bg-indigo-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <Layers className="size-3.5" /> Model Ablation Benchmark Suite (M1–M4)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("reference")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "reference"
              ? "bg-emerald-700 text-white shadow-xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          <Beaker className="size-3.5" /> Safety Knowledge Base & Datasets
        </button>
      </div>

      {/* Tab: Safety Knowledge Graph */}
      {activeTab === "graph" && (
        <section className="space-y-6">
          <SafetyKnowledgeGraph />
        </section>
      )}

      {/* Tab 1: Active Workspace Pipeline */}
      {activeTab === "pipeline" && (
        <section className="space-y-6">
          <CaseBar />
          <WithReasoning>
            {(output, record) => <SafetyWorkspace key={record.id} output={output} record={record} />}
          </WithReasoning>
        </section>
      )}

      {/* Tab 2: Live Demonstration Sandbox */}
      {activeTab === "sandbox" && (
        <section className="space-y-6">
          <ClinicalDemonstrationSandbox />
        </section>
      )}

      {/* Tab 3: Model Ablation Widget */}
      {activeTab === "ablation" && (
        <section className="space-y-6">
          <ModelAblationWidget />
        </section>
      )}

      {/* Tab 4: Reference Data */}
      {activeTab === "reference" && (
        <section className="space-y-6">
          <ReferenceData />
        </section>
      )}
    </div>
  )
}

export default SafetyPage
