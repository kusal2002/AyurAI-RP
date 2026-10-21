import json
import os
from unittest.mock import patch

import numpy as np
import pytest

from app.config import IngestionSettings, RetrievalSettings
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.models import (
    ExtractedPassage,
    PassageKind,
    SourceLocation,
    SourceMetadata,
)
from app.knowledge_ingestion.service import process_source, write_extraction
from app.retrieval.embedding import EmbeddingModelUnavailableError
from app.retrieval.source_chunks import (
    UNREVIEWED_SOURCE_TEXT,
    EmbeddingDimensionError,
    EmbeddingStoreError,
    RetrievalCase,
    SourceChunkIndex,
    build_embedding_store,
    evaluate_retrieval,
    read_store_manifest,
    store_dir_for,
)
from c2_test_support import FailingEncoder, KeywordEncoder
from ingestion_test_support import DEVANAGARI


SETTINGS = RetrievalSettings(batch_size=2, min_similarity=0.1, top_k=5)


class RecordingEncoder(KeywordEncoder):
    """KeywordEncoder that remembers every text it was asked to encode."""

    def __init__(self, model_id="test-keyword-encoder"):
        super().__init__()
        self._model_id = model_id
        self.texts = []

    @property
    def model_id(self):
        return self._model_id

    def encode(self, texts):
        self.texts.extend(texts)
        return super().encode(texts)


class FixedDimensionEncoder:
    def __init__(self, dimension, model_id="test-keyword-encoder"):
        self.dimension = dimension
        self.model_id = model_id

    def encode(self, texts):
        return np.ones((len(texts), self.dimension), dtype=np.float32)


def isolate_offline_env(monkeypatch):
    """Record HF offline variables so monkeypatch restores them afterwards."""
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)


def make_chunks(source_id, texts, page=1, metadata=None):
    passages = [
        ExtractedPassage(
            passage_index=index,
            kind=PassageKind.PAGE,
            text=text,
            location=SourceLocation(page=page + index),
        )
        for index, text in enumerate(texts)
    ]
    return chunk_passages(
        source_id,
        passages,
        IngestionSettings(chunk_max_chars=60, chunk_overlap_chars=0),
        metadata,
    )


CORPUS = {
    "src-pandu": [
        "Pandu presents with pallor and fatigue.",
        "The principle for pandu uses a herb formulation.",
    ],
    "src-market": ["Unrelated weather and market report."],
}


def corpus_chunks():
    chunks = []
    for source_id, texts in CORPUS.items():
        chunks.extend(make_chunks(source_id, texts))
    return chunks


def build(tmp_path, encoder=None, chunks=None, **kwargs):
    return build_embedding_store(
        chunks if chunks is not None else corpus_chunks(),
        encoder or RecordingEncoder(),
        tmp_path / "store",
        SETTINGS,
        **kwargs,
    )


# --- store building ----------------------------------------------------------

def test_build_store_records_model_dimension_and_provenance(tmp_path):
    stats = build(tmp_path)

    store = store_dir_for(tmp_path / "store", "test-keyword-encoder")
    manifest = read_store_manifest(store)
    assert manifest.model_id == "test-keyword-encoder"
    assert manifest.dimension == 15
    assert manifest.chunk_count == stats["chunks"] == len(corpus_chunks())
    assert manifest.source_count == 2
    assert manifest.chunker_versions == ["1"]
    vectors = np.load(store / "vectors.npy")
    assert vectors.shape == (manifest.chunk_count, 15)
    assert vectors.dtype == np.float32
    rows = [json.loads(line) for line in (store / "chunks.jsonl").open(encoding="utf-8")]
    assert [r["chunk_id"] for r in rows] == [c.chunk_id for c in corpus_chunks()]
    assert "original_text" not in rows[0]
    assert rows[0]["page_start"] == 1


def test_embedding_is_batched(tmp_path):
    calls = []

    class CountingEncoder(RecordingEncoder):
        def encode(self, texts):
            calls.append(len(texts))
            return super().encode(texts)

    build(tmp_path, encoder=CountingEncoder())
    assert max(calls) <= SETTINGS.batch_size


