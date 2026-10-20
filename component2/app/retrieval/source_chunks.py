"""Embedding store and semantic search over source-book chunks.

Source chunks (app.knowledge_ingestion) are unreviewed source text, not
curated evidence. Every search hit is labelled
evidence_status="unreviewed_source_text", and this index is deliberately
NOT wired into the reasoning pipeline or EvidenceRetrievalService: it is a
curation and review aid until reviewed knowledge exists.

It reuses the existing EmbeddingEncoder interface, normalize_rows() and
RetrievalSettings. A store is one directory per embedding model:

    <store_root>/<model slug>/manifest.json   model, dimension, prefixes
    <store_root>/<model slug>/vectors.npy     float32 [chunks x dimension]
    <store_root>/<model slug>/chunks.jsonl    row -> chunk ID and provenance

Vectors from different models or dimensions are never mixed: a store
refuses an encoder whose model ID, prefixes or output dimension differ.
Similarity values are cosine similarities (retrieval relevance only).
"""

import csv
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Callable, Iterable, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.config import RetrievalSettings
from app.knowledge_ingestion.models import PassageSpan, TextChunk
from app.knowledge_ingestion.normalization import profile_scripts
from app.retrieval.embedding import EmbeddingEncoder, normalize_rows


STORE_VERSION = 1
UNREVIEWED_SOURCE_TEXT = "unreviewed_source_text"
# Rows scored per block during search, to bound memory on a small VPS.
_SEARCH_BLOCK_ROWS = 20000


class EmbeddingStoreError(RuntimeError):
    """The store is missing, inconsistent or built with another model."""


class EmbeddingDimensionError(EmbeddingStoreError):
    """Vectors of different dimensions would be mixed in one store."""


