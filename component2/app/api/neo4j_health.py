"""Health, readiness and read-only graph diagnostics.

Each concern is reported separately so that a reachable database is never
presented as evidence that the knowledge graph is complete or that any
recommendation is valid:

- database_connectivity   the server answers a read-only query
- graph_schema            required constraints exist (counts only)
- knowledge_graph_content approved claims/evidence/sources in the graph
- local_corpus_ingestion  the local manifest and candidate store (counts)
- retrieval_service       the in-process evidence index
- embedding_model         configured model, loaded / cached locally
- component_integration   which upstream/downstream contracts exist

No endpoint here writes to the database, loads the embedding model, or
returns credentials, host names or source text.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from neo4j import READ_ACCESS, NotificationMinimumSeverity, unit_of_work
from neo4j.exceptions import DriverError, Neo4jError

from app.db.graph_validation import (
    CORE_CONSTRAINTS,
    STAGE_E_CONSTRAINTS,
    validate_graph,
)
from app.db.neo4j import check_neo4j, get_neo4j_driver, query_timeout
from app.retrieval.embedding import model_cached_locally
from app.retrieval.service import get_retrieval_service

router = APIRouter(tags=["Database Health"])

COMPONENT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = COMPONENT_DIR / "corpus" / "extracted" / "manifest.json"
DEFAULT_CANDIDATES = COMPONENT_DIR / "corpus" / "extracted" / "candidates"
_CONTENT_LABELS = ("Claim", "Evidence", "DescriptiveEvidence", "Source", "SourceChunk",
                   "Symptom", "Roga", "Herb", "Formulation",
                   "ProvisionalClaim", "ProvisionalEvidence")


@router.get("/health/neo4j")
def neo4j_health():
    result = check_neo4j()
    body = {
        "status": "healthy" if result["status"] == "healthy" else "unavailable",
        "database": "neo4j",
        "connected": result["status"] == "healthy",
        "reason": result["status"],
        "detail": result["detail"],
        "encrypted": result["encrypted"],
        "scope": "connectivity only; says nothing about graph content",
    }
    if not body["connected"]:
        raise HTTPException(status_code=503, detail=body)
    return body


def _graph_summary() -> dict:
    """Constraint names and node counts in one READ session (3 queries)."""

    @unit_of_work(timeout=query_timeout())
    def read(tx):
        constraints = {r["name"] for r in tx.run("SHOW CONSTRAINTS YIELD name RETURN name")}
        labels = {r["label"] for r in tx.run("CALL db.labels() YIELD label RETURN label")}
        counts = {}
        for label in _CONTENT_LABELS:
            if label in labels:
                counts[label] = tx.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
            else:
                counts[label] = 0
        return constraints, counts

    driver = get_neo4j_driver()
    with driver.session(
        default_access_mode=READ_ACCESS,
        notifications_min_severity=NotificationMinimumSeverity.OFF,
    ) as session:
        constraints, counts = session.execute_read(read)
    missing = sorted(CORE_CONSTRAINTS - constraints)
    return {
        "graph_schema": {
            "status": "missing_constraints" if missing else "core_constraints_present",
            "missing_core_constraints": missing,
            "stage_e_applied": not (STAGE_E_CONSTRAINTS - constraints),
            "full_validation": "GET /health/graph-validation",
        },
        "knowledge_graph_content": {
            "status": (
                "populated" if counts["Claim"]
                else "provisional_only" if counts.get("ProvisionalClaim")
                else "empty"
            ),
            "node_counts": counts,
            "note": (
                "Counts only; claim correctness is not assessed here." if counts["Claim"]
                else (f"No approved claims. {counts.get('ProvisionalClaim', 0)} provisional (unverified) "
                      "claims are available in research mode only; default reasoning abstains.")
                if counts.get("ProvisionalClaim")
                else "No approved claims: reasoning will abstain."
            ),
        },
    }


@lru_cache(maxsize=4)
def _cached_report(manifest: str, candidates: str | None, stamp: tuple) -> dict:
    # stamp (file modification times) invalidates the cache on change.
    from app.knowledge_ingestion.report import build_ingestion_report

    return build_ingestion_report(manifest, candidates_dir=candidates)


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _local_ingestion() -> dict:
    manifest = Path(os.getenv("C2_CORPUS_MANIFEST") or DEFAULT_MANIFEST)
    candidates = Path(os.getenv("C2_CANDIDATE_STORE") or DEFAULT_CANDIDATES)
    if not manifest.is_file():
        return {"status": "not_found",
                "detail": "No local ingestion manifest on this server."}
    candidates_file = candidates / "candidates.jsonl"
    try:
        report = _cached_report(
            str(manifest),
            str(candidates) if candidates.is_dir() else None,
            (_mtime(manifest), _mtime(candidates_file)),
        )
    except (OSError, ValueError) as exc:
        return {"status": "unreadable", "detail": type(exc).__name__}
    totals = report["totals"]
    review = report.get("candidates", {}).get("by_review_status", {})
    return {
        "status": "present",
        "manifest_generated_at": report["manifest_generated_at"],
        "sources": totals["sources"],
        "processed": totals["processed"],
        "needs_ocr_or_review": totals["needs_ocr_or_review"],
        "rejected": totals["rejected"],
        "duplicate_files_beyond_first": totals["duplicate_files_beyond_first"],
        "with_curated_metadata": totals["with_curated_title"],
        "candidate_claims": report.get("candidates", {}).get("total", 0),
        "approved_candidates": review.get("approved", 0),
        "note": "Local files are unreviewed source text until candidates are approved and promoted.",
    }


@router.get("/health/readiness")
def readiness():
    connectivity = check_neo4j()
    components: dict = {"database_connectivity": connectivity}
    if connectivity["status"] == "healthy":
        try:
            components.update(_graph_summary())
        except (Neo4jError, DriverError, OSError) as exc:
            components["graph_schema"] = {"status": "unknown", "detail": type(exc).__name__}
            components["knowledge_graph_content"] = {"status": "unknown"}
    else:
        components["graph_schema"] = {"status": "unknown", "detail": "database unavailable"}
        components["knowledge_graph_content"] = {"status": "unknown", "detail": "database unavailable"}

    components["local_corpus_ingestion"] = _local_ingestion()
    service = get_retrieval_service()
    retrieval = service.status()
    components["retrieval_service"] = {
        key: retrieval[key]
        for key in ("status", "indexed_evidence", "indexed_chunks", "last_error")
    }
    components["embedding_model"] = {
        "model_id": retrieval["model_id"],
        "loaded": retrieval["model_loaded"],
        "cached_locally": model_cached_locally(
            retrieval["model_id"], service.settings.cache_folder
        ),
    }
    components["component_integration"] = {
        "c1_screening_input": "implemented (POST /api/v1/c1/reasoning)",
        "c2_reasoning": "implemented (POST /api/v1/c2/reasoning)",
        "c3_handoff": "contract only (POST /api/v1/c2/reasoning/component3-handoff); C2 does not call C3",
    }

    schema_ok = components["graph_schema"].get("status") == "core_constraints_present"
    return {
        "service": "component2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready_for_reasoning": connectivity["status"] == "healthy" and schema_ok,
        "knowledge_available": components["knowledge_graph_content"].get("status") == "populated",
        "provisional_knowledge_available": bool(
            (components["knowledge_graph_content"].get("node_counts") or {}).get("ProvisionalClaim")
        ),
        "components": components,
        "notes": [
            "Database connectivity does not mean the corpus is complete or that recommendations are valid.",
            "A populated graph is not clinical validation: claims are traceable source statements, reviewed per the governance workflow.",
        ],
    }


@router.get("/health/graph-validation")
def graph_validation():
    """Full read-only integrity validation (counts and IDs, no text)."""
    connectivity = check_neo4j()
    if connectivity["status"] != "healthy":
        raise HTTPException(status_code=503, detail={
            "status": "unavailable", "reason": connectivity["status"],
            "detail": connectivity["detail"],
        })
    try:
        return validate_graph(get_neo4j_driver()).to_dict()
    except (Neo4jError, DriverError, OSError) as exc:
        raise HTTPException(status_code=503, detail={
            "status": "unavailable", "reason": "query_failed",
            "detail": type(exc).__name__,
        })
