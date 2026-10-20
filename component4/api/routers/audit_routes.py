"""Read and verify the audit chain; accept audit events from other services."""

import json
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import verify_chain, write_audit
from database import get_db
from models import AuditLog, User
from schemas import AuditEntryOut, ChainStatus, ServiceEvent
from security import require_roles
from settings import SERVICE_API_KEY

router = APIRouter(prefix="/api/v1/c4/audit", tags=["Audit"])


def to_out(entry):
    return AuditEntryOut(
        id=entry.id, timestamp=entry.timestamp, actor=entry.actor, role=entry.role,
        clinic_id=entry.clinic_id, action=entry.action, resource=entry.resource,
        details=json.loads(entry.details), prev_hash=entry.prev_hash, entry_hash=entry.entry_hash,
    )


@router.get("/logs", response_model=list[AuditEntryOut])
def list_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("practitioner", "supervisor")),
):
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 500))
    # RBAC: practitioners only see entries from their own clinic
    if user.role == "practitioner":
        query = query.where(AuditLog.clinic_id == user.clinic_id)
    return [to_out(entry) for entry in db.scalars(query).all()]


@router.get("/verify", response_model=ChainStatus)
def verify(db: Session = Depends(get_db), user: User = Depends(require_roles("supervisor"))):
    valid, checked, first_bad = verify_chain(db)
    write_audit(db, actor=user.username, role=user.role, clinic_id=user.clinic_id,
                action="audit.verify", details={"valid": valid, "entries_checked": checked})
    head = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    return ChainStatus(valid=valid, entries_checked=checked, first_invalid_id=first_bad,
                       head_hash=head.entry_hash if head else None)


@router.post("/events", status_code=201)
def ingest_service_event(
    body: ServiceEvent,
    x_service_key: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Component 2 / 3 post their audit records here with a shared service key."""
    if not SERVICE_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service ingestion is not configured")
    # compare_digest takes the same time for any wrong key (no timing leak)
    if not secrets.compare_digest(x_service_key, SERVICE_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service key")
    entry = write_audit(db, actor=body.service, role="service", action=body.event,
                        resource=body.reference_id, details=body.details)
    return {"id": entry.id, "entry_hash": entry.entry_hash}
