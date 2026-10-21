import { CaseBar } from "@/components/shared/case"
import { PageHeader } from "@/components/shared/page"
import { SafetyKnowledgeGraph } from "./SafetyKnowledgeGraph"

export function SafetyKnowledgeGraphPage() {
  return (
    <>
      <PageHeader
        eyebrow="Component 3 · Safety knowledge graph"
        title="Safety knowledge graph"
        description="Multi-hop biochemical interaction pathways, CYP450 enzyme metabolisms, contraindications, and clinical evidence connecting Ayurvedic herbs to pharmaceutical drugs."
      />
      <CaseBar />
      <SafetyKnowledgeGraph />
    </>
  )
}

export default SafetyKnowledgeGraphPage
