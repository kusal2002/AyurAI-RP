import { ApiError, createApiClient } from "@/lib/api/client"
import type {
  C1Answers,
  C1CaptureCounts,
  C1CaptureStatus,
  C1PpgSummary,
  C1Profile,
  C1Question,
  C1QuestionnaireBody,
  C1QuestionSet,
  C1SerialPorts,
  Component1HealthResponse,
  Component1Json,
  Component1Report,
  Component1SessionsResponse,
} from "@/lib/api/types"
import { env } from "@/lib/env"

/** Component 1 local research API. */
export const component1Client = createApiClient("Component 1 local API", env.c1BaseUrl)

const SERVICE = "Component 1 local API"

function encodeSessionId(sessionId: string) {
  return encodeURIComponent(sessionId)
}

/** Component 1 error bodies carry fixed, non-patient messages (consent, safety, hardware); show them. */
function c1Message(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    return detail.message
  }
  if (Array.isArray(detail)) return `${SERVICE}: the submitted form is incomplete or invalid.`
  return `${SERVICE} returned HTTP ${status}.`
}

/** Intake requests: JSON or multipart, longer timeout (PPG recording and model inference take seconds). */
async function intake<T>(path: string, init: { json?: unknown; form?: FormData; timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), init.timeoutMs ?? 120_000)
  let response: Response
  try {
    response = await fetch(`${env.c1BaseUrl}${path}`, {
      method: "POST",
      headers: init.json !== undefined ? { Accept: "application/json", "Content-Type": "application/json" } : { Accept: "application/json" },
      body: init.form ?? JSON.stringify(init.json ?? {}),
      signal: controller.signal,
    })
  } catch {
    throw new ApiError("network", `${SERVICE} could not be reached. Check that it is running on port 8001.`)
  } finally {
    window.clearTimeout(timer)
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError("http", c1Message(response.status, body), { status: response.status })
  return body as T
}

export const component1Api = {
  health: (signal?: AbortSignal) =>
    component1Client.get<Component1HealthResponse>("/api/c1/health", { signal }),

  sessions: (signal?: AbortSignal) =>
    component1Client.get<Component1SessionsResponse>("/api/c1/sessions", { signal }),

  /** Re-runs session fusion on existing evidence; does not capture or upload. */
  refresh: (sessionId: string, signal?: AbortSignal) =>
    component1Client.post<Component1Report>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/refresh`,
      {},
      { signal },
    ),

  c2Payload: (sessionId: string, signal?: AbortSignal) =>
    component1Client.get<Component1Json>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/c2-payload`,
      { signal },
    ),

  report: (sessionId: string, signal?: AbortSignal) =>
    component1Client.get<Component1Report>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/report`,
      { signal },
    ),

  screeningResult: (sessionId: string, signal?: AbortSignal) =>
    component1Client.get<Component1Json>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/screening-result`,
      { signal },
    ),

  // ---- Clinical intake

  createSession: () => intake<{ session_id: string }>("/api/c1/sessions"),

  questions: (signal?: AbortSignal) =>
    component1Client.get<C1QuestionSet>("/api/c1/questionnaire/questions", { signal }),

  followups: (profile: C1Profile, answers: C1Answers) =>
    intake<{ followups: C1Question[] }>("/api/c1/questionnaire/followups", { json: { profile, answers } }),

  saveQuestionnaire: (sessionId: string, body: C1QuestionnaireBody) =>
    intake<{ status: C1CaptureStatus; answers_saved: number }>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/questionnaire`,
      { json: body },
    ),

  uploadImage: (sessionId: string, modality: keyof C1CaptureCounts, image: Blob) => {
    const form = new FormData()
    form.append("image", image, `${modality}.png`)
    return intake<{ captures: C1CaptureCounts }>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/images?modality=${modality}`,
      { form },
    )
  },

  comfortCheck: (sessionId: string, answers: Record<string, string>) =>
    intake<{ status: C1CaptureStatus }>(`/api/c1/sessions/${encodeSessionId(sessionId)}/ppg/comfort`, {
      json: { answers },
    }),

  serialPorts: (signal?: AbortSignal) =>
    component1Client.get<C1SerialPorts>("/api/c1/hardware/serial-ports", { signal }),

  recordPpg: (sessionId: string, seconds: number) =>
    intake<C1PpgSummary>(`/api/c1/sessions/${encodeSessionId(sessionId)}/ppg/record`, {
      json: { seconds },
      timeoutMs: (seconds + 60) * 1000,
    }),

  analyze: (sessionId: string) =>
    intake<Component1Report>(`/api/c1/sessions/${encodeSessionId(sessionId)}/analyze`, { timeoutMs: 300_000 }),
}
