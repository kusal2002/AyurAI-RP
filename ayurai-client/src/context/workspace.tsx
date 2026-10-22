import * as React from "react"

import { buildC3Package } from "@/lib/api/adapters"
import { ApiError, isAbortError, isApiError } from "@/lib/api/client"
import { component1IntakeApi, component2Api } from "@/lib/api/component2"
import { component3Api } from "@/lib/api/component3"
import type {
  C1ScreeningPayload,
  C1SymptomMapping,
  Component2Output,
  KnowledgeScope,
  PatientContext,
  PractitionerFeedbackRequest,
  PractitionerFeedbackResponse,
  RiskTier,
  SafetyAssessmentReport,
} from "@/lib/api/types"
import { c1View } from "@/lib/api/types"
import { focusOutput } from "@/lib/c2-derive"
import { useAccess } from "@/lib/access"
import { readSession, SESSION_KEYS, writeSession } from "@/lib/session-store"

/**
 * Session workspace.
 *
 * Holds the cases created in this browser tab. There is no case-persistence
 * service in the repository, so nothing here is stored on a server. The cases
 * are kept in this tab's sessionStorage (never localStorage): a page refresh
 * keeps them, closing the tab clears them, and other tabs cannot see them.
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
  /** Null when Component 1 supplied no calibrated confidence. */
  calibrated_confidence: number | null
  symptom_ids: string[]
  /**
   * How this summary was obtained. No Component 1 model service exists yet:
   * manual entry or an imported C1 screening payload.
   */
  origin: "manual_entry" | "c1_payload"
  intake: AsyncState<{ status: string; message: string }>
  /** Imported Component 1 payload (held in this tab only). */
  payload?: C1ScreeningPayload
  /** Symptom-name mapping reported by POST /api/v1/c1/reasoning. */
  mapping?: C1SymptomMapping
  /** Label of the payload source shown to the user (e.g. "synthetic scenario"). */
  payloadSource?: string
}

export type FeedbackRecord = {
  localId: string
  submittedAt: string
  request: PractitionerFeedbackRequest
  outcome:
    | { status: "recorded"; response: PractitionerFeedbackResponse }
    | { status: "error"; error: ErrorInfo }
}

