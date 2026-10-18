
import { lazy, Suspense, type ReactNode } from "react"
import { Route, Routes } from "react-router"

import { AppShell } from "@/components/layout/AppShell"

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

const NewScreeningPage = lazy(() =>
  import("@/features/screening/NewScreeningPage").then((module) => ({
    default: module.NewScreeningPage,
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

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={withPageFallback(<OverviewPage />)} />
        <Route
          path="screening/new"
          element={withPageFallback(<NewScreeningPage />)}
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
        <Route
          path="candidates"
          element={withPageFallback(<CandidatesPage />)}
        />
        <Route path="safety" element={withPageFallback(<SafetyPage />)} />
        <Route path="review" element={withPageFallback(<ReviewPage />)} />
        <Route
          path="governance"
          element={withPageFallback(<GovernancePage />)}
        />
        <Route path="admin" element={withPageFallback(<AdminPage />)} />
        <Route path="*" element={withPageFallback(<NotFoundPage />)} />
      </Route>
    </Routes>
  )
}

export default App
