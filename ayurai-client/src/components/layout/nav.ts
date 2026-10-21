import {
  Activity,
  ClipboardCheck,
  FileInput,
  FileSearch,
  FlaskConical,
  FolderOpen,
  GitMerge,
  LayoutDashboard,
  Leaf,
  ListOrdered,
  LockKeyhole,
  Network,
  ScrollText,
  Settings2,
  Share2,
  ShieldCheck,
  Stethoscope,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import type { C4Role } from "@/lib/api/component4"

export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  /** Which research component owns the screen, shown as a small tag. */
  component?: "C1" | "C2" | "C3" | "C4"
  /** Roles that see this screen; leave out for every signed-in role. */
  roles?: C4Role[]
}

// Who sees what (see lib/access.ts). Practitioners get the clinical workflow;
// research, knowledge-base and governance screens are for supervisors/researchers.
const STAFF: C4Role[] = ["supervisor", "researcher"]
const CLINICAL: C4Role[] = ["practitioner", "supervisor"]
const SUPERVISOR: C4Role[] = ["supervisor"]

export const navGroups: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { label: "Overview", to: "/", icon: LayoutDashboard },
      { label: "New screening", to: "/screening/new", icon: Stethoscope, component: "C1" },
      { label: "Import C1 output", to: "/screening/import", icon: FileInput, component: "C2", roles: STAFF },
      { label: "Screening records", to: "/screenings", icon: Activity, component: "C1" },
      { label: "Patient cases", to: "/cases", icon: FolderOpen },
    ],
  },
  {
    title: "Ayurvedic reasoning",
    items: [
      { label: "Ayurvedic analysis", to: "/analysis", icon: Leaf, component: "C2" },
      { label: "Knowledge graph", to: "/knowledge-graph", icon: Network, component: "C2", roles: STAFF },
      { label: "Evidence explorer", to: "/evidence", icon: FileSearch, component: "C2", roles: STAFF },
      { label: "Research knowledge (unverified)", to: "/research-knowledge", icon: FlaskConical, component: "C2", roles: STAFF },
      { label: "Recommendation candidates", to: "/candidates", icon: ListOrdered, component: "C2" },
    ],
  },
  {
    title: "Safety & review",
    items: [
      { label: "Safety assessment", to: "/safety", icon: ShieldCheck, component: "C3" },
      { label: "Practitioner review", to: "/review", icon: ClipboardCheck, component: "C4", roles: CLINICAL },
    ],
  },
  {
    title: "Governance",
    items: [
      { label: "Federated training", to: "/federation", icon: Share2, component: "C4", roles: STAFF },
      { label: "Privacy budget", to: "/privacy", icon: LockKeyhole, component: "C4", roles: STAFF },
      { label: "Knowledge federation", to: "/fakl", icon: GitMerge, component: "C4", roles: STAFF },
      { label: "Audit & governance", to: "/governance", icon: ScrollText, component: "C4", roles: SUPERVISOR },
      { label: "Administration", to: "/admin", icon: Settings2, roles: SUPERVISOR },
    ],
  },
]

export const allNavItems = navGroups.flatMap((group) => group.items)

/** Navigation for one role: hidden screens and empty groups removed. */
export function navGroupsFor(allows: (roles: C4Role[] | undefined) => boolean) {
  return navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => allows(item.roles)) }))
    .filter((group) => group.items.length > 0)
}

/** Roles allowed on a route path (undefined = every signed-in role). */
export function rolesForPath(path: string): C4Role[] | undefined {
  return allNavItems.find((item) => item.to === path)?.roles
}

export function navItemFor(pathname: string): NavItem | undefined {
  if (pathname === "/") return allNavItems[0]
  return allNavItems
    .filter((item) => item.to !== "/" && pathname.startsWith(item.to))
    .sort((a, b) => b.to.length - a.to.length)[0]
}
