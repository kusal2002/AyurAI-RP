"""Orchestration of source inspection, extraction and manifest building.

Each stage is a plain function so it can be tested and reused without
FastAPI. Files are processed one at a time; passages of one book are held
in memory only while that book is written out.

Outputs written by write_extraction():

* <source_id>.extraction.json  -- source record and extraction summary
* <source_id>.passages.jsonl   -- one extracted passage per line
* <source_id>.chunks.jsonl     -- chunks (written by the chunk stage)

These files contain source-book text. Keep them out of version control
(corpus/extracted/ is git-ignored) and do not publish them.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import IngestionSettings, load_ingestion_settings
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.extractors import extract_document
from app.knowledge_ingestion.manifest import (
    SourceMetadataError,
    assemble_manifest,
    build_source_record,
    iter_source_files,
    load_sidecar_metadata,
    sha256_file,
)
from app.knowledge_ingestion.models import (
    ExtractedPassage,
    ExtractionResult,
    SourceManifest,
    SourceMetadata,
    SourceRecord,
    TextChunk,
)


class SourceOutsideRootError(ValueError):
    """A source file does not lie under the declared corpus root."""


def corpus_relative_path(path: str | Path, root: str | Path) -> str:
    """Path of a source relative to its corpus root, with '/' separators.

    Matches the relative paths build_manifest() records (via
    iter_source_files), so filters such as --path-filter behave the same
    for manifest and direct extraction. Both paths are resolved first.

    Raises NotADirectoryError if root is not a directory and
    SourceOutsideRootError if path is not under root.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"Corpus root is not a directory: {root}")
    try:
        relative = Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        raise SourceOutsideRootError(
            f"Source {Path(path).name} is not inside the corpus root {root}; "
            "pass the root that contains it, or omit --root."
        ) from None
    return relative.as_posix()


@dataclass
class SourceExtraction:
    record: SourceRecord
    result: ExtractionResult


