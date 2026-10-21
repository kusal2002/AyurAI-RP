import * as React from "react"

import { component4Api, setAuthToken, type C4User } from "@/lib/api/component4"

/**
 * Sign-in state for the Component 4 JWT (proposal FR6).
 *
 * The token is kept in memory only: reloading the page signs the user out.
 * Every workspace page requires sign-in (see RequireLiveAuth in App.tsx).
 */

type AuthContextValue = {
  user: C4User | null
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<C4User | null>(null)

  const signIn = React.useCallback(async (username: string, password: string) => {
    const response = await component4Api.login(username, password) // throws ApiError on failure
    setAuthToken(response.access_token)
    setUser(response.user)
  }, [])

  const signOut = React.useCallback(() => {
    setAuthToken(null)
    setUser(null)
  }, [])

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
