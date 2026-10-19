import * as React from "react"

import { isAbortError, isApiError } from "@/lib/api/client"
import { component2Api } from "@/lib/api/component2"
import { component3Api } from "@/lib/api/component3"
import { component4Api } from "@/lib/api/component4"

export type ServiceCheck = {
  key: "c2" | "c2-neo4j" | "c3" | "c4"
  label: string
  endpoint: string
  state: "loading" | "online" | "offline" | "degraded"
  message: string
}

const initial: ServiceCheck[] = [
  { key: "c2", label: "Component 2 reasoning API", endpoint: "GET /health", state: "loading", message: "" },
  { key: "c2-neo4j", label: "Component 2 knowledge graph (Neo4j)", endpoint: "GET /health/neo4j", state: "loading", message: "" },
  { key: "c3", label: "Component 3 safety API", endpoint: "GET /health", state: "loading", message: "" },
  { key: "c4", label: "Component 4 governance API", endpoint: "GET /health", state: "loading", message: "" },
]

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
          message: isApiError(error) ? error.message : "Unavailable",
        })
      }
    }

    void run("c2", () => component2Api.health(controller.signal))
    void run("c2-neo4j", () => component2Api.neo4jHealth(controller.signal))
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
