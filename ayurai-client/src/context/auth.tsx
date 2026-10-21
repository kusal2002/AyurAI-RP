import * as React from "react"

import { component4Api, setAuthToken, type C4User } from "@/lib/api/component4"
import { readSession, removeSession, SESSION_KEYS, writeSession } from "@/lib/session-store"

/**
 * Sign-in state for the Component 4 JWT (proposal FR6).
 *
 * The token and user are kept in sessionStorage for this browser tab: a page
 * refresh keeps the user signed in, closing the tab signs them out, and other
 * tabs cannot see it. An expired token is dropped on load and the user is
 * signed out automatically when it expires. Every workspace page requires
 * sign-in (see RequireLiveAuth in App.tsx).
 */

type StoredAuth = { token: string; user: C4User }

type AuthContextValue = {
  user: C4User | null
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

/** Expiry time (ms since epoch) from the JWT's "exp" claim; null if unreadable. */
function tokenExpiry(token: string): number | null {
  try {
    const payload = token.split(".")[1]
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    const exp = (JSON.parse(json) as { exp?: unknown }).exp
    return typeof exp === "number" ? exp * 1000 : null
  } catch {
    return null
  }
}

function isValid(token: string): boolean {
  const expiry = tokenExpiry(token)
  return expiry !== null && expiry > Date.now()
}

/** Sign-in restored from this tab's storage, or null (also clears an expired one). */
function restoreAuth(): StoredAuth | null {
  const stored = readSession<StoredAuth>(SESSION_KEYS.auth)
  if (stored?.token && stored.user && isValid(stored.token)) return stored
  removeSession(SESSION_KEYS.auth)
  return null
}

// Restore before the first render, so the first API requests already carry the token.
const restored = restoreAuth()
setAuthToken(restored?.token ?? null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = React.useState<StoredAuth | null>(restored)

  const signIn = React.useCallback(async (username: string, password: string) => {
    const response = await component4Api.login(username, password) // throws ApiError on failure
    const next = { token: response.access_token, user: response.user }
    setAuthToken(next.token)
    writeSession(SESSION_KEYS.auth, next)
    setAuth(next)
  }, [])

  const signOut = React.useCallback(() => {
    setAuthToken(null)
    removeSession(SESSION_KEYS.auth)
    setAuth(null)
  }, [])

  // Sign out when the token expires, instead of letting every request fail with 401.
  React.useEffect(() => {
    if (!auth) return
    const expiry = tokenExpiry(auth.token)
    if (expiry === null) return
    const timer = window.setTimeout(signOut, Math.max(0, expiry - Date.now()))
    return () => window.clearTimeout(timer)
  }, [auth, signOut])

  const user = auth?.user ?? null
  const value = React.useMemo(() => ({ user, signIn, signOut }), [user, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = React.useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used inside AuthProvider")
  return context
}

export const roleLabels: Record<C4User["role"], string> = {
  practitioner: "Practitioner",
  supervisor: "Supervisor",
  researcher: "Researcher",
}
