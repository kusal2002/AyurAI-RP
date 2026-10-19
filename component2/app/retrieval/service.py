"""Semantic evidence retrieval service used by the reasoning pipeline.

The service owns one EvidenceIndex, built lazily from Evidence records
stored in Neo4j. When the embedding model cannot be loaded the service
reports mode "unavailable"; it never falls back to keyword matching or
fake embeddings.
"""

import logging
import threading
from enum import Enum
from typing import Any, Callable, Iterable

from neo4j import Driver

from app.config import RetrievalSettings, load_retrieval_settings
from app.db.repository import list_evidence
from app.retrieval.embedding import (
    EmbeddingEncoder,
    EmbeddingModelUnavailableError,
    SentenceTransformerEncoder,
)
from app.retrieval.evidence_index import EvidenceIndex, RetrievedChunk


logger = logging.getLogger(__name__)


class RetrievalMode(str, Enum):
    NEURAL_EMBEDDING = "neural_embedding"
    UNAVAILABLE = "unavailable"


EvidenceLoader = Callable[[Driver | None], Iterable[dict[str, Any]]]


class EvidenceRetrievalService:
    def __init__(
        self,
        settings: RetrievalSettings | None = None,
        encoder: EmbeddingEncoder | None = None,
        evidence_loader: EvidenceLoader | None = None,
    ) -> None:
        self.settings = settings or load_retrieval_settings()
        self._encoder = encoder or SentenceTransformerEncoder(self.settings)
        self._evidence_loader = evidence_loader or (
            lambda driver: list_evidence(driver)
        )
        self._index = EvidenceIndex(
            self._encoder,
            chunk_max_chars=self.settings.chunk_max_chars,
            chunk_overlap_chars=self.settings.chunk_overlap_chars,
        )
        self._indexed = False
        self._model_verified = False
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def model_id(self) -> str:
        return self._encoder.model_id

    @property
    def index(self) -> EvidenceIndex:
        return self._index

    @property
    def mode(self) -> RetrievalMode:
        return (
            RetrievalMode.UNAVAILABLE
            if self.last_error
            else RetrievalMode.NEURAL_EMBEDDING
        )

    def refresh(self, driver: Driver | None = None) -> dict[str, Any]:
        """Re-read stored evidence and update the vector index.

        Raises EmbeddingModelUnavailableError if the model cannot load.
        """
        with self._lock:
            records = list(self._evidence_loader(driver))
            try:
                if not self._model_verified:
                    # Confirm the model really loads even when the corpus
                    # is empty, so the reported mode is never optimistic.
                    self._encoder.encode(["embedding model availability check"])
                    self._model_verified = True
                stats = self._index.refresh(records)
            except EmbeddingModelUnavailableError as exc:
                self.last_error = str(exc)
                logger.warning(
                    "c2.retrieval.model_unavailable model=%s error=%s",
                    self.model_id,
                    self.last_error,
                )
                raise
            self._indexed = True
            self.last_error = None
            logger.info(
                "c2.retrieval.index_refreshed model=%s chunks=%d "
                "evidence=%d skipped=%d",
                self.model_id,
                stats["indexed_chunks"],
                stats["indexed_evidence"],
                stats["skipped_evidence"],
            )
            return stats

    def ensure_ready(self, driver: Driver | None = None) -> bool:
        """Build the index on first use. Returns False if unavailable."""
        if self._indexed:
            return True
        try:
            self.refresh(driver)
        except EmbeddingModelUnavailableError:
            return False
        return True

    def search(
        self,
        query: str,
        top_k: int | None = None,
        restrict_to_evidence_ids: Iterable[str] | None = None,
        include_below_threshold: bool = False,
    ) -> list[RetrievedChunk]:
        """Search the index. Raises EmbeddingModelUnavailableError."""
        try:
            return self._index.search(
                query,
                top_k=top_k or self.settings.top_k,
                min_similarity=self.settings.min_similarity,
                restrict_to_evidence_ids=restrict_to_evidence_ids,
                include_below_threshold=include_below_threshold,
            )
        except EmbeddingModelUnavailableError as exc:
            self.last_error = str(exc)
            raise


_default_service: EvidenceRetrievalService | None = None
_default_lock = threading.Lock()


def get_retrieval_service() -> EvidenceRetrievalService:
    """Return the process-wide retrieval service (created lazily).

    Creating the service does not load the model; that happens on the
    first index refresh or search.
    """
    global _default_service
    if _default_service is None:
        with _default_lock:
            if _default_service is None:
                _default_service = EvidenceRetrievalService()
    return _default_service
