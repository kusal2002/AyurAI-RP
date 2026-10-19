import * as React from "react"

import { buildC3Package } from "@/lib/api/adapters"
import { ApiError, isAbortError, isApiError } from "@/lib/api/client"
import { component1IntakeApi, component2Api } from "@/lib/api/component2"
import { component3Api } from "@/lib/api/component3"
import type {
  Component2Output,
  PatientContext,
  PractitionerFeedbackRequest,
  PractitionerFeedbackResponse,
  RiskTier,
  SafetyAssessmentReport,
} from "@/lib/api/types"
import { demoComponent2Output, demoSafetyReport } from "@/lib/demo/fixtures"
import { env, type DataMode } from "@/lib/env"

/**
 * Session workspace.
 *
 * Holds the cases created in this browser tab. There is no case-persistence
 * service in the repository, so nothing here is stored on a server, and it
 * is deliberately not written to localStorage/sessionStorage: reloading the
 * page clears it.
 */

export type ErrorInfo = { kind: ApiError["kind"] | "unknown"; message: string; details: string[] }

export type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T; receivedAt: string }
  | { status: "error"; error: ErrorInfo }

export type ModalityKey = "conjunctiva" | "tongue" | "nail" | "ppg"

export type ScreeningInputs = {
  ageGroup: string
  sexAtBirth: string
  /** File names only; file contents are never uploaded or retained. */
  modalities: Partial<Record<ModalityKey, string>>
  questionnaire: Record<string, string>
}

export type C1Summary = {
  risk_tier: RiskTier
  calibrated_confidence: number
  symptom_ids: string[]
  /** How this summary was obtained. No Component 1 model service exists yet. */
  origin: "manual_entry" | "demo_fixture"
  intake: AsyncState<{ status: string; message: string }>
}

export type FeedbackRecord = {
  localId: string
  submittedAt: string
  request: PractitionerFeedbackRequest
  outcome:
    | { status: "recorded"; response: PractitionerFeedbackResponse }
    | { status: "demo_not_sent" }
    | { status: "error"; error: ErrorInfo }
}

export type CaseRecord = {
  id: string
  source: DataMode
  caseRef: string
  createdAt: string
  screening: ScreeningInputs | null
  c1: C1Summary | null
  c2: AsyncState<Component2Output>
  c3: AsyncState<SafetyAssessmentReport>
  c3Build: { notes: string[]; excluded: { candidateId: string; reason: string }[] } | null
  feedback: FeedbackRecord[]
}

type WorkspaceContextValue = {
  mode: DataMode
  setMode: (mode: DataMode) => void
  cases: CaseRecord[]
  activeCase: CaseRecord | null
  selectCase: (id: string) => void
  createCase: (input: {
    caseRef: string
    screening: ScreeningInputs | null
    c1: Omit<C1Summary, "intake" | "origin">
  }) => string
  validateIntake: (caseId: string) => Promise<void>
  runReasoning: (caseId: string) => Promise<void>
  runSafety: (caseId: string, patient: PatientContext, candidateIds: string[]) => Promise<void>
  submitFeedback: (caseId: string, request: PractitionerFeedbackRequest) => Promise<FeedbackRecord>
}

const WorkspaceContext = React.createContext<WorkspaceContextValue | undefined>(undefined)

export function toErrorInfo(error: unknown): ErrorInfo {
  if (isApiError(error)) {
    return { kind: error.kind, message: error.message, details: error.details }
  }
  return { kind: "unknown", message: "An unexpected error occurred.", details: [] }
}

