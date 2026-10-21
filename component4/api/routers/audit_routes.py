"""Read and verify the audit chain; accept audit events from other services."""

import json
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import blockchain
from audit import verify_chain, write_audit
from database import get_db
from models import Anchor, AuditLog, User
from schemas import AnchorCheck, AnchorOut, AnchorVerification, AuditEntryOut, ChainStatus, ServiceEvent
from security import require_roles
from settings import CONTRACT_ADDRESS, SERVICE_API_KEY

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


def anchor_out(anchor):
    return AnchorOut(
        id=anchor.id, created_at=anchor.created_at, head_entry_id=anchor.head_entry_id,
        head_hash=anchor.head_hash, onchain_id=anchor.onchain_id, tx_hash=anchor.tx_hash,
        block_number=anchor.block_number, contract_address=anchor.contract_address,
        anchored_by=anchor.anchored_by, explorer_url=blockchain.tx_url(anchor.tx_hash),
    )


def unavailable(message):
    # 503 + "dependency" lets the dashboard show a clear "blockchain unavailable" message
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, {"dependency": "blockchain", "message": message})


@router.post("/anchor", response_model=AnchorOut, status_code=201)
def anchor_chain_head(db: Session = Depends(get_db), user: User = Depends(require_roles("supervisor"))):
    """Write the newest audit entry's hash to the Sepolia contract (FR9).

    Anchoring the head hash commits to every earlier entry, because each entry
    hash includes the previous one. Takes ~15-30 s while the block is mined.
    """
    if not blockchain.is_configured():
        raise unavailable("Blockchain anchoring is not configured on this server.")

    # Never anchor a log that has already been tampered with
    valid, _, first_bad = verify_chain(db)
    if not valid:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Audit chain is broken at entry {first_bad}; not anchoring it.")

    head = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    if head is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The audit log is empty.")
    last = db.scalars(select(Anchor).order_by(Anchor.id.desc()).limit(1)).first()
    if last is not None and last.head_entry_id == head.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No new audit entries since the last anchor.")

    try:
        result = blockchain.anchor_hash(head.entry_hash)
    except blockchain.BlockchainError as exc:
        raise unavailable(str(exc))

    anchor = Anchor(
        head_entry_id=head.id, head_hash=head.entry_hash, onchain_id=result["onchain_id"],
        tx_hash=result["tx_hash"], block_number=result["block_number"],
        contract_address=CONTRACT_ADDRESS, anchored_by=user.username,
    )
    db.add(anchor)
    db.commit()
    db.refresh(anchor)
    # The anchoring itself is audited (this new entry is covered by the NEXT anchor)
    write_audit(db, actor=user.username, role=user.role, clinic_id=user.clinic_id,
                action="audit.anchor", resource=result["tx_hash"],
                details={"head_entry_id": head.id, "onchain_id": result["onchain_id"],
                         "block_number": result["block_number"]})
    return anchor_out(anchor)


@router.get("/anchors", response_model=list[AnchorOut])
def list_anchors(db: Session = Depends(get_db), user: User = Depends(require_roles("supervisor"))):
    return [anchor_out(a) for a in db.scalars(select(Anchor).order_by(Anchor.id.desc())).all()]


@router.get("/anchors/verify", response_model=AnchorVerification)
def verify_against_blockchain(db: Session = Depends(get_db), user: User = Depends(require_roles("supervisor"))):
    """Compare every anchored hash on-chain with what the database holds TODAY.

    The local check (verify_chain) catches edits to single rows. This check also
    catches someone who rewrote the whole chain and recomputed every hash: the
    recomputed hashes no longer match the values fixed on the blockchain.
    """
    local_valid, _, _ = verify_chain(db)
    checks = []
    for anchor in db.scalars(select(Anchor).order_by(Anchor.id)).all():
        try:
            onchain = blockchain.read_anchor(anchor.onchain_id)
        except blockchain.BlockchainError as exc:
            raise unavailable(str(exc))
        entry = db.get(AuditLog, anchor.head_entry_id)
        current = entry.entry_hash if entry else None   # None = the anchored entry was deleted
        checks.append(AnchorCheck(
            anchor_id=anchor.id, onchain_id=anchor.onchain_id, head_entry_id=anchor.head_entry_id,
            onchain_hash=onchain, current_db_hash=current, matches=(current == onchain),
        ))
    all_match = all(check.matches for check in checks)
    write_audit(db, actor=user.username, role=user.role, clinic_id=user.clinic_id,
                action="audit.verify_onchain",
                details={"anchors_checked": len(checks), "all_match": all_match, "local_valid": local_valid})
    return AnchorVerification(local_chain_valid=local_valid, anchors_checked=len(checks),
                              all_anchors_match=all_match, checks=checks)


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
