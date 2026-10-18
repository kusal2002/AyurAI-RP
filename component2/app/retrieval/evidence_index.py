"""In-process vector index over stored evidence records.

Evidence text is split into overlapping character chunks. Every chunk
keeps its source evidence_id and provenance metadata, so each search hit
can be traced back to the original Evidence node.

Similarity values are cosine similarities between embeddings. They measure
retrieval relevance only and are not clinical or evidential confidence.
"""

import hashlib
import json
from typing import Any, Iterable

import numpy as np
from pydantic import BaseModel, Field

from app.retrieval.embedding import EmbeddingEncoder, normalize_rows


PROVENANCE_FIELDS = (
    "title",
    "source_name",
    "evidence_type",
    "section",
    "page",
    "citation",
    "source_url",
    "practitioner_verified",
)


class EvidenceChunk(BaseModel):
    chunk_id: str
    evidence_id: str
    chunk_index: int
    text: str
    title: str | None = None
    source_name: str | None = None
    evidence_type: str | None = None
    section: str | None = None
    page: str | None = None
    citation: str | None = None
    source_url: str | None = None
    practitioner_verified: bool = False


class RetrievedChunk(BaseModel):
    chunk: EvidenceChunk
    similarity: float = Field(
        description="Cosine similarity: retrieval relevance only."
    )
    below_threshold: bool


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, preferring whitespace breaks."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive.")
    if not 0 <= overlap < max_chars:
        raise ValueError("overlap must be >= 0 and smaller than max_chars.")

    text = " ".join(text.split())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))

        if end < len(text):
            split_at = text.rfind(" ", start + 1, end)
            if split_at > start:
                end = split_at

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks


def _fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "text": record.get("text"),
        **{field: record.get(field) for field in PROVENANCE_FIELDS},
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class EvidenceIndex:
    """Cosine-similarity index of evidence chunks held in memory.

    The index is rebuilt incrementally by refresh(): only evidence records
    whose text or provenance changed are re-embedded.
    """

    def __init__(
        self,
        encoder: EmbeddingEncoder,
        chunk_max_chars: int = 800,
        chunk_overlap_chars: int = 100,
    ) -> None:
        self._encoder = encoder
        self._chunk_max_chars = chunk_max_chars
        self._chunk_overlap_chars = chunk_overlap_chars
        self._chunks: list[EvidenceChunk] = []
        self._vectors: np.ndarray | None = None
        # evidence_id -> (fingerprint, chunks, vectors)
        self._by_evidence: dict[
            str, tuple[str, list[EvidenceChunk], np.ndarray]
        ] = {}
        self.skipped_evidence_ids: list[str] = []

    @property
    def model_id(self) -> str:
        return self._encoder.model_id

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def evidence_ids(self) -> list[str]:
        return sorted(self._by_evidence)

    def _make_chunks(self, record: dict[str, Any]) -> list[EvidenceChunk]:
        evidence_id = record["evidence_id"]
        pieces = chunk_text(
            record.get("text") or "",
            self._chunk_max_chars,
            self._chunk_overlap_chars,
        )
        metadata: dict[str, Any] = {}
        for field in PROVENANCE_FIELDS:
            value = record.get(field)
            if field == "practitioner_verified":
                metadata[field] = bool(value)
            elif value is not None:
                metadata[field] = str(value)

        return [
            EvidenceChunk(
                chunk_id=f"{evidence_id}#chunk-{index}",
                evidence_id=evidence_id,
                chunk_index=index,
                text=piece,
                **metadata,
            )
            for index, piece in enumerate(pieces)
        ]

    def refresh(self, records: Iterable[dict[str, Any]]) -> dict[str, int]:
        """Synchronize the index with the given evidence records.

        Records missing an evidence_id or text are skipped and reported in
        skipped_evidence_ids rather than silently dropped. Evidence no
        longer present in records is removed from the index.
        """
        incoming: dict[str, dict[str, Any]] = {}
        skipped: list[str] = []

        for record in records:
            evidence_id = record.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                skipped.append("<missing evidence_id>")
                continue
            text = record.get("text")
            if not isinstance(text, str) or not text.strip():
                skipped.append(evidence_id)
                continue
            incoming[evidence_id] = record

        to_embed: list[tuple[str, str, list[EvidenceChunk]]] = []
        for evidence_id, record in incoming.items():
            fingerprint = _fingerprint(record)
            existing = self._by_evidence.get(evidence_id)
            if existing is None or existing[0] != fingerprint:
                to_embed.append(
                    (evidence_id, fingerprint, self._make_chunks(record))
                )

        texts = [
            chunk.text for _, _, chunks in to_embed for chunk in chunks
        ]
        vectors = (
            normalize_rows(self._encoder.encode(texts))
            if texts
            else np.zeros((0, 0), dtype=np.float32)
        )
        if len(vectors) != len(texts):
            raise RuntimeError(
                "Encoder returned a different number of embeddings "
                "than input texts."
            )

        removed = [
            evidence_id
            for evidence_id in self._by_evidence
            if evidence_id not in incoming
        ]
        for evidence_id in removed:
            del self._by_evidence[evidence_id]

        offset = 0
        for evidence_id, fingerprint, chunks in to_embed:
            count = len(chunks)
            self._by_evidence[evidence_id] = (
                fingerprint,
                chunks,
                vectors[offset:offset + count],
            )
            offset += count

        self._rebuild_matrix()
        self.skipped_evidence_ids = skipped

        return {
            "indexed_evidence": len(self._by_evidence),
            "indexed_chunks": len(self._chunks),
            "embedded_evidence": len(to_embed),
            "removed_evidence": len(removed),
            "skipped_evidence": len(skipped),
        }

    def _rebuild_matrix(self) -> None:
        chunks: list[EvidenceChunk] = []
        blocks: list[np.ndarray] = []
        for evidence_id in sorted(self._by_evidence):
            _, evidence_chunks, vectors = self._by_evidence[evidence_id]
            chunks.extend(evidence_chunks)
            if len(evidence_chunks):
                blocks.append(vectors)
        self._chunks = chunks
        self._vectors = np.vstack(blocks) if blocks else None

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
        restrict_to_evidence_ids: Iterable[str] | None = None,
        include_below_threshold: bool = False,
    ) -> list[RetrievedChunk]:
        """Return the most similar chunks to the query.

        Results are ordered by descending similarity, then chunk_id, so
        ordering is deterministic for fixed embeddings. Below-threshold
        hits are omitted unless include_below_threshold is True, in which
        case they are returned with below_threshold=True.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text.")
        if top_k < 1:
            raise ValueError("top_k must be positive.")

        if self._vectors is None or not self._chunks:
            return []

        allowed = (
            set(restrict_to_evidence_ids)
            if restrict_to_evidence_ids is not None
            else None
        )
        candidate_rows = [
            row
            for row, chunk in enumerate(self._chunks)
            if allowed is None or chunk.evidence_id in allowed
        ]
        if not candidate_rows:
            return []

        query_vector = normalize_rows(self._encoder.encode([query.strip()]))
        similarities = self._vectors[candidate_rows] @ query_vector[0]

        scored = sorted(
            (
                (round(float(similarity), 6), self._chunks[row])
                for row, similarity in zip(candidate_rows, similarities)
            ),
            key=lambda item: (-item[0], item[1].chunk_id),
        )

        results = []
        for similarity, chunk in scored:
            below = similarity < min_similarity
            if below and not include_below_threshold:
                continue
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    similarity=similarity,
                    below_threshold=below,
                )
            )
            if len(results) >= top_k:
                break

        return results
