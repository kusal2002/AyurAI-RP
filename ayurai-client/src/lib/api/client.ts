import { env } from "@/lib/env"

export type ApiErrorKind =
  | "network"
  | "timeout"
  | "aborted"
  | "http"
  | "validation"
  | "unavailable"
  | "parse"
  | "unauthorized"
  | "forbidden"

/** Error raised by the API layer. Messages are safe to show to users. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  /** Field-level validation messages (field path + message, never values). */
  readonly details: string[]

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number; details?: string[] } = {},
  ) {
    super(message)
    this.name = "ApiError"
    this.kind = kind
    this.status = options.status
    this.details = options.details ?? []
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function isAbortError(error: unknown): boolean {
  return isApiError(error) && error.kind === "aborted"
}

type RequestOptions = {
  method?: "GET" | "POST"
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
}

type FastApiValidationItem = { loc?: unknown[]; msg?: unknown }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

/** Extract validation messages from a FastAPI 422 body without echoing input values. */
function validationDetails(body: unknown): string[] {
  if (!isRecord(body) || !Array.isArray(body.detail)) return []
  return (body.detail as FastApiValidationItem[]).map((item) => {
    const location = Array.isArray(item.loc)
      ? item.loc.filter((part) => part !== "body").join(".")
      : "request"
    const message = typeof item.msg === "string" ? item.msg : "Invalid value"
    return `${location || "request"}: ${message}`
  })
}

function unavailableDependency(body: unknown): string | null {
  if (!isRecord(body) || !isRecord(body.detail)) return null
  const dependency = body.detail.dependency ?? body.detail.database
  return typeof dependency === "string" ? dependency : null
}

const dependencyLabels: Record<string, string> = {
  knowledge_graph: "the knowledge graph database",
  neo4j: "the knowledge graph database",
  embedding_model: "the embedding model",
  blockchain: "the Ethereum Sepolia connection",
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

function httpError(serviceName: string, status: number, body: unknown): ApiError {
  if (status === 422) {
    return new ApiError(
      "validation",
      `${serviceName} rejected the request because some fields are invalid.`,
      { status, details: validationDetails(body) },
    )
  }
  if (status === 503) {
    const dependency = unavailableDependency(body)
    const label = dependency ? dependencyLabels[dependency] ?? dependency : null
    return new ApiError(
      "unavailable",
      label
        ? `${serviceName} is running, but ${label} is unavailable.`
        : `${serviceName} is temporarily unavailable.`,
      { status },
    )
  }
  if (status === 401) {
    return new ApiError("unauthorized", `${serviceName}: your session is missing or has expired. Sign in again.`, {
      status,
    })
  }
  if (status === 403) {
    return new ApiError("forbidden", `${serviceName}: your role is not allowed to do this.`, { status })
  }
  if (status === 409) {
    return new ApiError("http", `${serviceName} reported a conflict (duplicate record).`, {
      status,
    })
  }
  if (status === 404) {
    return new ApiError("http", `${serviceName} does not provide this endpoint.`, { status })
  }
  if (status >= 500) {
    return new ApiError(
      "http",
      `${serviceName} encountered an internal error (HTTP ${status}).`,
      { status },
    )
  }
  return new ApiError("http", `${serviceName} returned HTTP ${status}.`, { status })
}

/**
 * Minimal JSON client shared by the component API modules.
 * - JSON request/response handling
 * - timeout plus caller-supplied cancellation
 * - typed, user-safe errors (no response bodies or patient data are logged)
 * - optional bearer token (Component 4 JWT); services without auth pass none
 */
export function createApiClient(
  serviceName: string,
  baseUrl: string,
  getToken?: () => string | null,
) {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const controller = new AbortController()
    const timeoutMs = options.timeoutMs ?? env.timeoutMs
    let timedOut = false
    const timer = window.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)

    const onCallerAbort = () => controller.abort()
    if (options.signal) {
      if (options.signal.aborted) controller.abort()
      else options.signal.addEventListener("abort", onCallerAbort, { once: true })
    }

    const token = getToken?.() ?? null

    let response: Response
    try {
      response = await fetch(`${baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers: {
          Accept: "application/json",
          ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
        credentials: "same-origin",
      })
    } catch {
      if (timedOut) {
        throw new ApiError(
          "timeout",
          `${serviceName} did not respond within ${Math.round(timeoutMs / 1000)} seconds.`,
        )
      }
      if (controller.signal.aborted) {
        throw new ApiError("aborted", "The request was cancelled.")
      }
      throw new ApiError(
        "network",
        `${serviceName} could not be reached. Check that the service is running and the API URL is configured.`,
      )
    } finally {
      window.clearTimeout(timer)
      options.signal?.removeEventListener("abort", onCallerAbort)
    }

    const body = await parseBody(response).catch(() => null)

    // The Vite proxy answers 502/504 when the upstream service is not running.
    if (response.status === 502 || response.status === 504) {
      throw new ApiError(
        "network",
        `${serviceName} could not be reached through the development proxy. Check that the service is running.`,
        { status: response.status },
      )
    }
    if (!response.ok) throw httpError(serviceName, response.status, body)
    if (body === null || typeof body === "string") {
      throw new ApiError("parse", `${serviceName} returned a response that is not valid JSON.`)
    }
    return body as T
  }

  return {
    serviceName,
    baseUrl,
    get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
      request<T>(path, { ...options, method: "GET" }),
    post: <T>(path: string, body: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
      request<T>(path, { ...options, method: "POST", body }),
  }
}

export type ApiClient = ReturnType<typeof createApiClient>

export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message
  return "An unexpected error occurred."
}
