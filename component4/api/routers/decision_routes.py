"""Practitioner decisions: approve / request changes / reject (FR4)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import write_audit
from database import get_db
from models import Decision, User
from schemas import DecisionCreate, DecisionOut
from security import require_roles

router = APIRouter(prefix="/api/v1/c4/decisions", tags=["Practitioner decisions"])


@router.post("", response_model=DecisionOut, status_code=201)
def create_decision(
    body: DecisionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("practitioner", "supervisor")),
):
    decision = Decision(
        case_ref=body.case_ref,
        c2_request_id=body.c2_request_id,
        c3_assessment_id=body.c3_assessment_id,
        decision=body.decision,
        rationale=body.rationale.strip(),
        reviewer=user.username,
        clinic_id=user.clinic_id,  # taken from the token, never from the request body
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    # Audit only identifiers; the free-text rationale stays out of the log
    write_audit(
        db, actor=user.username, role=user.role, clinic_id=user.clinic_id,
        action=f"decision.{body.decision}", resource=body.case_ref,
        details={
            "decision_id": decision.id,
            "c2_request_id": body.c2_request_id,
            "c3_assessment_id": body.c3_assessment_id,
        },
    )
    return decision


@router.get("", response_model=list[DecisionOut])
def list_decisions(
    case_ref: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("practitioner", "supervisor")),
):
    query = select(Decision).order_by(Decision.created_at.desc())
    # RBAC: practitioners only see their own clinic's decisions (FR7)
    if user.role == "practitioner":
        query = query.where(Decision.clinic_id == user.clinic_id)
    if case_ref:
        query = query.where(Decision.case_ref == case_ref)
    return db.scalars(query).all()
