"""Database tables (SQLAlchemy ORM)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    """A person who can sign in. Passwords are stored only as bcrypt hashes."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))          # practitioner | supervisor | researcher
    clinic_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # None = all clinics


class Decision(Base):
    """A practitioner's final decision on an AI-generated case."""
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(128))      # pseudonymous case ID
    c2_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    c3_assessment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision: Mapped[str] = mapped_column(String(32))       # approve | request_changes | reject
    rationale: Mapped[str] = mapped_column(Text, default="")
    reviewer: Mapped[str] = mapped_column(String(64))
    clinic_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    """Append-only, hash-chained audit trail.

    entry_hash = SHA-256(previous entry's hash + this entry's content), so
    editing or deleting any row breaks every hash after it.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    actor: Mapped[str] = mapped_column(String(64))           # username or service name
    role: Mapped[str] = mapped_column(String(32))
    clinic_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64))          # e.g. auth.login, decision.approve
    resource: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="{}")  # JSON; identifiers only, never free text
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class Anchor(Base):
    """One audit-chain head hash written to the AuditAnchor contract on Sepolia.

    Because every entry hash includes the previous one, anchoring the newest
    entry's hash commits to the whole log up to and including that entry.
    """
    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    head_entry_id: Mapped[int] = mapped_column(Integer)      # audit_logs.id that was anchored
    head_hash: Mapped[str] = mapped_column(String(64))       # its entry_hash at anchoring time
    onchain_id: Mapped[int] = mapped_column(Integer)         # id the contract assigned (hashes[id])
    tx_hash: Mapped[str] = mapped_column(String(66), unique=True)
    block_number: Mapped[int] = mapped_column(Integer)
    contract_address: Mapped[str] = mapped_column(String(42))
    anchored_by: Mapped[str] = mapped_column(String(64))
