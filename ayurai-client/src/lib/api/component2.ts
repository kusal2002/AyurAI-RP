import { createApiClient } from "@/lib/api/client"
import type {
  C1Input,
  C1ReasoningResponse,
  C1ScreeningPayload,
  C1IntakeResponse,
  Component2Output,
  Component2ReasoningRequest,
  HealthResponse,
  KnowledgeScope,
  ResearchKnowledgeResponse,
  Neo4jHealthResponse,
  ReadinessResponse,
  PractitionerFeedbackRequest,
  PractitionerFeedbackResponse,
} from "@/lib/api/types"
import { env } from "@/lib/env"

/** Component 2 FastAPI service (component2/app/main.py). */
export const component2Client = createApiClient("Component 2 reasoning service", env.c2BaseUrl)

/** Query string for the knowledge scope; the default (approved) sends nothing. */
function scopeQuery(scope: KnowledgeScope = "approved") {
  return scope === "approved" ? "" : `?knowledge_scope=${scope}`
}

export const component2Api = {
  health: (signal?: AbortSignal) =>
    component2Client.get<HealthResponse>("/health", { signal }),

  neo4jHealth: (signal?: AbortSignal) =>
    component2Client.get<Neo4jHealthResponse>("/health/neo4j", { signal }),

  /** GET /health/readiness - connectivity, schema, content, ingestion, retrieval, model. */
  readiness: (signal?: AbortSignal) =>
    component2Client.get<ReadinessResponse>("/health/readiness", { signal }),

  /** POST /api/v1/c2/reasoning - full structured reasoning output. */
  reason: (request: Component2ReasoningRequest, signal?: AbortSignal, scope?: KnowledgeScope) =>
    component2Client.post<Component2Output>(`/api/v1/c2/reasoning${scopeQuery(scope)}`, request, {
      signal,
      timeoutMs: env.reasoningTimeoutMs,
    }),

  /**
   * POST /api/v1/c1/reasoning - full Component 1 screening payload. The
   * service maps symptom names to knowledge-graph IDs (never guessing) and
   * runs reasoning only when at least one present symptom resolves.
   */
  reasonFromScreening: (payload: C1ScreeningPayload, signal?: AbortSignal, scope?: KnowledgeScope) =>
    component2Client.post<C1ReasoningResponse>(`/api/v1/c1/reasoning${scopeQuery(scope)}`, payload, {
      signal,
      timeoutMs: env.reasoningTimeoutMs,
    }),

  /** GET /api/v1/c2/research/knowledge - provisional (unverified) claims, read-only. */
  researchKnowledge: (signal?: AbortSignal, category?: string) =>
    component2Client.get<ResearchKnowledgeResponse>(
      `/api/v1/c2/research/knowledge?limit=500${category ? `&category=${encodeURIComponent(category)}` : ""}`,
      { signal },
    ),

  /** POST /api/v1/c2/feedback - append-only practitioner feedback record. */
  submitFeedback: (feedback: PractitionerFeedbackRequest, signal?: AbortSignal) =>
    component2Client.post<PractitionerFeedbackResponse>("/api/v1/c2/feedback", feedback, {
      signal,
      timeoutMs: env.reasoningTimeoutMs,
    }),
}

/**
 * Component 1 intake endpoint hosted by the Component 2 service.
 * It validates the payload and echoes it back; it does not run a model.
 */
export const component1IntakeApi = {
  validateScreeningResult: (input: C1Input, signal?: AbortSignal) =>
    component2Client.post<C1IntakeResponse>("/api/v1/c1/screening-result", input, { signal }),
}