class StoredChunk(BaseModel):
    """Chunk provenance kept next to its vector (no original_text copy)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    chunk_index: int
    text: str
    content_sha256: str
    passage_spans: list[PassageSpan]
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    section_heading: str | None = None
    item_id: str | None = None
    verse_numbers: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)
    printed_pages: list[str] = Field(default_factory=list)
    primary_script: str
    scripts: list[str] = Field(default_factory=list)
    iast_present: bool = False
    declared_source_language: str | None = None
    declared_translation_language: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    chunker_version: str
    normalization_version: str

    @classmethod
    def from_chunk(cls, chunk: TextChunk) -> "StoredChunk":
        return cls.model_validate(chunk.model_dump(exclude={"original_text"}))


class EmbeddingStoreManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_version: int = STORE_VERSION
    model_id: str
    dimension: int = Field(ge=1)
    normalized: bool = True
    query_prefix: str = ""
    passage_prefix: str = ""
    chunk_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    chunker_versions: list[str] = Field(default_factory=list)
    normalization_versions: list[str] = Field(default_factory=list)
    library_versions: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SourceChunkHit(BaseModel):
    chunk: StoredChunk
    similarity: float = Field(
        description="Cosine similarity: retrieval relevance only."
    )
    below_threshold: bool
    evidence_status: Literal["unreviewed_source_text"] = UNREVIEWED_SOURCE_TEXT


def model_slug(model_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", model_id).strip("_") or "model"


def store_dir_for(store_root: str | Path, model_id: str) -> Path:
    return Path(store_root) / model_slug(model_id)


def _library_versions() -> dict[str, str]:
    versions = {}
    for package in ("sentence-transformers", "transformers", "torch", "numpy"):
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            continue
    return versions


def _is_model_store(directory: Path) -> bool:
    # A source manifest (corpus/extracted/manifest.json) also exists, so a
    # store is recognised by its manifest and vectors together.
    return (directory / "manifest.json").is_file() and (
        directory / "vectors.npy"
    ).is_file()


def describe_missing_store(store_root: str | Path, model_id: str) -> str:
    """Explain why no store for model_id was found under store_root.

    --store names the store ROOT; each model has its own subdirectory
    (store_dir_for). The message names the full path that was checked and
    points out the common mistakes.
    """
    root = Path(store_root)
    expected = store_dir_for(root, model_id)
    message = (
        f"No embedding store for model {model_id!r} at {expected.as_posix()}."
    )
    if not root.is_dir():
        return (
            f"{message} The store root {root.as_posix()} does not exist; "
            "--store must be the directory that holds one subdirectory per "
            "model (for example corpus/extracted/embeddings)."
        )
    if _is_model_store(root):
        return (
            f"{message} {root.as_posix()} is itself a model store; pass its "
            f"parent directory ({root.parent.as_posix()}) as --store."
        )
    available = sorted(
        child.name for child in root.iterdir()
        if child.is_dir() and _is_model_store(child)
    )
    if available:
        return (
            f"{message} Stores under {root.as_posix()}: {', '.join(available)}. "
            "Check C2_SOURCE_EMBEDDING_MODEL, or build this model's store "
            "with the embed command."
        )
    return (
        f"{message} {root.as_posix()} contains no model stores; build one "
        "with the embed command."
    )


def read_store_manifest(store_dir: str | Path) -> EmbeddingStoreManifest:
    path = Path(store_dir) / "manifest.json"
    if not path.is_file():
        raise EmbeddingStoreError(
            f"No embedding store at {Path(store_dir).as_posix()}."
        )
    return EmbeddingStoreManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _load_stored_chunks(path: Path) -> list[StoredChunk]:
    with path.open(encoding="utf-8") as handle:
        return [
            StoredChunk.model_validate_json(line)
            for line in handle
            if line.strip()
        ]


def _encode_checked(
    encoder: EmbeddingEncoder,
    texts: list[str],
    dimension: int | None,
) -> np.ndarray:
    vectors = normalize_rows(encoder.encode(texts))
    if vectors.shape[0] != len(texts):
        raise EmbeddingStoreError(
            "Encoder returned a different number of embeddings than texts."
        )
    if dimension is not None and vectors.shape[1] != dimension:
        raise EmbeddingDimensionError(
            f"Encoder produced {vectors.shape[1]}-dimensional vectors; "
            f"the store holds {dimension}-dimensional vectors."
        )
    return vectors


def _write_atomic(path: Path, write: Callable[[Path], None]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    write(temporary)
    os.replace(temporary, path)


def build_embedding_store(
    chunks: Iterable[TextChunk],
    encoder: EmbeddingEncoder,
    store_root: str | Path,
    settings: RetrievalSettings,
    rebuild: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Create or update the store for encoder.model_id from chunks.

    Vectors are reused for chunks whose chunk_id and content_sha256 are
    unchanged; only new or changed chunks are encoded, in batches of
    settings.batch_size. Chunks no longer supplied are dropped. Files are
    replaced atomically, so an interrupted run leaves the previous store.

    Raises EmbeddingStoreError if an existing store used another model or
    prefixes (unless rebuild=True), EmbeddingDimensionError on dimension
    mismatch, and EmbeddingModelUnavailableError if encoding fails.
    """
    started = time.perf_counter()
    store_dir = store_dir_for(store_root, encoder.model_id)
    existing_rows: dict[tuple[str, str], int] = {}
    existing_vectors = None
    dimension: int | None = None
    created_at = datetime.now(timezone.utc)

    if (store_dir / "manifest.json").is_file() and not rebuild:
        manifest = read_store_manifest(store_dir)
        if (
            manifest.model_id != encoder.model_id
            or manifest.passage_prefix != settings.passage_prefix
            or manifest.query_prefix != settings.query_prefix
        ):
            raise EmbeddingStoreError(
                "Existing store was built with a different model or "
                "prefixes; rebuild it or use another store directory."
            )
        dimension = manifest.dimension
        created_at = manifest.created_at
        existing_vectors = np.load(store_dir / "vectors.npy", mmap_mode="r")
        stored = _load_stored_chunks(store_dir / "chunks.jsonl")
        if existing_vectors.shape != (len(stored), dimension):
            raise EmbeddingStoreError(
                "Existing store is inconsistent; rebuild it."
            )
        existing_rows = {
            (chunk.chunk_id, chunk.content_sha256): row
            for row, chunk in enumerate(stored)
        }

    records: list[StoredChunk] = []
    seen: set[str] = set()
    duplicates = 0
    for chunk in chunks:
        if chunk.chunk_id in seen:
            duplicates += 1
            continue
        seen.add(chunk.chunk_id)
        records.append(StoredChunk.from_chunk(chunk))

    pending = [
        index
        for index, record in enumerate(records)
        if (record.chunk_id, record.content_sha256) not in existing_rows
    ]
    batch_size = max(1, settings.batch_size)
    new_vectors: dict[int, np.ndarray] = {}
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        vectors = _encode_checked(
            encoder,
            [settings.passage_prefix + records[i].text for i in batch],
            dimension,
        )
        dimension = vectors.shape[1]
        for index, vector in zip(batch, vectors):
            new_vectors[index] = vector
        if progress:
            progress(min(offset + batch_size, len(pending)), len(pending))

    if dimension is None:
        if records:
            raise EmbeddingStoreError("No vectors available to build a store.")
        # Nothing to embed and no previous store: establish the dimension.
        dimension = _encode_checked(encoder, ["dimension check"], None).shape[1]

    matrix = np.zeros((len(records), dimension), dtype=np.float32)
    reused = 0
    for index, record in enumerate(records):
        if index in new_vectors:
            matrix[index] = new_vectors[index]
        else:
            matrix[index] = existing_vectors[
                existing_rows[(record.chunk_id, record.content_sha256)]
            ]
            reused += 1
    removed = len(set(existing_rows) - {
        (record.chunk_id, record.content_sha256) for record in records
    })
    existing_vectors = None  # release the memory map before replacing

    store_dir.mkdir(parents=True, exist_ok=True)

    def write_vectors(path: Path) -> None:
        with path.open("wb") as handle:
            np.save(handle, matrix)

    def write_chunks(path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(record.model_dump_json() + "\n")

    _write_atomic(store_dir / "vectors.npy", write_vectors)
    _write_atomic(store_dir / "chunks.jsonl", write_chunks)

    manifest = EmbeddingStoreManifest(
        model_id=encoder.model_id,
        dimension=dimension,
        query_prefix=settings.query_prefix,
        passage_prefix=settings.passage_prefix,
        chunk_count=len(records),
        source_count=len({record.source_id for record in records}),
        chunker_versions=sorted({r.chunker_version for r in records}),
        normalization_versions=sorted(
            {r.normalization_version for r in records}
        ),
        library_versions=_library_versions(),
        created_at=created_at,
        updated_at=datetime.now(timezone.utc),
    )
    _write_atomic(
        store_dir / "manifest.json",
        lambda path: path.write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        ),
    )
    return {
        "store_dir": str(store_dir),
        "model_id": encoder.model_id,
        "dimension": dimension,
        "chunks": len(records),
        "embedded": len(new_vectors),
        "reused": reused,
        "removed": removed,
        "duplicates_skipped": duplicates,
        "seconds": round(time.perf_counter() - started, 1),
    }