def test_rebuild_is_incremental(tmp_path):
    build(tmp_path)
    encoder = RecordingEncoder()
    stats = build(tmp_path, encoder=encoder)
    assert stats["embedded"] == 0
    assert stats["reused"] == stats["chunks"]
    assert encoder.texts == []

    changed = make_chunks("src-pandu", ["Pandu now edited text about pallor."])
    keep = make_chunks("src-market", CORPUS["src-market"])
    encoder = RecordingEncoder()
    stats = build(tmp_path, encoder=encoder, chunks=changed + keep)
    assert stats["embedded"] == len(changed)
    assert stats["reused"] == len(keep)
    assert stats["removed"] == len(make_chunks("src-pandu", CORPUS["src-pandu"]))


def test_passage_prefix_is_applied_and_recorded(tmp_path):
    settings = RetrievalSettings(
        batch_size=4, passage_prefix="passage: ", query_prefix="query: "
    )
    encoder = RecordingEncoder()
    build_embedding_store(corpus_chunks(), encoder, tmp_path / "s", settings)
    assert all(text.startswith("passage: ") for text in encoder.texts)

    index = SourceChunkIndex(tmp_path / "s", encoder, settings)
    encoder.texts.clear()
    index.search("pallor")
    assert encoder.texts == ["query: pallor"]

    with pytest.raises(EmbeddingStoreError):
        build_embedding_store(
            corpus_chunks(), RecordingEncoder(), tmp_path / "s", SETTINGS
        )


def test_models_get_separate_stores(tmp_path):
    build(tmp_path)
    build(tmp_path, encoder=RecordingEncoder("other/model-b"))
    names = sorted(p.name for p in (tmp_path / "store").iterdir())
    assert names == ["other__model-b", "test-keyword-encoder"]


def test_dimension_mismatch_is_rejected(tmp_path):
    build(tmp_path, encoder=FixedDimensionEncoder(15), chunks=corpus_chunks()[:1])
    with pytest.raises(EmbeddingDimensionError):
        build(tmp_path, encoder=FixedDimensionEncoder(8))
    # The rejected run left the earlier store untouched.
    manifest = read_store_manifest(store_dir_for(tmp_path / "store", "test-keyword-encoder"))
    assert manifest.dimension == 15 and manifest.chunk_count == 1

    stats = build(tmp_path, encoder=FixedDimensionEncoder(8), rebuild=True)
    assert stats["dimension"] == 8


def test_wrong_row_count_is_rejected(tmp_path):
    class ShortEncoder(FixedDimensionEncoder):
        def encode(self, texts):
            return np.ones((max(0, len(texts) - 1), 4), dtype=np.float32)

    with pytest.raises(EmbeddingStoreError):
        build(tmp_path, encoder=ShortEncoder(4))


def test_model_failure_is_reported_and_writes_nothing(tmp_path):
    with pytest.raises(EmbeddingModelUnavailableError):
        build(tmp_path, encoder=FailingEncoder())
    assert not (tmp_path / "store").exists()


def test_duplicate_chunks_are_skipped(tmp_path):
    chunks = corpus_chunks()
    stats = build(tmp_path, chunks=chunks + chunks[:1])
    assert stats["duplicates_skipped"] == 1
    assert stats["chunks"] == len(chunks)


# --- search ------------------------------------------------------------------

def make_index(tmp_path, chunks=None, settings=SETTINGS):
    encoder = RecordingEncoder()
    build_embedding_store(
        chunks if chunks is not None else corpus_chunks(),
        encoder, tmp_path / "store", settings,
    )
    return SourceChunkIndex(tmp_path / "store", encoder, settings)


def test_search_returns_traceable_unreviewed_hits(tmp_path):
    index = make_index(tmp_path)

    hits = index.search("pallor fatigue pandu")

    assert hits[0].chunk.source_id == "src-pandu"
    assert hits[0].chunk.page_start == 1
    assert hits[0].evidence_status == UNREVIEWED_SOURCE_TEXT
    assert all(h.chunk.source_id != "src-market" for h in hits)
    similarities = [h.similarity for h in hits]
    assert similarities == sorted(similarities, reverse=True)


