import { Route, Routes } from "react-router"

import { AppShell } from "@/components/layout/AppShell"
import { AdminPage } from "@/features/admin/AdminPage"
import { AnalysisPage } from "@/features/ayurvedic-analysis/AnalysisPage"
import { PatientCasesPage } from "@/features/cases/PatientCasesPage"
import { OverviewPage } from "@/features/dashboard/OverviewPage"
import { EvidencePage } from "@/features/evidence/EvidencePage"
import { GovernancePage } from "@/features/governance/GovernancePage"
import { KnowledgeGraphPage } from "@/features/knowledge-graph/KnowledgeGraphPage"
import { NotFoundPage } from "@/features/admin/NotFoundPage"
import { ReviewPage } from "@/features/practitioner-review/ReviewPage"
import { CandidatesPage } from "@/features/recommendations/CandidatesPage"
import { SafetyPage } from "@/features/safety/SafetyPage"
import { NewScreeningPage } from "@/features/screening/NewScreeningPage"
import { ScreeningRecordsPage } from "@/features/screening/ScreeningRecordsPage"

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="screening/new" element={<NewScreeningPage />} />
        <Route path="screenings" element={<ScreeningRecordsPage />} />
        <Route path="cases" element={<PatientCasesPage />} />
        <Route path="analysis" element={<AnalysisPage />} />
        <Route path="knowledge-graph" element={<KnowledgeGraphPage />} />
        <Route path="evidence" element={<EvidencePage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="safety" element={<SafetyPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="governance" element={<GovernancePage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
