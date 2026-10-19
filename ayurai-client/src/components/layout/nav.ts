import {
  Activity,
  ClipboardCheck,
  FileSearch,
  FolderOpen,
  LayoutDashboard,
  Leaf,
  ListOrdered,
  Network,
  ScrollText,
  Settings2,
  ShieldCheck,
  Stethoscope,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  /** Which research component owns the screen, shown as a small tag. */
  component?: "C1" | "C2" | "C3" | "C4"
}

export const navGroups: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { label: "Overview", to: "/", icon: LayoutDashboard },
      { label: "New screening", to: "/screening/new", icon: Stethoscope, component: "C1" },
      { label: "Screening records", to: "/screenings", icon: Activity, component: "C1" },
      { label: "Patient cases", to: "/cases", icon: FolderOpen },
    ],
  },
  {
    title: "Ayurvedic reasoning",
    items: [
      { label: "Ayurvedic analysis", to: "/analysis", icon: Leaf, component: "C2" },
      { label: "Knowledge graph", to: "/knowledge-graph", icon: Network, component: "C2" },
      { label: "Evidence explorer", to: "/evidence", icon: FileSearch, component: "C2" },
      { label: "Recommendation candidates", to: "/candidates", icon: ListOrdered, component: "C2" },
    ],
  },
  {
    title: "Safety & review",
    items: [
      { label: "Safety assessment", to: "/safety", icon: ShieldCheck, component: "C3" },
      { label: "Practitioner review", to: "/review", icon: ClipboardCheck, component: "C4" },
    ],
  },
  {
    title: "Governance",
    items: [
      { label: "Audit & governance", to: "/governance", icon: ScrollText, component: "C4" },
      { label: "Administration", to: "/admin", icon: Settings2 },
    ],
  },
]

export const allNavItems = navGroups.flatMap((group) => group.items)

export function navItemFor(pathname: string): NavItem | undefined {
  if (pathname === "/") return allNavItems[0]
  return allNavItems
    .filter((item) => item.to !== "/" && pathname.startsWith(item.to))
    .sort((a, b) => b.to.length - a.to.length)[0]
}
