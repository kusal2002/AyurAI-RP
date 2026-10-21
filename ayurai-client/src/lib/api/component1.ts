import { ApiError, createApiClient } from "@/lib/api/client"
import type {
  C1Answers,
  C1CaptureCounts,
  C1CaptureStatus,
  C1ImageChange,
  C1IntakeState,
  C1Patient,
  C1PatientDataStatus,
  C1PpgCaptureOptions,
  C1RegistrationBody,
  C1RegistrationResponse,
  C1PpgJob,
  C1PpgJobStatus,
  C1PpgUploadBody,
  C1RecordingResult,
  C1Profile,
  C1Question,
  C1QuestionnaireBody,
  C1QuestionSet,
  C1ReferralBody,
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
async function intake<T>(
  path: string,
  init: { json?: unknown; form?: FormData; timeoutMs?: number; method?: "GET" | "POST" | "PUT" | "DELETE" } = {},
): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), init.timeoutMs ?? 120_000)
  const method = init.method ?? "POST"
  let response: Response
  try {
    response = await fetch(`${env.c1BaseUrl}${path}`, {
      method,
      headers: init.json !== undefined ? { Accept: "application/json", "Content-Type": "application/json" } : { Accept: "application/json" },
      body: method === "GET" ? undefined : init.form ?? JSON.stringify(init.json ?? {}),
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

  /** Re-runs session fusion on existing evidence; does not capture or upload.
   *  Longer timeout: after an image change the backend re-runs the image models before fusion. */
  refresh: (sessionId: string, signal?: AbortSignal) =>
    component1Client.post<Component1Report>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/refresh`,
      {},
      { signal, timeoutMs: 120_000 },
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

  /** `replaces`: the original image is retired by the server only after this upload is saved. */
  uploadImage: (sessionId: string, modality: keyof C1CaptureCounts, image: Blob, replaces?: string) => {
    const form = new FormData()
    form.append("image", image, `${modality}.png`)
    const query = `modality=${modality}${replaces ? `&replaces=${encodeURIComponent(replaces)}` : ""}`
    return intake<C1ImageChange>(`/api/c1/sessions/${encodeSessionId(sessionId)}/images?${query}`, { form })
  },

  /** Removes one image from active evidence (the server keeps an audit copy). */
  deleteImage: (sessionId: string, imageId: string) =>
    intake<C1ImageChange>(
      `/api/c1/sessions/${encodeSessionId(sessionId)}/images/${encodeURIComponent(imageId)}`,
      { method: "DELETE" },
    ),

  imageUrl: (sessionId: string, imageId: string) =>
    `${env.c1BaseUrl}/api/c1/sessions/${encodeSessionId(sessionId)}/images/${encodeURIComponent(imageId)}`,

  comfortCheck: (sessionId: string, answers: Record<string, string>) =>
    intake<{ status: C1CaptureStatus }>(`/api/c1/sessions/${encodeSessionId(sessionId)}/ppg/comfort`, {
      json: { answers },
    }),

  serialPorts: (signal?: AbortSignal) =>
    component1Client.get<C1SerialPorts>("/api/c1/hardware/serial-ports", { signal }),

  /** Starts a background recording on the backend (single serial owner); poll ppgJob() for progress. */
  recordPpg: (sessionId: string, seconds: number) =>
    intake<C1PpgJob>(`/api/c1/sessions/${encodeSessionId(sessionId)}/ppg/record`, { json: { seconds } }),

  /** ~4 s live-signal check; nothing is saved. */
  probePpg: () => intake<C1PpgJob>("/api/c1/hardware/ppg-probe"),

  ppgJob: (signal?: AbortSignal) => component1Client.get<C1PpgJobStatus>("/api/c1/hardware/ppg-job", { signal }),

  cancelPpg: () => intake<{ cancel_requested: boolean }>("/api/c1/hardware/ppg-job/cancel"),

  /** Public: whether patient registration / PDF reports are available on this server (no personal data). */
  patientDataStatus: (signal?: AbortSignal) =>
    component1Client.get<C1PatientDataStatus>("/api/c1/patient-data/status", { signal }),

  /** Creates the coded session and its registration together; reuse request_id when retrying (no duplicates). */
  registerPatient: (body: C1RegistrationBody) => intake<C1RegistrationResponse>("/api/c1/patients/register", { json: body }),

  patient: (sessionId: string) =>
    intake<{ patient: C1Patient }>(`/api/c1/sessions/${encodeSessionId(sessionId)}/patient`, { method: "GET" }),

  updatePatient: (sessionId: string, body: { full_name: string; phone: string }) =>
    intake<{ patient: C1Patient; changed_fields: string[] }>(`/api/c1/sessions/${encodeSessionId(sessionId)}/patient`, {
      json: body,
      method: "PUT",
    }),

  /** Protected A4 PDF screening report. */
  reportPdf: async (sessionId: string): Promise<Blob> => {
    let response: Response
    try {
      response = await fetch(`${env.c1BaseUrl}/api/c1/doctor/sessions/${encodeSessionId(sessionId)}/report.pdf`, {
        headers: { Accept: "application/pdf" },
      })
    } catch {
      throw new ApiError("network", `${SERVICE} could not be reached.`)
    }
    if (!response.ok) {
      throw new ApiError("http", c1Message(response.status, await response.json().catch(() => null)), { status: response.status })
    }
    return response.blob()
  },

  ppgCaptureOptions: (signal?: AbortSignal) =>
    component1Client.get<C1PpgCaptureOptions>("/api/c1/ppg/capture-options", { signal }),

  /** Uploads a recording captured in this browser (Web Serial); retrying with the same upload_id never duplicates it. */
  uploadPpg: (sessionId: string, body: C1PpgUploadBody) =>
    intake<C1RecordingResult & { duplicate: boolean }>(`/api/c1/sessions/${encodeSessionId(sessionId)}/ppg/upload`, {
      json: body,
      timeoutMs: 120_000,
    }),

  intakeState: (sessionId: string, signal?: AbortSignal) =>
    component1Client.get<C1IntakeState>(`/api/c1/sessions/${encodeSessionId(sessionId)}/intake-state`, { signal }),

  /** Stop and refer: saves the answers given so far as a referral-only record (no risk tier). */
  referral: (sessionId: string, body: C1ReferralBody) =>
    intake<Component1Report>(`/api/c1/sessions/${encodeSessionId(sessionId)}/referral`, { json: body }),

  analyze: (sessionId: string) =>
    intake<Component1Report>(`/api/c1/sessions/${encodeSessionId(sessionId)}/analyze`, { timeoutMs: 300_000 }),
}