function localId(prefix: string) {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}-${random}`
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function demoCase(): CaseRecord {
  const now = new Date().toISOString()
  return {
    id: "demo-case-1",
    source: "demo",
    caseRef: "DEMO-CASE-001",
    createdAt: now,
    screening: {
      ageGroup: "30-44",
      sexAtBirth: "not-provided",
      modalities: { conjunctiva: "demo-eye.jpg", tongue: "demo-tongue.jpg" },
      questionnaire: { fatigue: "yes", dizziness: "not-answered", diet: "mixed" },
    },
    c1: {
      risk_tier: demoComponent2Output.upstream.risk_tier,
      calibrated_confidence: demoComponent2Output.upstream.calibrated_confidence,
      symptom_ids: demoComponent2Output.input_symptom_ids,
      origin: "demo_fixture",
      intake: { status: "idle" },
    },
    c2: { status: "success", data: demoComponent2Output, receivedAt: now },
    c3: { status: "success", data: demoSafetyReport, receivedAt: now },
    c3Build: null,
    feedback: [],
  }
}

function initialCases(mode: DataMode): CaseRecord[] {
  return mode === "demo" ? [demoCase()] : []
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = React.useState<DataMode>(env.defaultDataMode)
  const [cases, setCases] = React.useState<CaseRecord[]>(() => initialCases(env.defaultDataMode))
  const [activeId, setActiveId] = React.useState<string | null>(
    () => initialCases(env.defaultDataMode)[0]?.id ?? null,
  )
  const controllers = React.useRef(new Map<string, AbortController>())
  const casesRef = React.useRef(cases)
  React.useEffect(() => {
    casesRef.current = cases
  }, [cases])

  const updateCase = React.useCallback((id: string, update: (record: CaseRecord) => CaseRecord) => {
    setCases((current) => current.map((record) => (record.id === id ? update(record) : record)))
  }, [])

  /** Abort any in-flight request of the same kind for a case (outdated request). */
  const startRequest = React.useCallback((key: string) => {
    controllers.current.get(key)?.abort()
    const controller = new AbortController()
    controllers.current.set(key, controller)
    return controller
  }, [])

  const setMode = React.useCallback((next: DataMode) => {
    controllers.current.forEach((controller) => controller.abort())
    controllers.current.clear()
    const seeded = initialCases(next)
    setModeState(next)
    setCases(seeded)
    setActiveId(seeded[0]?.id ?? null)
  }, [])

  const createCase: WorkspaceContextValue["createCase"] = React.useCallback(
    ({ caseRef, screening, c1 }) => {
      const id = localId("case")
      const record: CaseRecord = {
        id,
        source: mode,
        caseRef,
        createdAt: new Date().toISOString(),
        screening,
        c1: { ...c1, origin: "manual_entry", intake: { status: "idle" } },
        c2: { status: "idle" },
        c3: { status: "idle" },
        c3Build: null,
        feedback: [],
      }
      // Keep the ref in sync immediately so follow-up actions can find the case.
      casesRef.current = [record, ...casesRef.current]
      setCases((current) => [record, ...current])
      setActiveId(id)
      return id
    },
    [mode],
  )

  const findCase = React.useCallback(
    (id: string) => casesRef.current.find((record) => record.id === id),
    [],
  )

  const validateIntake = React.useCallback(
    async (caseId: string) => {
      const record = findCase(caseId)
      if (!record?.c1) return
      const setIntake = (intake: C1Summary["intake"]) =>
        updateCase(caseId, (current) =>
          current.c1 ? { ...current, c1: { ...current.c1, intake } } : current,
        )
      if (record.source === "demo") {
        setIntake({ status: "error", error: { kind: "unknown", message: "Demo mode: nothing is sent to a service.", details: [] } })
        return
      }
      setIntake({ status: "loading" })
      const controller = startRequest(`${caseId}:intake`)
      try {
        const response = await component1IntakeApi.validateScreeningResult(
          {
            case_id: record.caseRef,
            risk_tier: record.c1.risk_tier,
            calibrated_confidence: record.c1.calibrated_confidence,
            symptom_summary: [],
            derived_context: {},
          },
          controller.signal,
        )
        setIntake({
          status: "success",
          data: { status: response.status, message: response.message },
          receivedAt: new Date().toISOString(),
        })
      } catch (error) {
        if (!isAbortError(error)) setIntake({ status: "error", error: toErrorInfo(error) })
      }
    },
    [findCase, startRequest, updateCase],
  )

  const runReasoning = React.useCallback(
    async (caseId: string) => {
      const record = findCase(caseId)
      if (!record?.c1) return
      updateCase(caseId, (current) => ({
        ...current,
        c2: { status: "loading" },
        c3: { status: "idle" },
        c3Build: null,
      }))

      if (record.source === "demo") {
        await wait(500)
        updateCase(caseId, (current) => ({
          ...current,
          c2: { status: "success", data: demoComponent2Output, receivedAt: new Date().toISOString() },
        }))
        return
      }

      const controller = startRequest(`${caseId}:c2`)
      try {
        const output = await component2Api.reason(
          {
            risk_tier: record.c1.risk_tier,
            calibrated_confidence: record.c1.calibrated_confidence,
            symptom_ids: record.c1.symptom_ids,
          },
          controller.signal,
        )
        updateCase(caseId, (current) => ({
          ...current,
          c2: { status: "success", data: output, receivedAt: new Date().toISOString() },
        }))
      } catch (error) {
        if (isAbortError(error)) return
        updateCase(caseId, (current) => ({ ...current, c2: { status: "error", error: toErrorInfo(error) } }))
      }
    },
    [findCase, startRequest, updateCase],
  )

  const runSafety = React.useCallback(
    async (caseId: string, patient: PatientContext, candidateIds: string[]) => {
      const record = findCase(caseId)
      if (!record || record.c2.status !== "success") return
      updateCase(caseId, (current) => ({ ...current, c3: { status: "loading" } }))

      if (record.source === "demo") {
        await wait(500)
        updateCase(caseId, (current) => ({
          ...current,
          c3: { status: "success", data: demoSafetyReport, receivedAt: new Date().toISOString() },
          c3Build: {
            notes: ["Demo mode: the fictional safety report fixture is shown; nothing was sent."],
            excluded: [],
          },
        }))
        return
      }

      const build = buildC3Package(record.c2.data, { caseId: record.caseRef, candidateIds })
      updateCase(caseId, (current) => ({
        ...current,
        c3Build: { notes: build.notes, excluded: build.excluded },
      }))
      if (build.package.candidates.length === 0) {
        updateCase(caseId, (current) => ({
          ...current,
          c3: {
            status: "error",
            error: {
              kind: "validation",
              message: "No candidate could be sent to Component 3. See the excluded candidates below.",
              details: [],
            },
          },
        }))
        return
      }

      const controller = startRequest(`${caseId}:c3`)
      try {
        const report = await component3Api.evaluate(
          { candidate_package: build.package, patient_context: patient },
          controller.signal,
        )
        updateCase(caseId, (current) => ({
          ...current,
          c3: { status: "success", data: report, receivedAt: new Date().toISOString() },
        }))
      } catch (error) {
        if (isAbortError(error)) return
        updateCase(caseId, (current) => ({ ...current, c3: { status: "error", error: toErrorInfo(error) } }))
      }
    },
    [findCase, startRequest, updateCase],
  )

  const submitFeedback = React.useCallback(
    async (caseId: string, request: PractitionerFeedbackRequest): Promise<FeedbackRecord> => {
      const record = findCase(caseId)
      const base = {
        localId: localId("fb"),
        submittedAt: new Date().toISOString(),
        request,
      }
      let entry: FeedbackRecord
      if (!record || record.source === "demo") {
        await wait(300)
        entry = { ...base, outcome: { status: "demo_not_sent" } }
      } else {
        try {
          const response = await component2Api.submitFeedback(request)
          entry = { ...base, outcome: { status: "recorded", response } }
        } catch (error) {
          entry = { ...base, outcome: { status: "error", error: toErrorInfo(error) } }
        }
      }
      updateCase(caseId, (current) => ({ ...current, feedback: [entry, ...current.feedback] }))
      return entry
    },
    [findCase, updateCase],
  )

  const activeCase = cases.find((record) => record.id === activeId) ?? null

  const value = React.useMemo<WorkspaceContextValue>(
    () => ({
      mode,
      setMode,
      cases,
      activeCase,
      selectCase: setActiveId,
      createCase,
      validateIntake,
      runReasoning,
      runSafety,
      submitFeedback,
    }),
    [mode, setMode, cases, activeCase, createCase, validateIntake, runReasoning, runSafety, submitFeedback],
  )

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const context = React.useContext(WorkspaceContext)
  if (!context) throw new Error("useWorkspace must be used within WorkspaceProvider")
  return context
}
