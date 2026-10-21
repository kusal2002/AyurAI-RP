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
