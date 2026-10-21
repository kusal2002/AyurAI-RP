/**
 * Small JSON wrapper around sessionStorage.
 *
 * sessionStorage belongs to one browser tab: it survives a page refresh but is
 * cleared when the tab is closed, and other tabs cannot read it. Every call is
 * guarded because storage can be blocked (private windows, strict settings) or
 * full; the app then simply behaves as before (memory only).
 */

export function readSession<T>(key: string): T | null {
  try {
    const raw = window.sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function writeSession(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Blocked or full: keep working from memory only.
  }
}

export function removeSession(key: string): void {
  try {
    window.sessionStorage.removeItem(key)
  } catch {
    // Nothing to do.
  }
}

/** Storage keys, versioned so a future format change can ignore old data. */
export const SESSION_KEYS = {
  auth: "ayurai.auth.v1",
  workspace: "ayurai.workspace.v1",
} as const
