import * as React from "react"
import { Download, Pencil, UserRound } from "lucide-react"

import { Notice, fieldClass } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { component1Api } from "@/lib/api/component1"
import type { C1Patient, C1PatientDataStatus } from "@/lib/api/types"

/**
 * Patient registration (name + phone) for Component 1. Personal details are only sent to the protected
 * Component 1 routes; they never appear in URLs, session IDs or file names.
 *
 * The browser can only use these routes in the local laptop mode for now: in Component 4 mode it would have to send
 * the user's sign-in token, which needs a shared change (a token getter exported from lib/api/component4.ts).
 */
export function patientFeaturesAvailable(status: C1PatientDataStatus | null): boolean {
  return status?.enabled === true && status.access_mode === "local_dev"
}

// Same rules as component1/api/patient_records.py (normalise_name / normalise_phone).
export function nameProblem(raw: string): string | null {
  const name = raw.normalize("NFC").trim().split(/\s+/).join(" ")
  if (name.length < 2 || name.length > 100) return "Enter the patient's full name (2 to 100 characters)."
  if (!/^[\p{L}\p{M} .'\-’]+$/u.test(name)) return "The name may contain letters, spaces, apostrophes, hyphens and full stops only."
  if ((name.match(/\p{L}/gu) ?? []).length < 2) return "Enter the patient's full name (2 to 100 characters)."
  return null
}

export function phoneProblem(raw: string): string | null {
  let compact = raw.replace(/[\s\-().]/g, "")
  if (compact.startsWith("00")) compact = "+" + compact.slice(2)
  if (/^0\d{9}$/.test(compact) || /^94\d{9}$/.test(compact)) return null
  if (/^\+[1-9]\d{7,14}$/.test(compact)) {
    return compact.startsWith("+94") && !/^\+94\d{9}$/.test(compact) ? "Sri Lankan numbers have 9 digits after +94 (for example +94 77 123 4567)." : null
  }
  return "Enter a phone number such as 077 123 4567 or +94 77 123 4567; international numbers start with +."
}

export function newRequestId(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : "Component 1 returned an unexpected error."
}

/** Name + phone form with inline validation; used for registration and for corrections. */
export function PatientDetailsForm({
  initial,
  submitLabel,
  busy,
  onSubmit,
  onCancel,
}: {
  initial?: { fullName: string; phone: string }
  submitLabel: string
  busy: boolean
  onSubmit: (fullName: string, phone: string) => Promise<void>
  onCancel?: () => void
}) {
  const [fullName, setFullName] = React.useState(initial?.fullName ?? "")
  const [phone, setPhone] = React.useState(initial?.phone ?? "")
  const [touched, setTouched] = React.useState(false)
  const nameError = nameProblem(fullName)
  const phoneError = phoneProblem(phone)
  const showErrors = touched || fullName !== "" || phone !== ""

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault()
        setTouched(true)
        if (!nameError && !phoneError && !busy) void onSubmit(fullName.trim(), phone.trim())
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium text-slate-600">
          Patient full name <span className="text-rose-700">*</span>
          <input className={fieldClass} value={fullName} autoComplete="off" maxLength={100} required
            aria-invalid={showErrors && Boolean(nameError)} onChange={(event) => setFullName(event.target.value)} />
          {showErrors && nameError && <span className="mt-1 block text-xs font-normal text-rose-700">{nameError}</span>}
        </label>
        <label className="text-xs font-medium text-slate-600">
          Contact phone number <span className="text-rose-700">*</span>
          <input className={fieldClass} value={phone} inputMode="tel" autoComplete="off" maxLength={24} required
            aria-invalid={showErrors && Boolean(phoneError)} onChange={(event) => setPhone(event.target.value)} />
          <span className="mt-1 block text-xs font-normal text-slate-500">Sri Lanka: 077 123 4567 or +94 77 123 4567. Other countries: + and the country code.</span>
          {showErrors && phoneError && <span className="mt-1 block text-xs font-normal text-rose-700">{phoneError}</span>}
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || (showErrors && Boolean(nameError || phoneError))}>
          <UserRound /> {busy ? "Saving…" : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}

/** Registered patient line for the current session, with review / correction. */
export function PatientBanner({
  sessionId,
  patient,
  onChanged,
}: {
  sessionId: string
  patient: C1Patient | null
  onChanged: (patient: C1Patient) => void
}) {
  const [editing, setEditing] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const save = async (fullName: string, phone: string) => {
    setBusy(true)
    setError(null)
    try {
      onChanged((await component1Api.updatePatient(sessionId, { full_name: fullName, phone })).patient)
      setEditing(false)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-3 space-y-2 rounded-xl border border-slate-200 p-3 text-sm">
      {editing ? (
        <PatientDetailsForm
          initial={patient ? { fullName: patient.full_name, phone: patient.phone_display ?? "" } : undefined}
          submitLabel={patient ? "Save corrected details" : "Save patient details"}
          busy={busy}
          onSubmit={save}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <UserRound className="size-4 text-slate-500" aria-hidden />
          {patient ? (
            <span>
              <span className="font-semibold text-slate-800">{patient.full_name}</span>
              <span className="text-slate-600"> · {patient.phone_display}</span>
            </span>
          ) : (
            <span className="text-slate-600">Coded session: no patient name or phone stored.</span>
          )}
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            <Pencil /> {patient ? "Edit details" : "Add patient details"}
          </Button>
        </div>
      )}
      {error && <Notice tone="critical">{error}</Notice>}
    </div>
  )
}

/** Downloads the protected PDF; the file name uses the session ID, never the patient's name. */
export function PdfReportButton({ sessionId, disabled }: { sessionId: string; disabled?: boolean }) {
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const download = async () => {
    setBusy(true)
    setError(null)
    try {
      const blob = await component1Api.reportPdf(sessionId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `AyurAI-C1-report-${sessionId}.pdf`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Button variant="outline" size="sm" disabled={busy || disabled} onClick={() => void download()}>
        <Download /> {busy ? "Preparing PDF…" : "PDF report"}
      </Button>
      {error && <span className="text-xs text-rose-700">{error}</span>}
    </>
  )
}

/** Shown instead of the registration form when patient features are off on this server. */
export function RegistrationUnavailable({ status }: { status: C1PatientDataStatus | null }) {
  if (!status) return null
  return (
    <Notice tone="neutral" title="Patient name and phone registration is not available here">
      {status.access_mode === "component4"
        ? "This server requires Component 4 sign-in for patient details, which this page cannot send yet. "
        : "Patient details are switched off on this server until Component 4 sign-in is integrated. "}
      A coded session (no name or phone) is created instead.
    </Notice>
  )
}