class SourceChunkIndex:
    """Read-only semantic search over one embedding store."""

    def __init__(
        self,
        store_root: str | Path,
        encoder: EmbeddingEncoder,
        settings: RetrievalSettings,
    ) -> None:
        self._encoder = encoder
        self._settings = settings
        store_dir = store_dir_for(store_root, encoder.model_id)
        if not (store_dir / "manifest.json").is_file():
            raise EmbeddingStoreError(
                describe_missing_store(store_root, encoder.model_id)
            )
        self.manifest = read_store_manifest(store_dir)
        if self.manifest.model_id != encoder.model_id:
            raise EmbeddingStoreError(
                "Store was built with a different embedding model."
            )
        if self.manifest.query_prefix != settings.query_prefix:
            raise EmbeddingStoreError(
                "Configured query prefix differs from the store's prefix."
            )
        self._vectors = np.load(store_dir / "vectors.npy", mmap_mode="r")
        self._chunks = _load_stored_chunks(store_dir / "chunks.jsonl")
        if self._vectors.shape != (len(self._chunks), self.manifest.dimension):
            raise EmbeddingDimensionError(
                "Store vectors do not match its manifest; rebuild it."
            )

    def get_chunk(self, chunk_id: str) -> StoredChunk | None:
        """The stored chunk with this ID, or None if it is not in the store."""
        if not hasattr(self, "_by_id"):
            self._by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        return self._by_id.get(chunk_id)

    @property
    def size(self) -> int:
        return len(self._chunks)

    def _candidate_rows(
        self,
        scripts: set[str] | None,
        source_ids: set[str] | None,
        languages: set[str] | None,
        exclude_flags: set[str] | None = None,
    ) -> np.ndarray:
        rows = []
        for row, chunk in enumerate(self._chunks):
            if exclude_flags and exclude_flags & set(chunk.quality_flags):
                continue
            if source_ids is not None and chunk.source_id not in source_ids:
                continue
            if scripts is not None and not (
                chunk.primary_script in scripts or scripts & set(chunk.scripts)
            ):
                continue
            if languages is not None and not (
                {chunk.declared_source_language,
                 chunk.declared_translation_language} & languages
            ):
                continue
            rows.append(row)
        return np.asarray(rows, dtype=np.int64)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        scripts: Iterable[str] | None = None,
        source_ids: Iterable[str] | None = None,
        declared_languages: Iterable[str] | None = None,
        max_per_source: int | None = None,
        include_below_threshold: bool = False,
        exclude_flags: Iterable[str] | None = None,
    ) -> list[SourceChunkHit]:
        """Return the chunks most similar to query, best first.

        Filters narrow the candidates by script, source or declared
        language; exclude_flags drops chunks carrying any of the given
        quality flags (nothing is excluded unless asked). max_per_source limits hits from any one source, for
        source-level deduplication. Ordering is by similarity, then
        chunk_id. Raises EmbeddingModelUnavailableError if encoding fails.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text.")
        top_k = top_k or self._settings.top_k
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        if max_per_source is not None and max_per_source < 1:
            raise ValueError("max_per_source must be positive.")

        rows = self._candidate_rows(
            set(scripts) if scripts is not None else None,
            set(source_ids) if source_ids is not None else None,
            set(declared_languages) if declared_languages is not None else None,
            set(exclude_flags) if exclude_flags else None,
        )
        if rows.size == 0:
            return []

        query_vector = _encode_checked(
            self._encoder,
            [self._settings.query_prefix + query.strip()],
            self.manifest.dimension,
        )[0]
        scores = np.empty(rows.size, dtype=np.float32)
        for start in range(0, rows.size, _SEARCH_BLOCK_ROWS):
            block = rows[start:start + _SEARCH_BLOCK_ROWS]
            scores[start:start + block.size] = (
                np.asarray(self._vectors[block]) @ query_vector
            )

        ranked = sorted(
            zip((round(float(s), 6) for s in scores), rows.tolist()),
            key=lambda item: (-item[0], self._chunks[item[1]].chunk_id),
        )
        hits: list[SourceChunkHit] = []
        per_source: dict[str, int] = {}
        for similarity, row in ranked:
            chunk = self._chunks[row]
            below = similarity < self._settings.min_similarity
            if below and not include_below_threshold:
                break
            if max_per_source is not None:
                if per_source.get(chunk.source_id, 0) >= max_per_source:
                    continue
                per_source[chunk.source_id] = per_source.get(chunk.source_id, 0) + 1
            hits.append(
                SourceChunkHit(
                    chunk=chunk, similarity=similarity, below_threshold=below
                )
            )
            if len(hits) >= top_k:
                break
        return hits


class RetrievalCase(BaseModel):
    """One evaluation query with the sources or chunks judged relevant."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    query: str = Field(min_length=1)
    relevant_source_ids: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    scripts: list[str] | None = None
    note: str | None = None
    # How the relevance labels were made, e.g. "lexical_pattern" or
    # "human_reviewed". Optional so older case files still load.
    label_method: str | None = None