def test_search_threshold_and_below_threshold_option(tmp_path):
    index = make_index(tmp_path)
    assert all(not h.below_threshold for h in index.search("market"))
    everything = index.search("market", include_below_threshold=True, top_k=10)
    assert any(h.below_threshold for h in everything)
    assert len(everything) == index.size


def test_search_with_no_match_is_empty(tmp_path):
    index = make_index(tmp_path)
    assert index.search("completely absent vocabulary") == []


def test_search_filters_and_source_dedup(tmp_path):
    deva = make_chunks(
        "src-deva", [f"{DEVANAGARI} pandu pallor"],
        metadata=SourceMetadata(source_language="sa"),
    )
    index = make_index(tmp_path, chunks=corpus_chunks() + deva)

    assert {h.chunk.source_id for h in index.search("pandu", scripts=["Deva"])} == {"src-deva"}
    only = index.search("pandu", source_ids=["src-pandu"], top_k=10)
    assert {h.chunk.source_id for h in only} == {"src-pandu"}
    assert [h.chunk.source_id for h in index.search("pandu", declared_languages=["sa"])] == ["src-deva"]

    deduped = index.search("pandu pallor", top_k=10, max_per_source=1)
    sources = [h.chunk.source_id for h in deduped]
    assert len(sources) == len(set(sources))


def test_empty_store_and_bad_queries(tmp_path):
    index = make_index(tmp_path, chunks=[])
    assert index.size == 0
    assert index.search("pallor") == []
    with pytest.raises(ValueError):
        index.search("   ")
    with pytest.raises(ValueError):
        index.search("pallor", max_per_source=0)


def test_index_rejects_other_model_or_missing_store(tmp_path):
    make_index(tmp_path)
    with pytest.raises(EmbeddingStoreError):
        SourceChunkIndex(tmp_path / "store", RecordingEncoder("other/model"), SETTINGS)
    with pytest.raises(EmbeddingStoreError):
        SourceChunkIndex(tmp_path / "missing", RecordingEncoder(), SETTINGS)


def test_query_dimension_mismatch(tmp_path):
    make_index(tmp_path)
    index = SourceChunkIndex(tmp_path / "store", FixedDimensionEncoder(4), SETTINGS)
    with pytest.raises(EmbeddingDimensionError):
        index.search("pallor")


def test_search_failure_propagates(tmp_path):
    make_index(tmp_path)

    class BrokenAfterLoad(RecordingEncoder):
        def encode(self, texts):
            raise EmbeddingModelUnavailableError("inference failed")

    index = SourceChunkIndex(tmp_path / "store", BrokenAfterLoad(), SETTINGS)
    with pytest.raises(EmbeddingModelUnavailableError):
        index.search("pallor")


# --- evaluation --------------------------------------------------------------

def test_evaluate_retrieval_hit_rate_and_mrr(tmp_path):
    index = make_index(tmp_path)
    cases = [
        RetrievalCase(case_id="c1", query="pallor fatigue", relevant_source_ids=["src-pandu"]),
        RetrievalCase(case_id="c2", query="weather market", relevant_source_ids=["src-market"]),
        RetrievalCase(case_id="c3", query="weather", relevant_source_ids=["src-absent"]),
    ]

    report = evaluate_retrieval(index, cases, top_k=3)

    assert report["cases"] == 3
    assert report["hit_rate@1"] == round(2 / 3, 4)
    assert report["hit_rate@3"] == round(2 / 3, 4)
    assert report["mrr"] == round(2 / 3, 4)
    assert [c["rank"] for c in report["per_case"]] == [1, 1, None]


# --- CLI ---------------------------------------------------------------------

