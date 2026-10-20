"""Runtime configuration for Component 2 retrieval and reasoning.

Values are read from environment variables so that model identifiers,
thresholds and limits stay outside the source code. All numeric
thresholds here are provisional engineering defaults, not clinically
validated values.
"""

import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv

load_dotenv()


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Model for the source-book chunk store (app.retrieval.source_chunks),
# chosen after the 2026-10-19 smoke comparison (docs/knowledge_ingestion.md).
# It is separate from DEFAULT_EMBEDDING_MODEL so the curated evidence index
# used by the API is not affected.
DEFAULT_SOURCE_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
# Role prefixes required by known model families, used when no explicit
# prefix is configured.
_MODEL_PREFIXES = {
    "intfloat/multilingual-e5-": ("query: ", "passage: "),
    "intfloat/e5-": ("query: ", "passage: "),
}


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
    # Text prepended before encoding, for models trained with role prefixes
    # (multilingual-e5 expects "query: " and "passage: "). Empty for
    # Sentence-BERT models such as MiniLM. Applied by the source-chunk
    # store only; the evidence index encodes text unchanged.
    query_prefix: str = ""
    passage_prefix: str = ""


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


def load_source_retrieval_settings(model_id: str | None = None) -> RetrievalSettings:
    """Settings for the source-book chunk store.

    Shares device, batch size, cache folder and top_k with the evidence
    index, but has its own model (C2_SOURCE_EMBEDDING_MODEL), prefixes and
    similarity threshold. The threshold defaults to 0.0 (no filtering):
    e5 similarities cluster around 0.85-0.91, so the evidence-index value
    of 0.30 would be meaningless, and no calibrated value exists yet.

    model_id selects another model's store (for example to compare models).
    Its prefixes then come from the model family; the prefix environment
    variables apply only to the configured model.
    """
    base = load_retrieval_settings()
    model = (
        model_id
        or os.getenv("C2_SOURCE_EMBEDDING_MODEL")
        or DEFAULT_SOURCE_EMBEDDING_MODEL
    ).strip()
    default_query, default_passage = next(
        (
            prefixes
            for family, prefixes in _MODEL_PREFIXES.items()
            if model.startswith(family)
        ),
        ("", ""),
    )
    # Prefixes are read verbatim: the trailing space is significant.
    query_prefix = passage_prefix = None
    if model_id is None:
        query_prefix = os.getenv("C2_SOURCE_EMBEDDING_QUERY_PREFIX")
        passage_prefix = os.getenv("C2_SOURCE_EMBEDDING_PASSAGE_PREFIX")
    return replace(
        base,
        embedding_model=model,
        query_prefix=default_query if query_prefix is None else query_prefix,
        passage_prefix=(
            default_passage if passage_prefix is None else passage_prefix
        ),
        min_similarity=_env_float("C2_SOURCE_RETRIEVAL_MIN_SIMILARITY", 0.0),
    )


@dataclass(frozen=True)
class IngestionSettings:
    """Limits and thresholds for source-document extraction.

    These are engineering safeguards, not quality guarantees. A page whose
    extracted text has fewer than min_page_text_chars non-whitespace
    characters is treated as having no usable text layer.
    """

    max_file_bytes: int = 512 * 1024 * 1024
    # Upper bound for any single member read from a DOCX or EPUB archive.
    max_archive_member_bytes: int = 64 * 1024 * 1024
    min_page_text_chars: int = 20
    # Fraction of U+FFFD or private-use characters above which extracted
    # text is flagged as probably garbled (missing font mappings, legacy
    # non-Unicode Sinhala fonts, damaged encodings).
    max_suspect_char_ratio: float = 0.05
    # Chunk size for source-book passages, in characters of normalized
    # text. Defaults match the evidence index (C2_CHUNK_*) so chunks suit
    # the same embedding model. Overlap is made of whole sentences or
    # verses, so the actual overlap may be shorter than this limit.
    chunk_max_chars: int = 800
    chunk_overlap_chars: int = 100

    def __post_init__(self) -> None:
        if self.chunk_max_chars < 50:
            raise ValueError("chunk_max_chars must be >= 50.")
        if not 0 <= self.chunk_overlap_chars < self.chunk_max_chars:
            raise ValueError(
                "chunk_overlap_chars must be >= 0 and smaller than "
                "chunk_max_chars."
            )


def load_ingestion_settings() -> IngestionSettings:
    return IngestionSettings(
        max_file_bytes=_env_int(
            "C2_INGEST_MAX_FILE_BYTES", 512 * 1024 * 1024
        ),
        max_archive_member_bytes=_env_int(
            "C2_INGEST_MAX_ARCHIVE_MEMBER_BYTES", 64 * 1024 * 1024
        ),
        min_page_text_chars=_env_int(
            "C2_INGEST_MIN_PAGE_TEXT_CHARS", 20, minimum=0
        ),
        max_suspect_char_ratio=_env_float(
            "C2_INGEST_MAX_SUSPECT_CHAR_RATIO", 0.05, minimum=0.0
        ),
        chunk_max_chars=_env_int(
            "C2_INGEST_CHUNK_MAX_CHARS", 800, minimum=50
        ),
        chunk_overlap_chars=_env_int(
            "C2_INGEST_CHUNK_OVERLAP_CHARS", 100, minimum=0
        ),
    )
