function readNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "")
}

export const env = {
  c2BaseUrl: trimTrailingSlash(import.meta.env.VITE_C2_API_BASE_URL || "/c2-api"),
  c3BaseUrl: trimTrailingSlash(import.meta.env.VITE_C3_API_BASE_URL || "/c3-api"),
  c4BaseUrl: trimTrailingSlash(import.meta.env.VITE_C4_API_BASE_URL || "/c4-api"),
  timeoutMs: readNumber(import.meta.env.VITE_API_TIMEOUT_MS, 20_000),
  reasoningTimeoutMs: readNumber(
    import.meta.env.VITE_C2_REASONING_TIMEOUT_MS,
    180_000,
  ),
  // Development only: skip the Component 4 sign-in page. Ignored in production builds.
  authBypass: import.meta.env.DEV && import.meta.env.VITE_AUTH_BYPASS === "true",
}
