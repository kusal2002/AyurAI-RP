import * as React from "react"
import { NavLink, Outlet, useLocation } from "react-router"
import { Leaf, LogIn, LogOut, Menu, Plus, ShieldCheck, UserRound, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { navGroupsFor, navItemFor } from "@/components/layout/nav"
import { roleLabels, useAuth } from "@/context/auth"
import { useAccess } from "@/lib/access"
import { env } from "@/lib/env"
import { cn } from "@/lib/utils"

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { allows, isPractitioner } = useAccess()
  const groups = navGroupsFor(allows)
  return (
    <>
      <nav aria-label="Main navigation" className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="mb-1.5 px-3 text-[10px] font-bold tracking-[0.15em] text-slate-400 uppercase">
              {group.title}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ label, to, icon: Icon, component }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === "/"}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition",
                        isActive
                          ? "bg-emerald-50 text-emerald-900 ring-1 ring-emerald-100"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          aria-hidden
                          size={17}
                          strokeWidth={isActive ? 2 : 1.7}
                          className={isActive ? "text-emerald-700" : "text-slate-400"}
                        />
                        <span className="flex-1 truncate">{label}</span>
                        {component && !isPractitioner && (
                          <span
                            className={cn(
                              "rounded px-1 text-[9px] font-bold tracking-wide",
                              isActive ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500",
                            )}
                          >
                            {component}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-100 p-4">
        <div className="rounded-xl bg-[#f3f8f5] p-3.5">
          <div className="flex items-center gap-2 text-emerald-800">
            <ShieldCheck aria-hidden size={16} />
            <p className="text-xs font-semibold">Decision support only</p>
          </div>
          <p className="mt-1.5 text-[11px] leading-5 text-slate-600">
            AI outputs are research decision support, not a diagnosis or prescription. A qualified
            practitioner makes every clinical decision.
          </p>
        </div>
      </div>
    </>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-700 text-white shadow-sm">
        <Leaf aria-hidden size={20} strokeWidth={1.8} />
      </div>
      <div>
        <p className="text-lg leading-tight font-bold tracking-tight text-slate-900">
          Ayur<span className="text-emerald-700">AI</span>
        </p>
        <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-400 uppercase">
          Clinical workspace
        </p>
      </div>
    </div>
  )
}

/** Signed-in Component 4 user (name, role, clinic) with sign-out, or a sign-in link. */
function UserMenu() {
  const { user, signOut } = useAuth()
  if (!user) {
    return (
      <Button variant="outline" size="sm" render={<NavLink to="/login" />} nativeButton={false}>
        <LogIn /> Sign in
      </Button>
    )
  }
  return (
    <div className="flex items-center gap-1.5">
      <span className="hidden items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-600 ring-1 ring-slate-200 ring-inset md:inline-flex">
        <UserRound aria-hidden className="size-3.5" />
        <span className="font-semibold text-slate-800">{user.username}</span>
        {roleLabels[user.role]}
        {user.clinic_id ? ` · ${user.clinic_id}` : ""}
      </span>
      <Button variant="ghost" size="icon" aria-label="Sign out" title="Sign out" onClick={signOut}>
        <LogOut />
      </Button>
    </div>
  )
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const location = useLocation()
  const current = navItemFor(location.pathname)
  const { user } = useAuth()

  React.useEffect(() => {
    if (!mobileOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [mobileOpen])

  return (
    <div className="min-h-screen bg-[#f7f9f8] text-slate-800">
      <a
        href="#main"
        className="sr-only z-[70] rounded-md bg-white px-3 py-2 text-sm font-semibold focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[260px] flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-[68px] items-center border-b border-slate-100 px-5">
          <Brand />
        </div>
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-slate-950/30"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[280px] max-w-[85vw] flex-col bg-white shadow-xl">
            <div className="flex h-[68px] items-center justify-between border-b border-slate-100 px-5">
              <Brand />
              <Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setMobileOpen(false)}>
                <X />
              </Button>
            </div>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between gap-3 border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu />
            </Button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800">{current?.label ?? "AyurAI"}</p>
              <p className="hidden truncate text-xs text-slate-400 sm:block">
                Screening · Ayurvedic reasoning · Safety · Practitioner review
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <UserMenu />
            <Button
              size="sm"
              className="hidden bg-emerald-700 hover:bg-emerald-800 sm:inline-flex"
              render={<NavLink to="/screening/new" />}
              nativeButton={false}
            >
              <Plus /> New screening
            </Button>
          </div>
        </header>

        {env.authBypass && !user && (
          <div role="status" className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900 sm:px-6">
            <strong>Sign-in bypassed (development only).</strong> Component 4 pages and decision recording still need a
            real sign-in. Remove <code>VITE_AUTH_BYPASS</code> from <code>.env.local</code> to turn this off.
          </div>
        )}

        <main id="main" className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
          <footer className="mt-10 flex flex-col gap-1 border-t border-slate-200/70 pt-4 text-[11px] text-slate-400 sm:flex-row sm:justify-between">
            <p>AyurAI · Integrated research decision-support prototype</p>
            <p>Not clinically validated · Human review required · No autonomous approval</p>
          </footer>
        </main>
      </div>
    </div>
  )
}
