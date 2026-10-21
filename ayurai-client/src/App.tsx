
import { lazy, Suspense, type ReactNode } from "react"
import { Link, Navigate, Outlet, Route, Routes, useLocation } from "react-router"
import { LockKeyhole } from "lucide-react"

import { AppShell } from "@/components/layout/AppShell"
import { rolesForPath } from "@/components/layout/nav"
import { EmptyState, Panel } from "@/components/shared/page"
import { Button } from "@/components/ui/button"
import { roleLabels, useAuth } from "@/context/auth"
import { useAccess } from "@/lib/access"
import { env } from "@/lib/env"

const LoginPage = lazy(() =>
  import("@/features/auth/LoginPage").then((module) => ({
    default: module.LoginPage,
  })),
)

const FederationPage = lazy(() =>
  import("@/features/federation/FederationPage").then((module) => ({
    default: module.FederationPage,
  })),
)

const FaklPage = lazy(() =>
  import("@/features/fakl/FaklPage").then((module) => ({
    default: module.FaklPage,
  })),
)

const PrivacyPage = lazy(() =>
  import("@/features/federation/PrivacyPage").then((module) => ({
    default: module.PrivacyPage,
  })),
)

const AdminPage = lazy(() =>
  import("@/features/admin/AdminPage").then((module) => ({
    default: module.AdminPage,
  })),
)

const NotFoundPage = lazy(() =>
  import("@/features/admin/NotFoundPage").then((module) => ({
    default: module.NotFoundPage,
  })),
)

const AnalysisPage = lazy(() =>
  import("@/features/ayurvedic-analysis/AnalysisPage").then((module) => ({
    default: module.AnalysisPage,
  })),
)

const PatientCasesPage = lazy(() =>
  import("@/features/cases/PatientCasesPage").then((module) => ({
    default: module.PatientCasesPage,
  })),
)

const OverviewPage = lazy(() =>
  import("@/features/dashboard/OverviewPage").then((module) => ({
    default: module.OverviewPage,
  })),
)

const EvidencePage = lazy(() =>
  import("@/features/evidence/EvidencePage").then((module) => ({
    default: module.EvidencePage,
  })),
)

const GovernancePage = lazy(() =>
  import("@/features/governance/GovernancePage").then((module) => ({
    default: module.GovernancePage,
  })),
)

const KnowledgeGraphPage = lazy(() =>
  import("@/features/knowledge-graph/KnowledgeGraphPage").then((module) => ({
    default: module.KnowledgeGraphPage,
  })),
)

const ReviewPage = lazy(() =>
  import("@/features/practitioner-review/ReviewPage").then((module) => ({
    default: module.ReviewPage,
  })),
)

const CandidatesPage = lazy(() =>
  import("@/features/recommendations/CandidatesPage").then((module) => ({
    default: module.CandidatesPage,
  })),
)

const SafetyPage = lazy(() =>
  import("@/features/safety/SafetyPage").then((module) => ({
    default: module.SafetyPage,
  })),
)

const SafetyKnowledgeGraphPage = lazy(() =>
  import("@/features/safety/SafetyKnowledgeGraphPage").then((module) => ({
    default: module.SafetyKnowledgeGraphPage,
  })),
)

const NewScreeningPage = lazy(() =>
  import("@/features/screening/NewScreeningPage").then((module) => ({
    default: module.NewScreeningPage,
  })),
)

const ImportC1Page = lazy(() =>
  import("@/features/screening/ImportC1Page").then((module) => ({
    default: module.ImportC1Page,
  })),
)

const ResearchKnowledgePage = lazy(() =>
  import("@/features/knowledge-graph/ResearchKnowledgePage").then((module) => ({
    default: module.ResearchKnowledgePage,
  })),
)
const ScreeningRecordsPage = lazy(() =>
  import("@/features/screening/ScreeningRecordsPage").then((module) => ({
    default: module.ScreeningRecordsPage,
  })),
)

function PageLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[240px] w-full items-center justify-center p-6"
    >
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-emerald-700 border-t-transparent motion-reduce:animate-none"
        />
        Loading workspace…
      </div>
    </div>
  )
}

function withPageFallback(page: ReactNode) {
  return <Suspense fallback={<PageLoading />}>{page}</Suspense>
}

/** The workspace works with real services, so it requires a Component 4 sign-in (proposal FR6). */
function RequireLiveAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user && !env.authBypass) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

/** Shows a page only to the roles listed for it in the navigation (components/layout/nav.ts). */
function RoleGate() {
  const { allows, role } = useAccess()
  const location = useLocation()
  if (allows(rolesForPath(location.pathname))) return <Outlet />
  return (
    <Panel>
      <EmptyState
        icon={LockKeyhole}
        title="This page is not available for your role"
        description={`You are signed in as ${role ? roleLabels[role] : "a user without a role"}. This page is for other staff roles, such as supervisors or researchers.`}
        action={
          <Button variant="outline" render={<Link to="/" />} nativeButton={false}>
            Back to overview
          </Button>
        }
      />
    </Panel>
  )
}

export function App() {
  return (
    <Routes>
      <Route path="login" element={withPageFallback(<LoginPage />)} />
      <Route
        element={
          <RequireLiveAuth>
            <AppShell />
          </RequireLiveAuth>
        }
      >
        <Route element={<RoleGate />}>
        <Route index element={withPageFallback(<OverviewPage />)} />
        <Route
          path="screening/new"
          element={withPageFallback(<NewScreeningPage />)}
        />
        <Route
          path="screening/import"
          element={withPageFallback(<ImportC1Page />)}
        />
        <Route
          path="screenings"
          element={withPageFallback(<ScreeningRecordsPage />)}
        />
        <Route
          path="cases"
          element={withPageFallback(<PatientCasesPage />)}
        />
        <Route
          path="analysis"
          element={withPageFallback(<AnalysisPage />)}
        />
        <Route
          path="knowledge-graph"
          element={withPageFallback(<KnowledgeGraphPage />)}
        />
        <Route path="evidence" element={withPageFallback(<EvidencePage />)} />
        <Route path="research-knowledge" element={withPageFallback(<ResearchKnowledgePage />)} />
        <Route
          path="candidates"
          element={withPageFallback(<CandidatesPage />)}
        />
        <Route path="safety" element={withPageFallback(<SafetyPage />)} />
        <Route
          path="safety-graph"
          element={withPageFallback(<SafetyKnowledgeGraphPage />)}
        />
        <Route path="review" element={withPageFallback(<ReviewPage />)} />
        <Route
          path="governance"
          element={withPageFallback(<GovernancePage />)}
        />
        <Route
          path="federation"
          element={withPageFallback(<FederationPage />)}
        />
        <Route path="privacy" element={withPageFallback(<PrivacyPage />)} />
        <Route path="fakl" element={withPageFallback(<FaklPage />)} />
        <Route path="admin" element={withPageFallback(<AdminPage />)} />
        <Route path="*" element={withPageFallback(<NotFoundPage />)} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