export type CaseRecord = {
  id: string
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
  /** Knowledge scope for the next reasoning run (approved by default; never stored). */
  knowledgeScope: KnowledgeScope
  setKnowledgeScope: (scope: KnowledgeScope) => void
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
  /** Create one case per Component 1 payload and run C1 -> C2 for each, in order. */
  importC1Payloads: (payloads: C1ScreeningPayload[], payloadSource: string) => Promise<string[]>
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

type StoredWorkspace = { cases: CaseRecord[]; activeId: string | null }

/** A request still running when the page was refreshed was cancelled: show it as not run. */
function settle<T>(state: AsyncState<T>): AsyncState<T> {
  return state.status === "loading" ? { status: "idle" } : state
}

function focusStored(state: CaseRecord["c2"]): CaseRecord["c2"] {
  return state.status === "success" ? { ...state, data: focusOutput(state.data) } : state
}

/** Cases saved in this tab's sessionStorage, with interrupted requests reset. */
function restoreWorkspace(): StoredWorkspace {
  const stored = readSession<StoredWorkspace>(SESSION_KEYS.workspace)
  if (!stored || !Array.isArray(stored.cases)) return { cases: [], activeId: null }
  const cases = stored.cases.map((record) => ({
    ...record,
    c1: record.c1 ? { ...record.c1, intake: settle(record.c1.intake) } : record.c1,
    // Cases saved before candidates were focused are focused on restore.
    c2: focusStored(settle(record.c2)),
    c3: settle(record.c3),
  }))
  const activeId = cases.some((record) => record.id === stored.activeId) ? stored.activeId : null
  return { cases, activeId }
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [restored] = React.useState(restoreWorkspace)
  const [cases, setCases] = React.useState<CaseRecord[]>(restored.cases)
  const [activeId, setActiveId] = React.useState<string | null>(restored.activeId)
  // Save after every change, so a refresh brings the cases back
  React.useEffect(() => {
    writeSession(SESSION_KEYS.workspace, { cases, activeId } satisfies StoredWorkspace)
  }, [cases, activeId])
  const [knowledgeScope, setKnowledgeScope] = React.useState<KnowledgeScope>("approved")
  const scopeRef = React.useRef<KnowledgeScope>("approved")
  // Only supervisors and researchers may include unverified (provisional) knowledge;
  // practitioners' reasoning always uses approved knowledge only.
  const { canUseTechnicalView } = useAccess()
  React.useEffect(() => {
    scopeRef.current = canUseTechnicalView ? knowledgeScope : "approved"
  }, [knowledgeScope, canUseTechnicalView])
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

  const createCase: WorkspaceContextValue["createCase"] = React.useCallback(
    ({ caseRef, screening, c1 }) => {
      const id = localId("case")
      const record: CaseRecord = {
        id,
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
    [],
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

      const controller = startRequest(`${caseId}:c2`)
      if (record.c1.origin === "c1_payload" && record.c1.payload) {
        try {
          const response = await component2Api.reasonFromScreening(
            record.c1.payload,
            controller.signal,
            scopeRef.current,
          )
          updateCase(caseId, (current) => ({
            ...current,
            c1: current.c1
              ? {
                  ...current.c1,
                  mapping: response.mapping,
                  symptom_ids: response.mapping.resolved_symptoms.map((item) => item.symptom_id),
                }
              : current.c1,
            c2: response.reasoning
              ? { status: "success", data: focusOutput(response.reasoning), receivedAt: new Date().toISOString() }
              : {
                  status: "error",
                  error: {
                    kind: "validation",
                    message:
                      response.status === "blocked"
                        ? `Component 2 did not run: the Component 1 payload was blocked (${response.mapping.reason ?? "unknown reason"}).`
                        : `Component 2 did not run: no present symptom resolved to a knowledge-graph symptom (${response.mapping.reason ?? "unknown reason"}). Nothing was guessed.`,
                    details: response.mapping.unresolved_symptoms.map(
                      (item) => `${item.input_name}: ${item.status.replace(/_/g, " ")}`,
                    ),
                  },
                },
          }))
        } catch (error) {
          if (isAbortError(error)) return
          updateCase(caseId, (current) => ({ ...current, c2: { status: "error", error: toErrorInfo(error) } }))
        }
        return
      }
      try {
        const output = await component2Api.reason(
          {
            risk_tier: record.c1.risk_tier,
            calibrated_confidence: record.c1.calibrated_confidence,
            symptom_ids: record.c1.symptom_ids,
          },
          controller.signal,
          scopeRef.current,
        )
        updateCase(caseId, (current) => ({
          ...current,
          c2: { status: "success", data: focusOutput(output), receivedAt: new Date().toISOString() },
        }))
      } catch (error) {
        if (isAbortError(error)) return
        updateCase(caseId, (current) => ({ ...current, c2: { status: "error", error: toErrorInfo(error) } }))
      }
    },
    [findCase, startRequest, updateCase],
  )

  const importC1Payloads = React.useCallback(
    async (payloads: C1ScreeningPayload[], payloadSource: string) => {
      const ids: string[] = []
      for (const payload of payloads) {
        const view = c1View(payload)
        const tier = view.riskLevel.trim().toLowerCase()
        const id = localId("case")
        const record: CaseRecord = {
          id,
          caseRef: payload.screening_id,
          createdAt: new Date().toISOString(),
          screening: null,
          c1: {
            // An unsupported tier is still sent: the service reports it as blocked.
            risk_tier: tier as RiskTier,
            calibrated_confidence: view.confidence,
            symptom_ids: [],
            origin: "c1_payload",
            intake: { status: "idle" },
            payload,
            payloadSource,
          },
          c2: { status: "idle" },
          c3: { status: "idle" },
          c3Build: null,
          feedback: [],
        }
        casesRef.current = [record, ...casesRef.current]
        setCases((current) => [record, ...current])
        ids.push(id)
      }
      if (ids.length) setActiveId(ids[0])
      // Sequential: the first request may load the embedding model.
      for (const id of ids) await runReasoning(id)
      return ids
    },
    [runReasoning],
  )

  const runSafety = React.useCallback(
    async (caseId: string, patient: PatientContext, candidateIds: string[]) => {
      const record = findCase(caseId)
      if (!record || record.c2.status !== "success") return
      updateCase(caseId, (current) => ({ ...current, c3: { status: "loading" } }))

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
      const base = {
        localId: localId("fb"),
        submittedAt: new Date().toISOString(),
        request,
      }
      let entry: FeedbackRecord
      try {
        const response = await component2Api.submitFeedback(request)
        entry = { ...base, outcome: { status: "recorded", response } }
      } catch (error) {
        entry = { ...base, outcome: { status: "error", error: toErrorInfo(error) } }
      }
      updateCase(caseId, (current) => ({ ...current, feedback: [entry, ...current.feedback] }))
      return entry
    },
    [updateCase],
  )

  const activeCase = cases.find((record) => record.id === activeId) ?? null

  const value = React.useMemo<WorkspaceContextValue>(
    () => ({
      knowledgeScope,
      setKnowledgeScope,
      cases,
      activeCase,
      selectCase: setActiveId,
      createCase,
      validateIntake,
      runReasoning,
      importC1Payloads,
      runSafety,
      submitFeedback,
    }),
    [knowledgeScope, cases, activeCase, createCase, validateIntake, runReasoning, importC1Payloads, runSafety, submitFeedback],
  )

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const context = React.useContext(WorkspaceContext)
  if (!context) throw new Error("useWorkspace must be used within WorkspaceProvider")
  return context
}
