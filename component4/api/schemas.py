"""Request / response shapes (Pydantic). FastAPI validates every request against these."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Same identifier rule as Component 2, so IDs pass between services unchanged
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    username: str
    role: str
    clinic_id: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DecisionCreate(BaseModel):
    case_ref: str = Field(pattern=ID_PATTERN)
    c2_request_id: str | None = Field(default=None, pattern=ID_PATTERN)
    c3_assessment_id: str | None = Field(default=None, pattern=ID_PATTERN)
    decision: Literal["approve", "request_changes", "reject"]
    rationale: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def rationale_needed_unless_approved(self):
        # A practitioner must explain why they reject or ask for changes
        if self.decision != "approve" and not self.rationale.strip():
            raise ValueError("rationale is required for reject and request_changes")
        return self


class DecisionOut(BaseModel):
    id: int
    case_ref: str
    c2_request_id: str | None
    c3_assessment_id: str | None
    decision: str
    rationale: str
    reviewer: str
    clinic_id: str | None
    created_at: datetime


class AuditEntryOut(BaseModel):
    id: int
    timestamp: datetime
    actor: str
    role: str
    clinic_id: str | None
    action: str
    resource: str | None
    details: dict
    prev_hash: str
    entry_hash: str


class ChainStatus(BaseModel):
    valid: bool
    entries_checked: int
    first_invalid_id: int | None
    head_hash: str | None


class AnchorOut(BaseModel):
    id: int
    created_at: datetime
    head_entry_id: int
    head_hash: str
    onchain_id: int
    tx_hash: str
    block_number: int
    contract_address: str
    anchored_by: str
    explorer_url: str      # Etherscan page for the transaction


class AnchorCheck(BaseModel):
    """Result of comparing one anchor with the blockchain and the current database."""
    anchor_id: int
    onchain_id: int
    head_entry_id: int
    onchain_hash: str            # what the contract stores
    current_db_hash: str | None  # what the database holds for that entry today
    matches: bool


class AnchorVerification(BaseModel):
    local_chain_valid: bool          # recomputing the hash chain inside the database
    anchors_checked: int
    all_anchors_match: bool          # every on-chain hash equals the database today
    checks: list[AnchorCheck]


class ServiceEvent(BaseModel):
    """An audit event posted by another AyurAI service (e.g. C2's AuditRecord)."""
    service: Literal["component2", "component3"]
    event: str = Field(min_length=1, max_length=64)
    reference_id: str | None = Field(default=None, pattern=ID_PATTERN)
    details: dict = Field(default_factory=dict)
