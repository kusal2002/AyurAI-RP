
from fastapi import APIRouter, HTTPException

from app.db.neo4j import verify_neo4j_connection

router = APIRouter(tags=["Database Health"])


@router.get("/health/neo4j")
def neo4j_health():
    try:
        verify_neo4j_connection()
        return {
            "status": "healthy",
            "database": "neo4j",
            "connected": True,
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "database": "neo4j",
                "connected": False,
            },
        )
