import sys

import numpy as np
import pytest

from app.config import RetrievalSettings
from app.retrieval.embedding import (
    EmbeddingModelUnavailableError,
    SentenceTransformerEncoder,
)
from app.retrieval.evidence_index import EvidenceIndex, chunk_text
from c2_test_support import (
    FailingEncoder,
    KeywordEncoder,
    full_provenance,
    make_retrieval_service,
)


def make_index(records, encoder=None, **kwargs):
    index = EvidenceIndex(encoder or KeywordEncoder(), **kwargs)
    index.refresh(records)
    return index


def test_sentence_transformer_encoder_is_lazy():
    encoder = SentenceTransformerEncoder(
        RetrievalSettings(embedding_model="not-loaded-yet")
    )

    assert encoder.is_loaded is False
    assert encoder.model_id == "not-loaded-yet"


def test_model_load_failure_raises_clear_error(monkeypatch):
    # Simulate sentence-transformers not being importable.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    encoder = SentenceTransformerEncoder(RetrievalSettings())

    with pytest.raises(EmbeddingModelUnavailableError):
        encoder.encode(["text"])

    assert encoder.is_loaded is False


def test_invalid_model_path_raises_clear_error(tmp_path):
    pytest.importorskip("sentence_transformers")
    missing = tmp_path / "missing-model"
    encoder = SentenceTransformerEncoder(
        RetrievalSettings(embedding_model=str(missing))
    )

    with pytest.raises(EmbeddingModelUnavailableError):
        encoder.encode(["text"])


def test_chunking_preserves_text_with_overlap():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, max_chars=80, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert chunks[0].startswith("word0")
    assert chunks[-1].endswith("word99")


def test_chunking_rejects_invalid_settings():
    with pytest.raises(ValueError):
        chunk_text("text", max_chars=10, overlap=10)


def test_search_returns_source_metadata():
    index = make_index(
        [full_provenance("EV-1", "pallor indicates pandu")]
    )
    results = index.search("pallor pandu", top_k=3)

    assert len(results) == 1
    chunk = results[0].chunk
    assert chunk.evidence_id == "EV-1"
    assert chunk.chunk_id == "EV-1#chunk-0"
    assert chunk.title == "Synthetic test source EV-1"
    assert chunk.citation == "Synthetic citation EV-1"
    assert chunk.page == "1"
    assert chunk.evidence_type == "classical"


def test_long_text_chunks_keep_source_ids():
    text = " ".join(["pallor indicates pandu"] * 60)
    index = make_index(
        [full_provenance("EV-LONG", text)],
        chunk_max_chars=100,
        chunk_overlap_chars=10,
    )

    assert index.size > 1
    results = index.search("pallor", top_k=50)
    assert {r.chunk.evidence_id for r in results} == {"EV-LONG"}


def test_similarity_ordering_is_deterministic():
    records = [
        full_provenance("EV-B", "pallor indicates pandu"),
        full_provenance("EV-A", "pallor indicates pandu"),
        full_provenance("EV-C", "weather market"),
    ]
    first = make_index(records).search(
        "pallor pandu", top_k=3, min_similarity=0.1
    )
    second = make_index(list(reversed(records))).search(
        "pallor pandu", top_k=3, min_similarity=0.1
    )

    ids = [r.chunk.chunk_id for r in first]
    assert ids == [r.chunk.chunk_id for r in second]
    assert ids == ["EV-A#chunk-0", "EV-B#chunk-0"]
    assert first[0].similarity == pytest.approx(
        2 / np.sqrt(2) / np.sqrt(3), abs=1e-5
    )


def test_empty_corpus_returns_empty_result():
    index = make_index([])

    assert index.size == 0
    assert index.search("pallor") == []


def test_low_relevance_is_flagged_or_excluded():
    index = make_index([full_provenance("EV-1", "weather market")])

    assert index.search("pallor", min_similarity=0.3) == []

    flagged = index.search(
        "pallor weather", min_similarity=0.9, include_below_threshold=True
    )
    assert len(flagged) == 1
    assert flagged[0].below_threshold is True


def test_restrict_to_evidence_ids():
    index = make_index(
        [
            full_provenance("EV-1", "pallor"),
            full_provenance("EV-2", "pallor"),
        ]
    )
    results = index.search("pallor", restrict_to_evidence_ids=["EV-2"])

    assert [r.chunk.evidence_id for r in results] == ["EV-2"]


def test_refresh_reembeds_only_changed_records_and_removes_deleted():
    encoder = KeywordEncoder()
    index = EvidenceIndex(encoder)
    stats = index.refresh(
        [full_provenance("EV-1", "pallor"), full_provenance("EV-2", "pandu")]
    )
    assert stats["embedded_evidence"] == 2

    stats = index.refresh(
        [full_provenance("EV-1", "pallor"), full_provenance("EV-2", "diet")]
    )
    assert stats["embedded_evidence"] == 1

    stats = index.refresh([full_provenance("EV-1", "pallor")])
    assert stats["removed_evidence"] == 1
    assert index.evidence_ids == ["EV-1"]


def test_records_without_text_are_reported_not_silently_dropped():
    index = EvidenceIndex(KeywordEncoder())
    stats = index.refresh(
        [full_provenance("EV-1", "pallor"), {"evidence_id": "EV-EMPTY"}]
    )

    assert stats["skipped_evidence"] == 1
    assert index.skipped_evidence_ids == ["EV-EMPTY"]


def test_duplicate_evidence_records_are_indexed_once():
    record = full_provenance("EV-1", "pallor")
    index = make_index([record, dict(record)])

    assert index.size == 1


def test_service_reports_unavailable_model_without_fallback():
    service = make_retrieval_service(encoder=FailingEncoder())

    assert service.ensure_ready() is False
    assert service.mode.value == "unavailable"
    assert "could not be loaded" in service.last_error


def test_service_builds_index_lazily_and_offline():
    encoder = KeywordEncoder()
    service = make_retrieval_service(encoder=encoder)

    assert encoder.calls == 0
    assert service.ensure_ready() is True
    assert service.mode.value == "neural_embedding"