def label_method_of(case: RetrievalCase) -> str:
    """The declared label method; inferred only from an explicit note."""
    if case.label_method:
        return case.label_method
    if case.note and case.note.lower().startswith("lexical label"):
        return "lexical_pattern (inferred from note)"
    return "unspecified"


def load_retrieval_cases(path: str | Path) -> list[RetrievalCase]:
    with Path(path).open(encoding="utf-8") as handle:
        cases = [
            RetrievalCase.model_validate_json(line)
            for line in handle
            if line.strip()
        ]
    for case in cases:
        if not case.relevant_source_ids and not case.relevant_chunk_ids:
            raise ValueError(f"Case {case.case_id} lists nothing relevant.")
    return cases


def case_diagnostics(
    index: SourceChunkIndex,
    case: RetrievalCase,
    hits: list[SourceChunkHit],
) -> dict:
    """Describe a case's labels and results so failures can be interpreted.

    Reports how labels were made, what the labelled set contains (by script
    and source), whether any labelled chunk is written in the query's
    script ("answerable_in_query_script"), labelled IDs missing from the
    store, and the scripts and quality flags of the retrieved hits. It does
    not judge relevance and does not change any label.
    """
    query_profile = profile_scripts(case.query)
    labelled = [index.get_chunk(chunk_id) for chunk_id in case.relevant_chunk_ids]
    present = [chunk for chunk in labelled if chunk is not None]
    script_counts = Counter(chunk.primary_script for chunk in present)
    source_counts = Counter(chunk.source_id for chunk in present)
    query_script = query_profile.primary_script
    if query_script in ("unknown", "mixed"):
        answerable = None
    else:
        answerable = any(
            query_script == chunk.primary_script or query_script in chunk.scripts
            for chunk in present
        )
    return {
        "label_method": label_method_of(case),
        "query_script": query_script,
        "query_scripts": query_profile.scripts,
        "query_iast": query_profile.iast_present,
        "labelled_chunks": len(case.relevant_chunk_ids),
        "labelled_chunks_missing_from_store": len(labelled) - len(present),
        "labelled_sources": len(case.relevant_source_ids),
        "labelled_by_script": dict(sorted(script_counts.items())),
        "labelled_top_sources": dict(source_counts.most_common(5)),
        "answerable_in_query_script": answerable,
        "hits_by_script": dict(sorted(
            Counter(hit.chunk.primary_script for hit in hits).items()
        )),
        "hits_with_quality_flags": sum(1 for hit in hits if hit.chunk.quality_flags),
    }


