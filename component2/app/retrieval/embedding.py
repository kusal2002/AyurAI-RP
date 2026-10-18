"""Embedding encoders used for semantic evidence retrieval.

The default encoder wraps a pretrained Sentence Transformers model. The
model is loaded lazily on first use, never at import time. If loading
fails, EmbeddingModelUnavailableError is raised; no substitute or fake
embedding is produced.
"""

import threading
from typing import Protocol, Sequence

import numpy as np

from app.config import RetrievalSettings


class EmbeddingModelUnavailableError(RuntimeError):
    """Raised when the configured embedding model cannot be loaded or used."""


class EmbeddingEncoder(Protocol):
    """Interface for encoders. Tests inject deterministic implementations."""

    @property
    def model_id(self) -> str: ...

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return a 2-D float array with one L2-normalized row per text."""
        ...


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize each row; zero vectors stay zero."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2:
        raise ValueError("Embeddings must be a 2-D array.")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class SentenceTransformerEncoder:
    """Lazy-loading Sentence Transformers encoder for CPU inference."""

    def __init__(self, settings: RetrievalSettings) -> None:
        self._settings = settings
        self._model = None
        self._lock = threading.Lock()
        self._load_error: str | None = None

    @property
    def model_id(self) -> str:
        return self._settings.embedding_model

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            try:
                # Imported here so that importing the API never pulls in
                # torch or downloads model files.
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                self._load_error = "sentence-transformers is not installed"
                raise EmbeddingModelUnavailableError(
                    self._load_error
                ) from exc

            try:
                self._model = SentenceTransformer(
                    self._settings.embedding_model,
                    device=self._settings.device,
                    cache_folder=self._settings.cache_folder,
                )
            except Exception as exc:
                self._load_error = (
                    f"Embedding model {self.model_id!r} could not be "
                    f"loaded: {type(exc).__name__}"
                )
                raise EmbeddingModelUnavailableError(
                    self._load_error
                ) from exc

            self._load_error = None
            return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        texts = list(texts)
        model = self._load()

        if not texts:
            dimension = model.get_sentence_embedding_dimension() or 0
            return np.zeros((0, dimension), dtype=np.float32)

        try:
            vectors = model.encode(
                texts,
                batch_size=self._settings.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingModelUnavailableError(
                f"Embedding inference failed: {type(exc).__name__}"
            ) from exc

        return normalize_rows(vectors)
