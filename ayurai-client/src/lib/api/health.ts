import * as React from "react"

import { isAbortError, isApiError } from "@/lib/api/client"
import { component2Api } from "@/lib/api/component2"
import { component3Api } from "@/lib/api/component3"
import { component4Api } from "@/lib/api/component4"
import type { ReadinessResponse } from "@/lib/api/types"

export type ServiceState = "loading" | "online" | "offline" | "degraded"

export type ServiceCheck = {
  key: "c2" | "c2-neo4j" | "c2-knowledge" | "c3" | "c4"
  label: string
  endpoint: string
  state: ServiceState
  message: string
}

const initial: ServiceCheck[] = [
  { key: "c2", label: "Component 2 reasoning API", endpoint: "GET /health", state: "loading", message: "" },
  {
    key: "c2-neo4j",
    label: "Component 2 database connectivity (Neo4j)",
    endpoint: "GET /health/readiness",
    state: "loading",
    message: "",
  },
  {
    key: "c2-knowledge",
    label: "Component 2 knowledge graph content",
    endpoint: "GET /health/readiness",
    state: "loading",
    message: "",
  },
  { key: "c3", label: "Component 3 safety API", endpoint: "GET /health", state: "loading", message: "" },
  { key: "c4", label: "Component 4 governance API", endpoint: "GET /health", state: "loading", message: "" },
]

const connectivityMessages: Record<string, string> = {
  healthy: "Connected (read-only check). This does not show that the graph holds knowledge.",
  not_configured: "Database settings are missing on the server",
  misconfigured: "Database settings are invalid on the server",
  auth_failed: "Database rejected the server's credentials",
  unreachable: "Database server could not be reached",
  query_failed: "Database answered but the read query failed",
}

function errorMessage(error: unknown): string {
  return isApiError(error) ? error.message : "Unavailable"
}

/** Readiness splits connectivity from content; neither implies valid recommendations. */
export function readinessChecks(readiness: ReadinessResponse): Pick<ServiceCheck, "state" | "message">[] {
  const { database_connectivity: db, knowledge_graph_content: content } = readiness.components
  const connectivity: Pick<ServiceCheck, "state" | "message"> = {
    state: db.status === "healthy" ? "online" : "offline",
    message: connectivityMessages[db.status] ?? db.status,
  }
  const claims = content.node_counts?.Claim
  const knowledge: Pick<ServiceCheck, "state" | "message"> =
    content.status === "populated"
      ? { state: "online", message: `${claims ?? 0} approved claim(s) stored; correctness is not assessed here` }
      : content.status === "provisional_only"
        ? {
            state: "degraded",
            message: `No approved claims; ${content.node_counts?.ProvisionalClaim ?? 0} unverified provisional claim(s) usable in research scope only`,
          }
        : content.status === "empty"
          ? { state: "degraded", message: "Empty: no approved claims, so reasoning will abstain" }
        : { state: "offline", message: "Unknown: database unavailable" }
  return [connectivity, knowledge]
}

/** Health checks send no patient data. Only enabled in live mode. */
export function useServiceHealth(enabled: boolean) {
  const [checks, setChecks] = React.useState<ServiceCheck[]>(initial)
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    const update = (key: ServiceCheck["key"], patch: Partial<ServiceCheck>) =>
      setChecks((current) => current.map((check) => (check.key === key ? { ...check, ...patch } : check)))

    const run = async (key: ServiceCheck["key"], call: () => Promise<{ status: string }>) => {
      try {
        const result = await call()
        update(key, {
          state: result.status === "healthy" ? "online" : "degraded",
          message: `Reported status: ${result.status}`,
        })
      } catch (error) {
        if (isAbortError(error)) return
        update(key, {
          state: isApiError(error) && error.kind === "unavailable" ? "degraded" : "offline",
          message: errorMessage(error),
        })
      }
    }

    const runReadiness = async () => {
      try {
        const readiness = await component2Api.readiness(controller.signal)
        const [connectivity, knowledge] = readinessChecks(readiness)
        update("c2-neo4j", connectivity)
        update("c2-knowledge", knowledge)
      } catch (error) {
        if (isAbortError(error)) return
        const failed = { state: "offline" as const, message: errorMessage(error) }
        update("c2-neo4j", failed)
        update("c2-knowledge", failed)
      }
    }

    void run("c2", () => component2Api.health(controller.signal))
    void runReadiness()
    void run("c3", () => component3Api.health(controller.signal))
    void run("c4", () => component4Api.health(controller.signal))
    return () => controller.abort()
  }, [enabled, tick])

  return {
    checks,
    refresh: () => {
      setChecks(initial)
      setTick((value) => value + 1)
    },
  }
}

export type ReadinessState =
  | { status: "idle" | "loading" }
  | { status: "success"; data: ReadinessResponse }
  | { status: "error"; message: string }

/** Full Component 2 readiness report for the administration page. */
export function useC2Readiness(enabled: boolean) {
  const [state, setState] = React.useState<ReadinessState>({ status: "loading" })
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    component2Api
      .readiness(controller.signal)
      .then((data) => setState({ status: "success", data }))
      .catch((error: unknown) => {
        if (isAbortError(error)) return
        setState({ status: "error", message: errorMessage(error) })
      })
    return () => controller.abort()
  }, [enabled, tick])

  return {
    state,
    refresh: () => {
      setState({ status: "loading" })
      setTick((value) => value + 1)
    },
  }
}
