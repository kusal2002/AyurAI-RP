"""Validation helpers for evidence provenance metadata."""

from urllib.parse import urlparse

from app.models.evidence import EvidenceRecord


def validate_evidence_provenance(evidence: EvidenceRecord) -> None:
    """Validate required evidence text and optional provenance metadata.

    This checks metadata completeness and URL structure only.
    It does not authenticate a source or establish that it supports a claim.
    """
    required_fields = {
        "evidence_id": evidence.evidence_id,
        "title": evidence.title,
        "source_name": evidence.source_name,
        "text": evidence.text,
    }

    for field_name, value in required_fields.items():
        if not value or not value.strip():
            raise ValueError(
                f"{field_name} must not be empty or whitespace."
            )

    optional_fields = {
        "section": evidence.section,
        "page": evidence.page,
        "citation": evidence.citation,
    }

    for field_name, value in optional_fields.items():
        if value is not None and not value.strip():
            raise ValueError(
                f"{field_name} must not be blank when provided."
            )

    if evidence.source_url is not None:
        if not evidence.source_url.strip():
            raise ValueError(
                "source_url must not be blank when provided."
            )

        parsed_url = urlparse(evidence.source_url.strip())

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
        ):
            raise ValueError(
                "source_url must be a valid HTTP or HTTPS URL."
            )
