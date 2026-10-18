"""Runtime configuration for Component 2 retrieval and reasoning.

Values are read from environment variables so that model identifiers,
thresholds and limits stay outside the source code. All numeric
thresholds here are provisional engineering defaults, not clinically
validated values.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")
    return value


def _env_float(
    name: str,
    default: float,
    minimum: float = -1.0,
    maximum: float = 1.0,
) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw)
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}."
        )
    return value


@dataclass(frozen=True)
class RetrievalSettings:
    """Embedding model and vector-search configuration."""

    # Hugging Face model identifier or a local directory path.
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    device: str = "cpu"
    batch_size: int = 32
    # Optional directory for cached model files.
    cache_folder: str | None = None
    top_k: int = 5
    # Cosine similarity below this value is flagged as low relevance.
    # Provisional: chosen for MiniLM-style models, not validated.
    min_similarity: float = 0.30
    chunk_max_chars: int = 800
    chunk_overlap_chars: int = 100


def load_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings(
        embedding_model=(
            os.getenv("C2_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
        ).strip(),
        device=(os.getenv("C2_EMBEDDING_DEVICE") or "cpu").strip(),
        batch_size=_env_int("C2_EMBEDDING_BATCH_SIZE", 32),
        cache_folder=os.getenv("C2_EMBEDDING_CACHE_DIR") or None,
        top_k=_env_int("C2_RETRIEVAL_TOP_K", 5),
        min_similarity=_env_float("C2_RETRIEVAL_MIN_SIMILARITY", 0.30),
        chunk_max_chars=_env_int("C2_CHUNK_MAX_CHARS", 800, minimum=50),
        chunk_overlap_chars=_env_int(
            "C2_CHUNK_OVERLAP_CHARS", 100, minimum=0
        ),
    )
