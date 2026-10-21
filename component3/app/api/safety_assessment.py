import json
from pathlib import Path
from fastapi import APIRouter
from app.models.c2_input import C2CandidatePackage
from app.models.patient_context import PatientContext
from app.models.safety_output import SafetyAssessmentReport
from app.core.safety_classifier import SafetyClassifier

router = APIRouter(
    prefix="/api/v1/safety",
    tags=["Safety Assessment & Knowledge"]
)

classifier = SafetyClassifier()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@router.get("/herbs")
def get_supported_herbs():
    """Returns curated Ayurvedic herbs database."""
    with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/drugs")
def get_supported_drugs():
    """Returns commonly prescribed pharmaceutical drugs database."""
    with open(DATA_DIR / "pharma_drugs.json", "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/known-interactions")
def get_known_interactions():
    """Returns verified herb-drug interaction rules with PubMed / WHO citations."""
    with open(DATA_DIR / "known_interactions.json", "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/cyp-pathways")
def get_cyp_pathways():
    """Returns CYP450 enzyme substrate and inhibitor profiles."""
    with open(DATA_DIR / "cyp_enzymes.json", "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/graph-stats")
def get_graph_statistics():
    """Returns node and relationship statistics from Neo4j (or local graph cache)."""
    from app.core.graph_service import GraphService
    service = GraphService()
    return service.get_graph_stats()


@router.get("/graph-path")
def get_multi_hop_pathway(herb: str, drug: str):
    """Discovers multi-hop biochemical interaction pathways between an Ayurvedic herb and a pharmaceutical drug.
    Path: Herb -> Active Compound -> CYP Enzyme / Target <- Drug
    """
    from app.core.graph_service import GraphService
    service = GraphService()
    return service.find_multi_hop_path(herb, drug)