def evaluate_retrieval(
    index: SourceChunkIndex,
    cases: list[RetrievalCase],
    top_k: int = 10,
    exclude_flags: Iterable[str] | None = None,
    details: bool = False,
) -> dict:
    """Hit rate and mean reciprocal rank over hand-labelled cases.

    A hit is the first result whose chunk_id is in relevant_chunk_ids or
    whose source_id is in relevant_source_ids. These numbers are only as
    good as the labelled cases; a handful of cases is not a validation.
    """
    per_case = []
    for case in cases:
        hits = index.search(
            case.query,
            top_k=top_k,
            scripts=case.scripts,
            include_below_threshold=True,
            exclude_flags=exclude_flags,
        )
        rank = None
        for position, hit in enumerate(hits, start=1):
            if (
                hit.chunk.chunk_id in case.relevant_chunk_ids
                or hit.chunk.source_id in case.relevant_source_ids
            ):
                rank = position
                break
        entry = {
            "case_id": case.case_id,
            "rank": rank,
            "top_similarity": hits[0].similarity if hits else None,
        }
        if details:
            entry["diagnostics"] = case_diagnostics(index, case, hits)
        per_case.append(entry)
    count = len(per_case) or 1
    return {
        "model_id": index.manifest.model_id,
        "excluded_flags": sorted(exclude_flags or []),
        "cases": len(per_case),
        "top_k": top_k,
        f"hit_rate@{top_k}": round(
            sum(1 for c in per_case if c["rank"]) / count, 4
        ),
        "hit_rate@1": round(
            sum(1 for c in per_case if c["rank"] == 1) / count, 4
        ),
        "mrr": round(
            sum(1 / c["rank"] for c in per_case if c["rank"]) / count, 4
        ),
        "per_case": per_case,
    }


