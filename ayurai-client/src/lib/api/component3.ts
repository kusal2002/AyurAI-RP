import { createApiClient } from "@/lib/api/client"
import type {
  C2SafetyEvaluationRequest,
  C3CypPathway,
  C3Drug,
  C3GraphResponse,
  C3Herb,
  C3KnownInteraction,
  HealthResponse,
  SafetyAssessmentReport,
} from "@/lib/api/types"
import { env } from "@/lib/env"

/** Component 3 FastAPI safety service (component3/app/main.py). */
export const component3Client = createApiClient("Component 3 safety service", env.c3BaseUrl)

export const component3Api = {
  health: (signal?: AbortSignal) =>
    component3Client.get<HealthResponse>("/health", { signal }),

  /** POST /api/v1/c2/safety-evaluation */
  evaluate: (request: C2SafetyEvaluationRequest, signal?: AbortSignal) =>
    component3Client.post<SafetyAssessmentReport>("/api/v1/c2/safety-evaluation", request, {
      signal,
    }),

  herbs: (signal?: AbortSignal) =>
    component3Client.get<C3Herb[]>("/api/v1/safety/herbs", { signal }),
  drugs: (signal?: AbortSignal) =>
    component3Client.get<C3Drug[]>("/api/v1/safety/drugs", { signal }),
  knownInteractions: (signal?: AbortSignal) =>
    component3Client.get<C3KnownInteraction[]>("/api/v1/safety/known-interactions", { signal }),
  cypPathways: (signal?: AbortSignal) =>
    component3Client.get<C3CypPathway[]>("/api/v1/safety/cyp-pathways", { signal }),
  graphStats: (signal?: AbortSignal) =>
    component3Client.get<Record<string, unknown>>("/api/v1/safety/graph-stats", { signal }),
  benchmarks: (signal?: AbortSignal) =>
    component3Client.get<Record<string, unknown>>("/api/v1/safety/benchmarks", { signal }),

  /** GET /api/v1/safety/subgraph */
  subgraph: (
    params?: { herb?: string; drug?: string; severity?: string; limit?: number },
    signal?: AbortSignal,
  ) => {
    const search = new URLSearchParams()
    if (params?.herb) search.set("herb", params.herb)
    if (params?.drug) search.set("drug", params.drug)
    if (params?.severity) search.set("severity", params.severity)
    if (params?.limit) search.set("limit", String(params.limit))
    const query = search.toString()
    return component3Client.get<C3GraphResponse>(
      `/api/v1/safety/subgraph${query ? `?${query}` : ""}`,
      { signal },
    )
  },

  /** GET /api/v1/safety/graph-path */
  graphPath: (herb: string, drug: string, signal?: AbortSignal) => {
    const search = new URLSearchParams({ herb, drug })
    return component3Client.get<Record<string, unknown>>(
      `/api/v1/safety/graph-path?${search.toString()}`,
      { signal },
    )
  },
}