def test_cli_embed_search_and_eval_offline_by_default(tmp_path, capsys, monkeypatch):
    book = tmp_path / "book.md"
    book.write_text(
        "# Pandu\n\nPandu presents with pallor and fatigue.\n\n"
        "# Weather\n\nUnrelated weather and market report.",
        encoding="utf-8",
    )
    out = tmp_path / "extracted"
    write_extraction(process_source(book), out)
    assert main(["chunk", str(out)]) == 0
    isolate_offline_env(monkeypatch)
    encoder = RecordingEncoder()

    def fake_encoder(settings, allow_download):
        fake_encoder.allow = allow_download
        if not allow_download:
            os.environ["HF_HUB_OFFLINE"] = "1"
        return encoder

    store = tmp_path / "embeddings"
    with patch("app.knowledge_ingestion.cli._make_encoder", fake_encoder):
        assert main(["embed", str(out), "--store", str(store)]) == 0
        assert fake_encoder.allow is False
        assert "embedded" in capsys.readouterr().out

        assert main(["search", "pallor fatigue", "--store", str(store)]) == 0
        output = capsys.readouterr().out
        assert "#chk-" in output and UNREVIEWED_SOURCE_TEXT in output

        cases = tmp_path / "cases.jsonl"
        source_id = process_source(book).record.source_id
        cases.write_text(json.dumps({
            "case_id": "c1", "query": "pallor", "relevant_source_ids": [source_id],
        }) + "\n", encoding="utf-8")
        assert main(["search-eval", str(cases), "--store", str(store)]) == 0
        assert json.loads(capsys.readouterr().out)["hit_rate@10"] == 1.0


def test_make_encoder_sets_offline_mode(monkeypatch):
    from app.knowledge_ingestion.cli import _make_encoder

    isolate_offline_env(monkeypatch)
    encoder = _make_encoder(RetrievalSettings(), allow_download=False)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert encoder.model_id == RetrievalSettings().embedding_model
    assert not encoder.is_loaded  # creating it does not load or download


def test_cli_reports_store_errors(tmp_path, capsys):
    with patch(
        "app.knowledge_ingestion.cli._make_encoder",
        lambda settings, allow: RecordingEncoder(),
    ):
        assert main(["search", "x", "--store", str(tmp_path / "none")]) == 3
    assert "No embedding store" in capsys.readouterr().out


def test_exclude_flags_is_opt_in(tmp_path):
    from app.knowledge_ingestion.normalization import REPETITIVE_TEXT_FLAG

    chunks = corpus_chunks()
    noisy = chunks[0].model_copy(update={"quality_flags": [REPETITIVE_TEXT_FLAG]})
    index = make_index(tmp_path, chunks=[noisy, *chunks[1:]])

    default = index.search("pallor fatigue pandu", top_k=10)
    assert noisy.chunk_id in {h.chunk.chunk_id for h in default}

    filtered = index.search(
        "pallor fatigue pandu", top_k=10, exclude_flags=[REPETITIVE_TEXT_FLAG]
    )
    assert noisy.chunk_id not in {h.chunk.chunk_id for h in filtered}

    report = evaluate_retrieval(
        index,
        [RetrievalCase(case_id="c", query="pallor", relevant_chunk_ids=[noisy.chunk_id])],
        exclude_flags=[REPETITIVE_TEXT_FLAG],
    )
    assert report["excluded_flags"] == [REPETITIVE_TEXT_FLAG]
    assert report["per_case"][0]["rank"] is None


# --- store-path error messages -----------------------------------------------

def test_missing_store_root_is_explained(tmp_path):
    with pytest.raises(EmbeddingStoreError) as info:
        SourceChunkIndex(tmp_path / "placeholder", RecordingEncoder(), SETTINGS)
    message = str(info.value)
    assert message.startswith("No embedding store")
    assert (tmp_path / "placeholder" / "test-keyword-encoder").as_posix() in message
    assert "does not exist" in message and "one subdirectory per model" in message


def test_model_directory_passed_as_store_points_to_parent(tmp_path):
    make_index(tmp_path)
    model_dir = tmp_path / "store" / "test-keyword-encoder"
    with pytest.raises(EmbeddingStoreError) as info:
        SourceChunkIndex(model_dir, RecordingEncoder(), SETTINGS)
    message = str(info.value)
    assert "is itself a model store" in message
    assert (tmp_path / "store").as_posix() in message