def process_source(
    path: str | Path,
    relative_path: str | None = None,
    metadata: SourceMetadata | None = None,
    settings: IngestionSettings | None = None,
) -> SourceExtraction:
    """Hash, identify and extract one existing local file.

    Metadata comes from the argument, else from a '<file>.meta.json'
    sidecar. An invalid sidecar is reported in the record's errors and the
    content-derived source_id is used instead.

    Raises FileNotFoundError if path is not an existing file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Source file not found: {path.name}")

    metadata_errors: list[str] = []
    if metadata is None:
        try:
            metadata = load_sidecar_metadata(path)
        except SourceMetadataError as exc:
            metadata_errors.append(str(exc))
            metadata = None

    content_sha256 = sha256_file(path)
    result = extract_document(path, settings or load_ingestion_settings())
    record = build_source_record(
        path,
        relative_path or path.name,
        content_sha256,
        result,
        metadata,
        extra_errors=metadata_errors,
    )
    return SourceExtraction(record=record, result=result)


def extraction_summary(extraction: SourceExtraction) -> dict:
    """Summary without passage text, safe to print or log."""
    result = extraction.result
    return {
        "source": extraction.record.model_dump(mode="json"),
        "passages_by_kind": _count_kinds(result),
        "text_char_count": result.text_char_count,
        "blank_pages": result.blank_pages,
        "page_issues": [
            issue.model_dump(mode="json") for issue in result.page_issues
        ],
        "flagged_passages": sum(
            1 for passage in result.passages if passage.quality_flags
        ),
        "embedded_metadata": result.embedded_metadata,
    }


def _count_kinds(result: ExtractionResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for passage in result.passages:
        counts[passage.kind.value] = counts.get(passage.kind.value, 0) + 1
    return counts


def write_extraction(
    extraction: SourceExtraction,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    """Write the summary JSON and passages JSONL for one source.

    Re-running for the same source_id replaces the previous output, so
    repeated extraction is idempotent.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_id = extraction.record.source_id

    summary_path = out_dir / f"{source_id}.extraction.json"
    summary_path.write_text(
        json.dumps(extraction_summary(extraction), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    passages_path = out_dir / f"{source_id}.passages.jsonl"
    with passages_path.open("w", encoding="utf-8", newline="\n") as handle:
        for passage in extraction.result.passages:
            line = {"source_id": source_id, **passage.model_dump(mode="json")}
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    return summary_path, passages_path


def build_manifest(
    root: str | Path,
    extract_dir: str | Path | None = None,
    settings: IngestionSettings | None = None,
) -> SourceManifest:
    """Process every source file under root into a manifest.

    When extract_dir is given, each source's passages are written there as
    soon as it is processed and then released from memory.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"Source directory not found: {root.name}")
    settings = settings or load_ingestion_settings()

    records: list[SourceRecord] = []
    skipped: list[str] = []
    for path, relative in iter_source_files(root):
        if path is None:
            skipped.append(f"{relative} (symbolic link)")
            continue
        try:
            extraction = process_source(path, relative, settings=settings)
        except OSError as exc:
            skipped.append(f"{relative} ({type(exc).__name__})")
            continue
        if extract_dir is not None and extraction.result.passages:
            write_extraction(extraction, extract_dir)
        records.append(extraction.record)

    return assemble_manifest(records, skipped)


def update_manifest(
    manifest: SourceManifest,
    root: str | Path,
    path_prefixes: list[str],
    extract_dir: str | Path | None = None,
    settings: IngestionSettings | None = None,
) -> tuple[SourceManifest, list[str]]:
    """Re-process only files whose relative path starts with a prefix.

    Records of every other source are kept exactly as stored, so adding a
    few new sources does not re-extract a large corpus. A record whose
    relative path matches a prefix is replaced by the fresh result; one
    whose file has disappeared is dropped. Duplicate groups and source_id
    conflicts are recomputed over the merged records. Returns the new
    manifest and the relative paths that were processed.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"Source directory not found: {root.name}")
    if not path_prefixes:
        raise ValueError("At least one path prefix is required.")
    settings = settings or load_ingestion_settings()

    def selected(relative: str) -> bool:
        return any(relative.startswith(prefix) for prefix in path_prefixes)

    kept = [r for r in manifest.sources if not selected(r.relative_path)]
    skipped = [s for s in manifest.skipped_files if not selected(s.split(" (", 1)[0])]
    processed: list[str] = []
    fresh: list[SourceRecord] = []
    for path, relative in iter_source_files(root):
        if not selected(relative):
            continue
        if path is None:
            skipped.append(f"{relative} (symbolic link)")
            continue
        try:
            extraction = process_source(path, relative, settings=settings)
        except OSError as exc:
            skipped.append(f"{relative} ({type(exc).__name__})")
            continue
        if extract_dir is not None and extraction.result.passages:
            write_extraction(extraction, extract_dir)
        fresh.append(extraction.record)
        processed.append(relative)
    return assemble_manifest(kept + fresh, skipped), processed


def scan_hashes(root: str | Path) -> tuple[dict[str, list[str]], list[str]]:
    """Hash every source file under root without extracting it.

    Returns ({content_sha256: [relative paths]}, skipped) for a quick
    duplicate check over a large corpus.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"Source directory not found: {root.name}")
    by_hash: dict[str, list[str]] = {}
    skipped: list[str] = []
    for path, relative in iter_source_files(root):
        if path is None:
            skipped.append(f"{relative} (symbolic link)")
            continue
        try:
            by_hash.setdefault(sha256_file(path), []).append(relative)
        except OSError as exc:
            skipped.append(f"{relative} ({type(exc).__name__})")
    return by_hash, skipped


# --- Stage B: chunking of stored extraction output ---------------------------

def iter_extraction_summaries(path: str | Path) -> list[Path]:
    """Return '*.extraction.json' files: the path itself or those in a dir."""
    path = Path(path)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.extraction.json"))
    raise FileNotFoundError(f"Extraction output not found: {path.name}")


def load_extraction_output(
    summary_path: str | Path,
) -> tuple[SourceRecord, list[ExtractedPassage]]:
    """Read a source record and its passages written by write_extraction()."""
    summary_path = Path(summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    record = SourceRecord.model_validate(summary["source"])
    passages_path = summary_path.with_name(
        f"{record.source_id}.passages.jsonl"
    )
    passages = []
    with passages_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.pop("source_id", record.source_id) != record.source_id:
                raise ValueError(
                    f"{passages_path.name} contains passages of another source."
                )
            passages.append(ExtractedPassage.model_validate(data))
    return record, passages


def chunks_path(out_dir: str | Path, source_id: str) -> Path:
    return Path(out_dir) / f"{source_id}.chunks.jsonl"


def write_chunks(chunks: list[TextChunk], path: str | Path) -> Path:
    """Write chunks as JSON Lines, replacing any previous file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(chunk.model_dump_json() + "\n")
    return path


def load_chunks(path: str | Path) -> list[TextChunk]:
    with Path(path).open(encoding="utf-8") as handle:
        return [
            TextChunk.model_validate_json(line)
            for line in handle
            if line.strip()
        ]


def chunk_extraction_output(
    summary_path: str | Path,
    settings: IngestionSettings | None = None,
) -> tuple[SourceRecord, list[ExtractedPassage], list[TextChunk]]:
    settings = settings or load_ingestion_settings()
    record, passages = load_extraction_output(summary_path)
    chunks = chunk_passages(record.source_id, passages, settings, record.metadata)
    return record, passages, chunks
