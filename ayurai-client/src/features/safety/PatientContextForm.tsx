import * as React from "react"
import { Plus, Trash2 } from "lucide-react"

import { fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import type { MedicationItem, PatientContext } from "@/lib/api/types"

export type PatientFormState = {
  patientId: string
  age: string
  gender: string
  pregnant: boolean
  trimester: string
  lactating: boolean
  medications: MedicationItem[]
  comorbidities: string
  allergies: string
  egfr: string
  ckdStage: string
  hepatic: string
  creatinine: string
}

export const emptyPatientForm: PatientFormState = {
  patientId: "",
  age: "",
  gender: "",
  pregnant: false,
  trimester: "",
  lactating: false,
  medications: [],
  comorbidities: "",
  allergies: "",
  egfr: "",
  ckdStage: "Normal",
  hepatic: "None",
  creatinine: "",
}

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/

const splitList = (value: string) =>
  value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)

const optionalNumber = (value: string) => {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

export function validatePatientForm(form: PatientFormState): {
  errors: Partial<Record<keyof PatientFormState, string>>
  context: PatientContext | null
} {
  const errors: Partial<Record<keyof PatientFormState, string>> = {}
  if (!ID_PATTERN.test(form.patientId.trim())) errors.patientId = "Use a pseudonymous ID (letters, digits, . _ : -)."
  const age = Number(form.age)
  if (!form.age.trim() || !Number.isInteger(age) || age < 0 || age > 120) errors.age = "Enter a whole number from 0 to 120."
  if (!form.gender) errors.gender = "Select an option."
  const egfr = optionalNumber(form.egfr)
  if (Number.isNaN(egfr)) errors.egfr = "Enter a number or leave blank."
  const creatinine = optionalNumber(form.creatinine)
  if (Number.isNaN(creatinine)) errors.creatinine = "Enter a number or leave blank."
  if (form.medications.some((medication) => !medication.name.trim())) errors.medications = "Each medication needs a name."

  if (Object.keys(errors).length > 0) return { errors, context: null }

  const medications = form.medications.map((medication) => ({
    name: medication.name.trim(),
    drug_class: medication.drug_class?.trim() || null,
    dosage: medication.dosage?.trim() || null,
    route: "Oral",
  }))

  return {
    errors,
    context: {
      patient_id: form.patientId.trim(),
      age,
      gender: form.gender,
      pregnancy_status: form.pregnant,
      pregnancy_trimester: form.pregnant && form.trimester ? Number(form.trimester) : null,
      lactation_status: form.lactating,
      current_medications: medications,
      comorbidities: splitList(form.comorbidities),
      allergies: splitList(form.allergies),
      organ_function: {
        egfr,
        ckd_stage: form.ckdStage,
        hepatic_impairment: form.hepatic,
        serum_creatinine: creatinine,
      },
      // The Component 3 schema describes polypharmacy as five or more concurrent medications.
      polypharmacy: medications.length >= 5,
    },
  }
}

function FieldError({ message }: { message?: string }) {
  return message ? <span className="mt-1 block text-xs font-normal text-rose-700">{message}</span> : null
}

export function PatientContextForm({
  form,
  onChange,
  errors,
  drugSuggestions,
  disabled,
}: {
  form: PatientFormState
  onChange: (form: PatientFormState) => void
  errors: Partial<Record<keyof PatientFormState, string>>
  drugSuggestions: string[]
  disabled?: boolean
}) {
  const set = <K extends keyof PatientFormState>(key: K, value: PatientFormState[K]) => onChange({ ...form, [key]: value })
  const listId = React.useId()

  return (
    <fieldset disabled={disabled} className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <label className="text-sm font-medium text-slate-700">
          Pseudonymous patient ID <span className="text-rose-600">*</span>
          <input value={form.patientId} onChange={(event) => set("patientId", event.target.value)} placeholder="e.g. PT-0001" className={fieldClass} aria-invalid={Boolean(errors.patientId)} />
          <FieldError message={errors.patientId} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Age <span className="text-rose-600">*</span>
          <input inputMode="numeric" value={form.age} onChange={(event) => set("age", event.target.value)} className={fieldClass} aria-invalid={Boolean(errors.age)} />
          <FieldError message={errors.age} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Gender <span className="text-rose-600">*</span>
          <select value={form.gender} onChange={(event) => set("gender", event.target.value)} className={fieldClass} aria-invalid={Boolean(errors.gender)}>
            <option value="">Select…</option>
            <option value="Female">Female</option>
            <option value="Male">Male</option>
            <option value="Other">Other</option>
          </select>
          <FieldError message={errors.gender} />
        </label>
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox checked={form.pregnant} onCheckedChange={(checked) => set("pregnant", checked === true)} /> Currently pregnant
        </label>
        {form.pregnant && (
          <label className="text-sm text-slate-700">
            Trimester
            <select value={form.trimester} onChange={(event) => set("trimester", event.target.value)} className={`${fieldClass} w-36`}>
              <option value="">Unknown</option>
              <option value="1">First</option>
              <option value="2">Second</option>
              <option value="3">Third</option>
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Checkbox checked={form.lactating} onCheckedChange={(checked) => set("lactating", checked === true)} /> Breastfeeding
        </label>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700">Current medications</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => set("medications", [...form.medications, { name: "", drug_class: "", dosage: "" }])}
          >
            <Plus /> Add medication
          </Button>
        </div>
        <datalist id={listId}>
          {drugSuggestions.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        {form.medications.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            No medications entered. Herb–drug interaction rules can only match medications listed here.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {form.medications.map((medication, index) => (
              <li key={index} className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 p-2 sm:grid-cols-[1.4fr_1fr_1fr_auto]">
                <input
                  aria-label={`Medication ${index + 1} generic name`}
                  list={listId}
                  value={medication.name}
                  placeholder="Generic name"
                  onChange={(event) =>
                    set("medications", form.medications.map((item, i) => (i === index ? { ...item, name: event.target.value } : item)))
                  }
                  className={`${fieldClass} mt-0`}
                />
                <input
                  aria-label={`Medication ${index + 1} drug class`}
                  value={medication.drug_class ?? ""}
                  placeholder="Class (optional)"
                  onChange={(event) =>
                    set("medications", form.medications.map((item, i) => (i === index ? { ...item, drug_class: event.target.value } : item)))
                  }
                  className={`${fieldClass} mt-0`}
                />
                <input
                  aria-label={`Medication ${index + 1} current dosage`}
                  value={medication.dosage ?? ""}
                  placeholder="Current dosage (optional)"
                  onChange={(event) =>
                    set("medications", form.medications.map((item, i) => (i === index ? { ...item, dosage: event.target.value } : item)))
                  }
                  className={`${fieldClass} mt-0`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove medication ${index + 1}`}
                  onClick={() => set("medications", form.medications.filter((_, i) => i !== index))}
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <FieldError message={errors.medications} />
        {form.medications.length >= 5 && <p className="mt-1 text-xs text-slate-500">Polypharmacy flag will be set (five or more medications).</p>}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">
          Comorbidities
          <input value={form.comorbidities} onChange={(event) => set("comorbidities", event.target.value)} placeholder="Comma-separated, e.g. Hypertension" className={fieldClass} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Allergies
          <input value={form.allergies} onChange={(event) => set("allergies", event.target.value)} placeholder="Comma-separated" className={fieldClass} />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <label className="text-sm font-medium text-slate-700">
          eGFR (mL/min/1.73m²)
          <input inputMode="decimal" value={form.egfr} onChange={(event) => set("egfr", event.target.value)} className={fieldClass} />
          <FieldError message={errors.egfr} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          CKD stage
          <select value={form.ckdStage} onChange={(event) => set("ckdStage", event.target.value)} className={fieldClass}>
            {["Normal", "Stage G1", "Stage G2", "Stage G3a", "Stage G3b", "Stage G4", "Stage G5"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Hepatic impairment
          <select value={form.hepatic} onChange={(event) => set("hepatic", event.target.value)} className={fieldClass}>
            {["None", "Mild", "Moderate", "Severe"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Serum creatinine (mg/dL)
          <input inputMode="decimal" value={form.creatinine} onChange={(event) => set("creatinine", event.target.value)} className={fieldClass} />
          <FieldError message={errors.creatinine} />
        </label>
      </div>
    </fieldset>
  )
}
