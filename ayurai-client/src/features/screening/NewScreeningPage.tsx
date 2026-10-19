import * as React from "react"
import { useNavigate } from "react-router"
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileUp,
  Leaf,
  ListChecks,
  UserRound,
  X,
} from "lucide-react"

import { Notice, PageHeader, Panel, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useWorkspace, type ModalityKey } from "@/context/workspace"
import type { RiskTier } from "@/lib/api/types"
import { cn } from "@/lib/utils"

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/
const SYMPTOM_ID_PATTERN = /^[^\s,]{1,128}$/
const MAX_IMAGE_BYTES = 15 * 1024 * 1024

const modalities: {
  key: ModalityKey
  title: string
  description: string
  accept: string
}[] = [
  { key: "conjunctiva", title: "Conjunctiva / eye image", description: "JPG, PNG or WebP", accept: "image/jpeg,image/png,image/webp" },
  { key: "tongue", title: "Tongue image", description: "JPG, PNG or WebP", accept: "image/jpeg,image/png,image/webp" },
  { key: "nail", title: "Nail image", description: "JPG, PNG or WebP", accept: "image/jpeg,image/png,image/webp" },
  { key: "ppg", title: "PPG signal file", description: "CSV, JSON or TXT", accept: ".csv,.json,.txt,text/csv,application/json,text/plain" },
]

const questionnaire = [
  { key: "fatigue", label: "Unusual fatigue", options: ["not-answered", "yes", "no"] },
  { key: "dizziness", label: "Dizziness", options: ["not-answered", "yes", "no"] },
  { key: "breathlessness", label: "Breathlessness on exertion", options: ["not-answered", "yes", "no"] },
  { key: "diet", label: "Dietary context", options: ["not-answered", "mixed", "vegetarian", "other"] },
]

const optionLabel = (value: string) =>
  value === "not-answered" ? "Not answered" : value.charAt(0).toUpperCase() + value.slice(1)

