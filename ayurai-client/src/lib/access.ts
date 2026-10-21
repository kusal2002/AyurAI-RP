import * as React from "react"

import { useAuth } from "@/context/auth"
import type { C4Role } from "@/lib/api/component4"
import { env } from "@/lib/env"
import { readSession, writeSession } from "@/lib/session-store"

/**
 * What each signed-in role sees in the interface.
 *
 * - practitioner (Ayurvedic doctor): the clinical workflow with clean summaries.
 * - supervisor: everything, plus a "Technical details" switch on case screens.
 * - researcher: research and knowledge screens and the technical details.
 *
 * This only shapes the interface. The services enforce their own rules (for
 * example, Component 4 decides who may record decisions).
 */

/** Roles that may switch on the technical view (IDs, claims, evidence policy, retrieval). */
const TECHNICAL_ROLES: C4Role[] = ["supervisor", "researcher"]

export function useAccess() {
  const { user } = useAuth()
  // Development sign-in bypass has no user: show everything, like a supervisor.
  const role: C4Role | null = user?.role ?? (env.authBypass ? "supervisor" : null)
  return React.useMemo(
    () => ({
      role,
      isPractitioner: role === "practitioner",
      canUseTechnicalView: role !== null && TECHNICAL_ROLES.includes(role),
      allows: (roles: C4Role[] | undefined) => !roles || (role !== null && roles.includes(role)),
    }),
    [role],
  )
}

const TECHNICAL_VIEW_KEY = "ayurai.view.technical.v1"

// One shared value, so every component using the switch updates together.
let technicalView = readSession<boolean>(TECHNICAL_VIEW_KEY) === true
const listeners = new Set<() => void>()

function setTechnicalView(on: boolean) {
  technicalView = on
  writeSession(TECHNICAL_VIEW_KEY, on)
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * The "Technical details" switch, remembered for this browser tab.
 * Always off for roles that may not use it.
 */
export function useTechnicalView(): [boolean, (on: boolean) => void] {
  const { canUseTechnicalView } = useAccess()
  const on = React.useSyncExternalStore(subscribe, () => technicalView)
  return [canUseTechnicalView && on, setTechnicalView]
}
