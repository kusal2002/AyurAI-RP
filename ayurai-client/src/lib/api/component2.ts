import { createApiClient } from "@/lib/api/client"
import type {
  C1Input,
  C1IntakeResponse,
  Component2Output,
  Component2ReasoningRequest,
  HealthResponse,
  Neo4jHealthResponse,
  PractitionerFeedbackRequest,
  PractitionerFeedbackResponse,
} from "@/lib/api/types"
import { env } from "@/lib/env"

/** Component 2 FastAPI service (component2/app/main.py). */
export const component2Client = createApiClient("Component 2 reasoning service", env.c2BaseUrl)

export const component2Api = {
  health: (signal?: AbortSignal) =>
    component2Client.get<HealthResponse>("/health", { signal }),

  neo4jHealth: (signal?: AbortSignal) =>
    component2Client.get<Neo4jHealthResponse>("/health/neo4j", { signal }),

  /** POST /api/v1/c2/reasoning - full structured reasoning output. */
  reason: (request: Component2ReasoningRequest, signal?: AbortSignal) =>
    component2Client.post<Component2Output>("/api/v1/c2/reasoning", request, {
      signal,
      timeoutMs: env.reasoningTimeoutMs,
    }),

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
