import pytest
from pydantic import ValidationError

from app.models.evidence import EvidenceRecord, EvidenceType
from app.ontology.evidence_validation import (
    validate_evidence_provenance,
)
from unittest.mock import patch

from app.db.repository import save_evidence


def make_evidence(**overrides) -> EvidenceRecord:
    data = {
        "evidence_id": "EVIDENCE-001",
        "title": "Example research paper",
        "source_name": "Example Research Journal",
        "evidence_type": EvidenceType.MODERN_RESEARCH,
        "text": "Example evidence text for validation.",
        "source_url": "https://example.org/research",
        "citation": "Example Journal, 2025",
    }
    data.update(overrides)
    return EvidenceRecord(**data)


def test_accepts_valid_evidence():
    evidence = make_evidence()

    validate_evidence_provenance(evidence)


@pytest.mark.parametrize(
    "field_name",
    ["evidence_id", "title", "source_name", "text"],
)
def test_rejects_whitespace_required_fields(field_name):
    evidence = make_evidence(**{field_name: "   "})

    with pytest.raises(
        ValueError,
        match=f"{field_name} must not be empty",
    ):
        validate_evidence_provenance(evidence)


@pytest.mark.parametrize(
    "field_name",
    ["section", "page", "citation"],
)
def test_rejects_blank_optional_metadata(field_name):
    evidence = make_evidence(**{field_name: "   "})

    with pytest.raises(
        ValueError,
        match=f"{field_name} must not be blank",
    ):
        validate_evidence_provenance(evidence)


@pytest.mark.parametrize(
    "source_url",
    [
        "",
        "   ",
        "not-a-url",
        "ftp://example.org/source",
        "https:///missing-host",
    ],
)
def test_rejects_invalid_source_urls(source_url):
    evidence = make_evidence(source_url=source_url)

    with pytest.raises(ValueError):
        validate_evidence_provenance(evidence)


@pytest.mark.parametrize(
    "source_url",
    [
        None,
        "https://example.org/source",
        "http://example.org/source",
    ],
)
def test_accepts_optional_or_valid_source_urls(source_url):
    evidence = make_evidence(source_url=source_url)

    validate_evidence_provenance(evidence)


def test_accepts_missing_optional_metadata():
    evidence = make_evidence(
        source_url=None,
        citation=None,
        section=None,
        page=None,
    )

    validate_evidence_provenance(evidence)


def test_pydantic_rejects_empty_required_text():
    with pytest.raises(ValidationError):
        make_evidence(text="")


def test_save_evidence_rejects_invalid_metadata_before_database_access():
    evidence = make_evidence(source_url="not-a-url")

    with patch("app.db.repository._get_driver") as get_driver:
        with pytest.raises(
            ValueError,
            match="source_url must be a valid HTTP or HTTPS URL",
        ):
            save_evidence(evidence)

        get_driver.assert_not_called()


def test_save_evidence_rejects_blank_optional_metadata_before_database_access():
    evidence = make_evidence(citation="   ")

    with patch("app.db.repository._get_driver") as get_driver:
        with pytest.raises(
            ValueError,
            match="citation must not be blank",
        ):
            save_evidence(evidence)

        get_driver.assert_not_called()
