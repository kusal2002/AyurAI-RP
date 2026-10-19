"""Hash-chained audit logging (proposal SO4 / FR8, NFR Auditability)."""

import hashlib
import json
from datetime import timezone

from sqlalchemy import select

from models import AuditLog, utc_now

GENESIS_HASH = "0" * 64  # "previous hash" of the very first entry


def compute_hash(prev_hash, timestamp, actor, role, clinic_id, action, resource, details):
    """SHA-256 over the previous hash plus this entry's fields, in a fixed order."""
    payload = json.dumps(
        [prev_hash, timestamp, actor, role, clinic_id, action, resource, details],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso(dt):
    """Timestamp as naive-UTC text, so the hash is identical on write and on verify.

    SQLite returns naive datetimes; PostgreSQL may return them in its own
    timezone. Converting both to UTC without tzinfo makes them comparable.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="microseconds")


def write_audit(db, actor, role, action, clinic_id=None, resource=None, details=None):
    """Append one entry to the audit chain and commit it.

    Note: two simultaneous writers could both read the same last entry.
    Fine for this prototype; production would lock the last row first.
    """
    last = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    prev_hash = last.entry_hash if last else GENESIS_HASH
    timestamp = utc_now()
    details_json = json.dumps(details or {}, sort_keys=True)

    entry = AuditLog(
        timestamp=timestamp,
        actor=actor,
        role=role,
        clinic_id=clinic_id,
        action=action,
        resource=resource,
        details=details_json,
        prev_hash=prev_hash,
        entry_hash=compute_hash(prev_hash, _iso(timestamp), actor, role, clinic_id, action, resource, details_json),
    )
    db.add(entry)
    db.commit()
    return entry


def verify_chain(db):
    """Recompute every hash. Returns (is_valid, number_checked, first_bad_id)."""
    prev_hash = GENESIS_HASH
    entries = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    for entry in entries:
        expected = compute_hash(
            prev_hash, _iso(entry.timestamp), entry.actor, entry.role,
            entry.clinic_id, entry.action, entry.resource, entry.details,
        )
        if entry.prev_hash != prev_hash or entry.entry_hash != expected:
            return False, len(entries), entry.id
        prev_hash = entry.entry_hash
    return True, len(entries), None