def test_store_root_without_this_model_lists_available_stores(tmp_path):
    make_index(tmp_path)
    # A source manifest is not a model store and must not be reported as one.
    (tmp_path / "store" / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(EmbeddingStoreError) as info:
        SourceChunkIndex(tmp_path / "store", RecordingEncoder("other/model"), SETTINGS)
    message = str(info.value)
    assert "Stores under" in message and "test-keyword-encoder" in message
    assert "is itself a model store" not in message


# --- evaluation diagnostics and relevance pooling ----------------------------

import csv  # noqa: E402

from app.config import load_source_retrieval_settings  # noqa: E402
from app.retrieval.source_chunks import (  # noqa: E402
    build_relevance_pool,
    label_method_of,
    write_relevance_pool,
)


def diagnostic_index(tmp_path):
    deva = make_chunks("src-deva", [f"{DEVANAGARI} pandu pallor"])
    chunks = corpus_chunks() + deva
    return make_index(tmp_path, chunks=chunks), chunks, deva


def test_details_report_label_composition_and_answerability(tmp_path):
    index, chunks, deva = diagnostic_index(tmp_path)
    latin_pandu = [c.chunk_id for c in chunks if c.source_id == "src-pandu"]
    cases = [
        RetrievalCase(case_id="latin", query="pallor fatigue",
                      relevant_chunk_ids=latin_pandu,
                      note="lexical label /pallor/; chance hit@1 = 0.1"),
        RetrievalCase(case_id="deva-no-target", query="पाण्डु रोग",
                      relevant_chunk_ids=latin_pandu + ["src-x#chk-missing"],
                      label_method="human_reviewed"),
        RetrievalCase(case_id="deva-target", query="पाण्डु रोग",
                      relevant_chunk_ids=[deva[0].chunk_id]),
    ]

    report = evaluate_retrieval(index, cases, top_k=3, details=True)
    diag = {c["case_id"]: c["diagnostics"] for c in report["per_case"]}

    assert diag["latin"]["label_method"] == "lexical_pattern (inferred from note)"
    assert diag["latin"]["query_script"] == "Latn"
    assert diag["latin"]["labelled_by_script"] == {"Latn": len(latin_pandu)}
    assert diag["latin"]["labelled_top_sources"] == {"src-pandu": len(latin_pandu)}
    assert diag["latin"]["answerable_in_query_script"] is True

    assert diag["deva-no-target"]["label_method"] == "human_reviewed"
    assert diag["deva-no-target"]["query_script"] == "Deva"
    assert diag["deva-no-target"]["answerable_in_query_script"] is False
    assert diag["deva-no-target"]["labelled_chunks_missing_from_store"] == 1

    assert diag["deva-target"]["label_method"] == "unspecified"
    assert diag["deva-target"]["answerable_in_query_script"] is True
    assert sum(diag["latin"]["hits_by_script"].values()) == 3


def test_report_shape_is_unchanged_without_details(tmp_path):
    index, chunks, _ = diagnostic_index(tmp_path)
    case = RetrievalCase(case_id="c", query="pallor",
                         relevant_chunk_ids=[chunks[0].chunk_id])
    report = evaluate_retrieval(index, [case], top_k=3)
    assert set(report["per_case"][0]) == {"case_id", "rank", "top_similarity"}


def test_old_case_files_still_load_without_label_method():
    case = RetrievalCase.model_validate_json(
        '{"case_id": "c", "query": "q", "relevant_chunk_ids": ["a"], "note": "free text"}'
    )
    assert case.label_method is None
    assert label_method_of(case) == "unspecified"


def two_model_store(tmp_path):
    chunks = corpus_chunks()
    for model_id in ("test-keyword-encoder", "other/model"):
        build_embedding_store(chunks, RecordingEncoder(model_id), tmp_path / "store", SETTINGS)
    indexes = [
        SourceChunkIndex(tmp_path / "store", RecordingEncoder(m), SETTINGS)
        for m in ("test-keyword-encoder", "other/model")
    ]
    return indexes, chunks


def test_pool_merges_models_and_leaves_judgements_empty(tmp_path):
    indexes, chunks = two_model_store(tmp_path)
    labelled = chunks[0].chunk_id
    case = RetrievalCase(case_id="c1", query="pallor fatigue pandu",
                         relevant_chunk_ids=[labelled])

    rows = build_relevance_pool(indexes, [case], top_k=2)

    assert len({row["chunk_id"] for row in rows}) == len(rows)  # one row per passage
    for row in rows:
        assert row["case_id"] == "c1" and row["text"]
        assert "rank:test-keyword-encoder" in row and "rank:other/model" in row
        assert row["judgement"] == row["reviewer"] == row["review_notes"] == ""
    assert any(row["in_existing_labels"] for row in rows)
    best = [min(r["rank:test-keyword-encoder"] or 99, r["rank:other/model"] or 99) for r in rows]
    assert best == sorted(best)


def test_pool_csv_keeps_indic_text(tmp_path):
    rows = [{"case_id": "c", "text": f"{DEVANAGARI} पाठ", "judgement": ""}]
    path = write_relevance_pool(rows, tmp_path / "pool" / "pool.csv")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        (row,) = list(csv.DictReader(handle))
    assert row["text"] == f"{DEVANAGARI} पाठ"
    with pytest.raises(ValueError):
        write_relevance_pool([], tmp_path / "empty.csv")


def test_cli_search_pool_and_details_never_touch_the_cases_file(tmp_path, capsys):
    two_model_store(tmp_path)
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps({
        "case_id": "c1", "query": "pallor fatigue",
        "relevant_chunk_ids": [corpus_chunks()[0].chunk_id],
    }) + "\n", encoding="utf-8")
    before = cases_path.read_bytes()
    store = str(tmp_path / "store")

    with patch(
        "app.knowledge_ingestion.cli._make_encoder",
        lambda settings, allow: RecordingEncoder(settings.embedding_model),
    ):
        assert main(["search-pool", str(cases_path), "--store", store,
                     "--out", str(cases_path),
                     "--model", "test-keyword-encoder"]) == 2
        out = tmp_path / "eval" / "pool.csv"
        assert main(["search-pool", str(cases_path), "--store", store,
                     "--out", str(out), "--model", "test-keyword-encoder",
                     "--model", "other/model", "--top-k", "2"]) == 0
        assert out.is_file()
        capsys.readouterr()

        assert main(["search-eval", str(cases_path), "--store", store,
                     "--details"]) == 3  # configured model has no store here
        capsys.readouterr()

    assert cases_path.read_bytes() == before


