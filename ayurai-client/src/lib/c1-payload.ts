import type { C1ScreeningPayload } from "@/lib/api/types"

/** Light structural check; the Component 2 service validates the full contract. */
export function looksLikePayload(value: unknown): value is C1ScreeningPayload {
  if (typeof value !== "object" || value === null) return false
  const record = value as Record<string, unknown>
  const result = record.screening_result as Record<string, unknown> | undefined
  return (
    typeof record.screening_id === "string" &&
    typeof result?.risk_level === "string" &&
    Array.isArray(record.symptoms)
  )
}

/**
 * Accepts one payload, an array, {payloads: [...]}, {scenarios: [{payload}]}
 * or an object of named payloads such as {high_risk: {...}, low_risk: {...}}.
 */
export function extractPayloads(parsed: unknown): { payloads: C1ScreeningPayload[]; rejected: number } {
  let items: unknown[] = []
  if (Array.isArray(parsed)) items = parsed
  else if (typeof parsed === "object" && parsed !== null) {
    const record = parsed as Record<string, unknown>
    if (Array.isArray(record.payloads)) items = record.payloads
    else if (Array.isArray(record.scenarios))
      items = (record.scenarios as Record<string, unknown>[]).map((item) => item.payload)
    else if (looksLikePayload(parsed)) items = [parsed]
    else if (Object.values(record).some(looksLikePayload)) items = Object.values(record)
    else items = [parsed]
  }
  const payloads = items.filter(looksLikePayload)
  return { payloads, rejected: items.length - payloads.length }
}