# --- pooling for human relevance review --------------------------------------

POOL_JUDGEMENT_COLUMNS = ("judgement", "reviewer", "review_notes")


def build_relevance_pool(
    indexes: list[SourceChunkIndex],
    cases: list[RetrievalCase],
    top_k: int = 10,
    labels: list[str] | None = None,
) -> list[dict]:
    """Pool the top-k results of several models per case for human review.

    Each row is one (case, chunk) pair retrieved by at least one model, with
    every model's rank and similarity, whether the chunk is in the case's
    existing automatic labels, its provenance and its normalized text. The
    judgement columns are left empty: relevance is decided by a reviewer,
    never here. Rows are ordered by case, best rank across models, chunk ID.
    """
    rows: list[dict] = []
    # Column keys: the model ID by default, or a system label when the same
    # model is compared over different stores (e.g. corpus experiments).
    model_ids = labels or [index.manifest.model_id for index in indexes]
    if len(set(model_ids)) != len(model_ids):
        raise ValueError("Each compared system needs a distinct label.")
    for case in cases:
        labelled = set(case.relevant_chunk_ids)
        pooled: dict[str, dict] = {}
        for index, model_id in zip(indexes, model_ids):
            hits = index.search(case.query, top_k=top_k, include_below_threshold=True)
            for rank, hit in enumerate(hits, start=1):
                chunk = hit.chunk
                row = pooled.setdefault(chunk.chunk_id, {
                    "case_id": case.case_id,
                    "query": case.query,
                    "chunk_id": chunk.chunk_id,
                    "source_id": chunk.source_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "section_heading": chunk.section_heading,
                    "primary_script": chunk.primary_script,
                    "quality_flags": ";".join(chunk.quality_flags),
                    "in_existing_labels": chunk.chunk_id in labelled,
                    "label_method": label_method_of(case),
                    "text": chunk.text,
                })
                row[f"rank:{model_id}"] = rank
                row[f"similarity:{model_id}"] = hit.similarity
        for row in pooled.values():
            for model_id in model_ids:
                row.setdefault(f"rank:{model_id}", None)
                row.setdefault(f"similarity:{model_id}", None)
            for column in POOL_JUDGEMENT_COLUMNS:
                row[column] = ""
        rows.extend(sorted(
            pooled.values(),
            key=lambda row: (
                min(row[f"rank:{m}"] or top_k + 1 for m in model_ids),
                row["chunk_id"],
            ),
        ))
    return rows


def write_relevance_pool(rows: list[dict], path: str | Path) -> Path:
    """Write pool rows as CSV (UTF-8 with BOM so spreadsheets keep scripts).

    The file contains source-book text: keep it in a git-ignored location.
    """
    path = Path(path)
    if not rows:
        raise ValueError("Nothing to write: the pool is empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path