def test_settings_for_a_named_model_use_family_prefixes(monkeypatch):
    monkeypatch.setenv("C2_SOURCE_EMBEDDING_QUERY_PREFIX", "custom: ")
    assert load_source_retrieval_settings().query_prefix == "custom: "
    e5 = load_source_retrieval_settings("intfloat/multilingual-e5-small")
    assert (e5.query_prefix, e5.passage_prefix) == ("query: ", "passage: ")
    minilm = load_source_retrieval_settings("sentence-transformers/all-MiniLM-L6-v2")
    assert (minilm.query_prefix, minilm.passage_prefix) == ("", "")


def test_pool_compares_one_model_over_two_corpora(tmp_path):
    chunks = corpus_chunks()
    encoder = RecordingEncoder("test-keyword-encoder")
    build_embedding_store(chunks[:1], encoder, tmp_path / "baseline", SETTINGS)
    build_embedding_store(chunks, encoder, tmp_path / "extended", SETTINGS)
    indexes = [SourceChunkIndex(tmp_path / root, encoder, SETTINGS)
               for root in ("baseline", "extended")]
    case = RetrievalCase(case_id="c1", query="pallor fatigue pandu", relevant_chunk_ids=[])

    rows = build_relevance_pool(indexes, [case], top_k=3, labels=["baseline", "extended"])

    assert all("rank:baseline" in row and "rank:extended" in row for row in rows)
    # Passages only in the extended corpus have no baseline rank.
    assert any(row["rank:baseline"] is None and row["rank:extended"] for row in rows)
    with pytest.raises(ValueError, match="distinct label"):
        build_relevance_pool(indexes, [case], labels=["same", "same"])