const sexLabels: Record<string, string> = {
  "not-provided": "Not provided",
  female: "Female",
  male: "Male",
  other: "Other / prefer to describe",
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function parseSymptomIds(raw: string) {
  const ids = Array.from(
    new Set(
      raw
        .split(/[\s,]+/)
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  )
  const invalid = ids.filter((id) => !SYMPTOM_ID_PATTERN.test(id))
  return { ids, invalid }
}

const steps = [
  { number: 1, label: "Case context", icon: UserRound },
  { number: 2, label: "Screening inputs", icon: Activity },
  { number: 3, label: "Component 1 result", icon: ListChecks },
  { number: 4, label: "Review & run", icon: ClipboardList },
]

export function NewScreeningPage() {
  const navigate = useNavigate()
  const { mode, createCase, runReasoning, validateIntake } = useWorkspace()
  const isDemo = mode === "demo"

  const [step, setStep] = React.useState(1)
  const [caseRef, setCaseRef] = React.useState(isDemo ? "DEMO-CASE-002" : "")
  const [ageGroup, setAgeGroup] = React.useState("")
  const [sexAtBirth, setSexAtBirth] = React.useState("not-provided")
  const [files, setFiles] = React.useState<Partial<Record<ModalityKey, File>>>({})
  const [fileErrors, setFileErrors] = React.useState<Partial<Record<ModalityKey, string>>>({})
  const [answers, setAnswers] = React.useState<Record<string, string>>(
    Object.fromEntries(questionnaire.map((question) => [question.key, "not-answered"])),
  )
  const [riskTier, setRiskTier] = React.useState<RiskTier | "">("")
  const [confidence, setConfidence] = React.useState("")
  const [symptomRaw, setSymptomRaw] = React.useState("")
  const [validateFirst, setValidateFirst] = React.useState(true)
  const [submitting, setSubmitting] = React.useState(false)
  const [touched, setTouched] = React.useState(false)

  const caseRefValid = ID_PATTERN.test(caseRef.trim())
  const confidenceValue = Number(confidence)
  const confidenceValid = confidence.trim() !== "" && Number.isFinite(confidenceValue) && confidenceValue >= 0 && confidenceValue <= 1
  const { ids: symptomIds, invalid: invalidSymptoms } = parseSymptomIds(symptomRaw)
  const symptomsValid = symptomIds.length >= 1 && symptomIds.length <= 50 && invalidSymptoms.length === 0
  const c1Valid = riskTier !== "" && confidenceValid && symptomsValid
  const selectedCount = Object.keys(files).length

  const stepValid = step === 1 ? caseRefValid : step === 3 ? c1Valid : true

  function selectFile(key: ModalityKey, file: File | null) {
    setFileErrors((current) => ({ ...current, [key]: undefined }))
    if (!file) return
    if (key !== "ppg" && file.size > MAX_IMAGE_BYTES) {
      setFileErrors((current) => ({ ...current, [key]: `File is larger than ${formatBytes(MAX_IMAGE_BYTES)}.` }))
      return
    }
    setFiles((current) => ({ ...current, [key]: file }))
  }

  function removeFile(key: ModalityKey) {
    setFiles((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  function next() {
    setTouched(true)
    if (!stepValid) return
    setTouched(false)
    setStep((current) => Math.min(4, current + 1))
  }

  function submit() {
    if (!caseRefValid || !c1Valid) return
    setSubmitting(true)
    const id = createCase({
      caseRef: caseRef.trim(),
      screening: {
        ageGroup,
        sexAtBirth,
        modalities: Object.fromEntries(
          Object.entries(files).map(([key, file]) => [key, file?.name ?? ""]),
        ),
        questionnaire: answers,
      },
      c1: {
        risk_tier: riskTier,
        calibrated_confidence: confidenceValue,
        symptom_ids: symptomIds,
      },
    })
    if (validateFirst && !isDemo) void validateIntake(id)
    void runReasoning(id)
    navigate("/analysis")
  }

  return (
    <>
      <PageHeader
        eyebrow="Component 1 · Screening"
        title="New screening"
        description="Collect screening inputs, record the approved Component 1 summary and send it to Component 2 for Ayurvedic reasoning."
      />

      <Notice tone="caution" title="What this form does and does not do" className="mb-5">
        No Component 1 screening model service exists in this repository. Selected images and PPG
        files stay in this browser: they are not uploaded and no model runs on them. The anemia risk
        tier, calibrated confidence and symptom IDs must come from an approved Component 1 result and
        are entered manually in step 3. Use synthetic or de-identified data only.
      </Notice>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[240px_minmax(0,1fr)]">
        <nav aria-label="Screening steps">
          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-1">
            {steps.map(({ number, label, icon: Icon }) => (
              <li key={number}>
                <button
                  type="button"
                  disabled={number > step}
                  onClick={() => setStep(number)}
                  aria-current={step === number ? "step" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-xl p-2.5 text-left transition disabled:cursor-not-allowed",
                    step === number
                      ? "bg-emerald-50 text-emerald-900 ring-1 ring-emerald-200"
                      : step > number
                        ? "text-emerald-800 hover:bg-white"
                        : "text-slate-400",
                  )}
                >
                  {step > number ? (
                    <CheckCircle2 aria-hidden className="size-5 shrink-0" />
                  ) : (
                    <Icon aria-hidden className="size-5 shrink-0" />
                  )}
                  <span className="min-w-0">
                    <span className="block text-[10px] opacity-70">STEP {number}</span>
                    <span className="block truncate text-xs font-semibold sm:text-sm">{label}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <Panel bodyClassName="p-5 sm:p-6">
          {step === 1 && (
            <div>
              <h2 className="text-base font-semibold text-slate-900">Case context</h2>
              <p className="mt-1 text-sm text-slate-500">
                Use a pseudonymous case reference. Never enter names, national IDs or contact details.
              </p>
              <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">
                  Case reference <span className="text-rose-600">*</span>
                  <input
                    value={caseRef}
                    onChange={(event) => setCaseRef(event.target.value)}
                    placeholder="e.g. CASE-0001"
                    aria-invalid={touched && !caseRefValid}
                    className={fieldClass}
                  />
                  <span className={cn("mt-1 block text-xs font-normal", touched && !caseRefValid ? "text-rose-700" : "text-slate-400")}>
                    1–64 characters: letters, digits, “.”, “_”, “:” or “-”.
                  </span>
                </label>
                <label className="text-sm font-medium text-slate-700">
                  Age group
                  <select value={ageGroup} onChange={(event) => setAgeGroup(event.target.value)} className={fieldClass}>
                    <option value="">Not specified</option>
                    <option value="under-18">Under 18</option>
                    <option value="18-29">18–29 years</option>
                    <option value="30-44">30–44 years</option>
                    <option value="45-59">45–59 years</option>
                    <option value="60-plus">60 years or older</option>
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700 sm:col-span-2">
                  Sex assigned at birth
                  <select value={sexAtBirth} onChange={(event) => setSexAtBirth(event.target.value)} className={fieldClass}>
                    <option value="not-provided">Not provided</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other / prefer to describe</option>
                  </select>
                  <span className="mt-1 block text-xs font-normal text-slate-400">
                    Context fields are kept in this browser only; Component 2 does not accept them.
                  </span>
                </label>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-base font-semibold text-slate-900">Screening inputs</h2>
              <p className="mt-1 text-sm text-slate-500">
                File selection only (camera capture is not implemented). Files are not uploaded and not analysed.
              </p>
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {modalities.map((modality) => {
                  const file = files[modality.key]
                  const error = fileErrors[modality.key]
                  return (
                    <div
                      key={modality.key}
                      className={cn(
                        "rounded-xl border p-4",
                        file ? "border-emerald-200 bg-emerald-50/40" : "border-dashed border-slate-300 bg-slate-50/60",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                            <FileUp aria-hidden className="size-4 text-emerald-700" /> {modality.title}
                          </p>
                          <p className="mt-0.5 text-xs text-slate-500">{modality.description}</p>
                        </div>
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", file ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500")}>
                          {file ? "Selected" : "Missing"}
                        </span>
                      </div>
                      {file ? (
                        <div className="mt-3 flex items-center justify-between gap-2 text-xs">
                          <span className="truncate font-medium text-slate-700">
                            {file.name} · {formatBytes(file.size)}
                          </span>
                          <Button variant="ghost" size="icon-xs" aria-label={`Remove ${modality.title}`} onClick={() => removeFile(modality.key)}>
                            <X />
                          </Button>
                        </div>
                      ) : (
                        <label className="mt-3 inline-flex cursor-pointer items-center rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 focus-within:ring-2 focus-within:ring-emerald-500 hover:bg-slate-50">
                          Choose file
                          <input
                            type="file"
                            accept={modality.accept}
                            className="sr-only"
                            onChange={(event) => {
                              selectFile(modality.key, event.target.files?.[0] ?? null)
                              event.target.value = ""
                            }}
                          />
                        </label>
                      )}
                      {error && <p className="mt-2 text-xs text-rose-700">{error}</p>}
                    </div>
                  )
                })}
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Input completeness: {selectedCount} of {modalities.length} modalities selected. Modality
                quality scoring is not available because no Component 1 service is connected.
              </p>

              <div className="mt-6 rounded-xl border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Structured questionnaire</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Example fields only; the approved research questionnaire is not yet defined in the repository.
                </p>
                <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {questionnaire.map((question) => (
                    <label key={question.key} className="text-sm text-slate-600">
                      {question.label}
                      <select
                        value={answers[question.key]}
                        onChange={(event) => setAnswers((current) => ({ ...current, [question.key]: event.target.value }))}
                        className={fieldClass}
                      >
                        {question.options.map((option) => (
                          <option key={option} value={option}>
                            {optionLabel(option)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-base font-semibold text-slate-900">Approved Component 1 result</h2>
              <p className="mt-1 text-sm text-slate-500">
                These fields form the Component 2 reasoning request (<code className="text-xs">risk_tier</code>,{" "}
                <code className="text-xs">calibrated_confidence</code>, <code className="text-xs">symptom_ids</code>).
                Copy them from an approved Component 1 output; do not estimate them.
              </p>
              <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
                <fieldset>
                  <legend className="text-sm font-medium text-slate-700">
                    Anemia risk tier <span className="text-rose-600">*</span>
                  </legend>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(["low", "moderate", "high"] as const).map((tier) => (
                      <label
                        key={tier}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm capitalize",
                          riskTier === tier ? "border-emerald-600 bg-emerald-50 text-emerald-900" : "border-slate-200 text-slate-700",
                        )}
                      >
                        <input
                          type="radio"
                          name="risk-tier"
                          value={tier}
                          checked={riskTier === tier}
                          onChange={() => setRiskTier(tier)}
                          className="accent-emerald-700"
                        />
                        {tier}
                      </label>
                    ))}
                  </div>
                  {touched && riskTier === "" && <p className="mt-1 text-xs text-rose-700">Select the risk tier.</p>}
                </fieldset>
                <label className="text-sm font-medium text-slate-700">
                  Calibrated confidence (0–1) <span className="text-rose-600">*</span>
                  <input
                    inputMode="decimal"
                    value={confidence}
                    onChange={(event) => setConfidence(event.target.value)}
                    placeholder="e.g. 0.82"
                    aria-invalid={touched && !confidenceValid}
                    className={fieldClass}
                  />
                  <span className={cn("mt-1 block text-xs font-normal", touched && !confidenceValid ? "text-rose-700" : "text-slate-400")}>
                    Component 1 screening confidence. Passed to Component 2 as metadata only.
                  </span>
                </label>
                <label className="text-sm font-medium text-slate-700 sm:col-span-2">
                  Canonical symptom IDs <span className="text-rose-600">*</span>
                  <textarea
                    value={symptomRaw}
                    onChange={(event) => setSymptomRaw(event.target.value)}
                    rows={3}
                    placeholder="Separate IDs with commas, spaces or new lines"
                    aria-invalid={touched && !symptomsValid}
                    className={cn(fieldClass, "h-auto py-2 font-mono")}
                  />
                  <span className={cn("mt-1 block text-xs font-normal", touched && !symptomsValid ? "text-rose-700" : "text-slate-400")}>
                    {symptomIds.length} ID{symptomIds.length === 1 ? "" : "s"} (1–50 required).{" "}
                    {invalidSymptoms.length > 0 && `Invalid: ${invalidSymptoms.slice(0, 3).join(", ")}. `}
                    IDs must match stored Symptom concepts; free-text symptom mapping is not implemented and
                    there is no endpoint to list available IDs.
                  </span>
                </label>
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-base font-semibold text-slate-900">Review and run reasoning</h2>
              <dl className="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-200">
                {[
                  ["Case reference", caseRef.trim()],
                  ["Age group", ageGroup || "Not specified"],
                  ["Sex assigned at birth", sexLabels[sexAtBirth] ?? sexAtBirth],
                  ["Inputs selected (local only)", `${selectedCount} of ${modalities.length}`],
                  ["Risk tier", riskTier],
                  ["Calibrated confidence", confidenceValid ? confidenceValue.toFixed(2) : "—"],
                  ["Symptom IDs", symptomIds.join(", ")],
                ].map(([label, value]) => (
                  <div key={label} className="flex flex-wrap justify-between gap-2 px-4 py-2.5">
                    <dt className="text-sm text-slate-500">{label}</dt>
                    <dd className="max-w-[65%] text-right text-sm font-medium break-words text-slate-800">{value}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-4 rounded-xl border border-slate-200 p-4 text-sm">
                <p className="font-semibold text-slate-800">What will be sent</p>
                {isDemo ? (
                  <p className="mt-1 text-slate-600">
                    Nothing. Demo mode displays a fixed fictional Component 2 response; your inputs are not analysed.
                  </p>
                ) : (
                  <>
                    <p className="mt-1 text-slate-600">
                      Only <code className="text-xs">risk_tier</code>, <code className="text-xs">calibrated_confidence</code> and{" "}
                      <code className="text-xs">symptom_ids</code> go to <code className="text-xs">POST /api/v1/c2/reasoning</code>.
                      The case reference, context fields, questionnaire and files are not sent.
                    </p>
                    <label className="mt-3 flex items-start gap-2 text-slate-700">
                      <Checkbox checked={validateFirst} onCheckedChange={(checked) => setValidateFirst(checked === true)} className="mt-0.5" />
                      <span>
                        Also validate the summary with the Component 1 intake endpoint{" "}
                        <code className="text-xs">POST /api/v1/c1/screening-result</code> (schema validation and
                        echo only; sends the case reference, risk tier and confidence).
                      </span>
                    </label>
                  </>
                )}
              </div>
            </div>
          )}

          <div className="mt-6 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <Button
              variant="ghost"
              onClick={() => (step === 1 ? navigate("/") : setStep((current) => current - 1))}
            >
              {step > 1 && <ChevronLeft />}
              {step === 1 ? "Cancel" : "Back"}
            </Button>
            <span className="hidden text-xs text-slate-400 sm:block">Step {step} of 4</span>
            {step < 4 ? (
              <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={next}>
                Continue <ChevronRight />
              </Button>
            ) : (
              <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={submit} disabled={submitting || !c1Valid || !caseRefValid}>
                <Leaf /> {isDemo ? "Create demo case" : "Create case & run reasoning"}
              </Button>
            )}
          </div>
        </Panel>
      </div>
    </>
  )
}
