"""FAKL (Federated Ayurvedic Knowledge Learning) — readiness of its data source.

FAKL itself is scheduled for a later iteration (proposal SO3). This endpoint only
READS Component 2's knowledge graph to report whether the inputs FAKL needs exist:
claims with a confidence value, and practitioner feedback that says which clinic
it came from. It never writes to Component 2's database.
"""

from fastapi import APIRouter, Depends
from neo4j import GraphDatabase

from models import User
from security import get_current_user
from settings import C2_NEO4J_DATABASE, C2_NEO4J_PASSWORD, C2_NEO4J_URI, C2_NEO4J_USERNAME

router = APIRouter(prefix="/api/v1/c4/fakl", tags=["FAKL (planned)"])


def _count_inputs(tx):
    """Counts only — no claim text, no feedback text, no reviewer details."""
    return tx.run(
        """
        CALL () { MATCH (c:Claim) RETURN count(c) AS claims, count(c.confidence) AS claims_with_confidence }
        CALL () { MATCH (f:PractitionerFeedback)
                  RETURN count(f) AS feedback, count(f.clinic_id) AS feedback_with_clinic }
        CALL () { MATCH (:PractitionerFeedback)-[r:REVIEWS]->(:Claim) RETURN count(r) AS feedback_links }
        RETURN claims, claims_with_confidence, feedback, feedback_with_clinic, feedback_links
        """
    ).single().data()


@router.get("/status")
def fakl_status(user: User = Depends(get_current_user)):
    status = {"configured": bool(C2_NEO4J_URI and C2_NEO4J_USERNAME and C2_NEO4J_PASSWORD),
              "connected": False, "error": None, "counts": None}
    if not status["configured"]:
        status["error"] = "Component 2's knowledge-graph connection is not configured on this server."
        return status
    try:
        with GraphDatabase.driver(C2_NEO4J_URI, auth=(C2_NEO4J_USERNAME, C2_NEO4J_PASSWORD),
                                  connection_timeout=10) as driver:
            # Read-only session: the database itself rejects any write
            with driver.session(database=C2_NEO4J_DATABASE, default_access_mode="READ") as session:
                status["counts"] = session.execute_read(_count_inputs)
        status["connected"] = True
    except Exception:
        # Fixed message: the original error could contain the database address
        status["error"] = "Could not read Component 2's knowledge graph (offline, paused or credentials changed)."
    return status
