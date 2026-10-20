"""Source fingerprints, stable identifiers, duplicates and manifests.

Source identity and file content are kept apart:

* content_sha256 identifies the exact bytes of a file.
* source_id identifies the work/edition. It comes from curator-supplied
  metadata when given; otherwise it is derived from the content hash, so a
  corrected or different edition never silently merges with another file.

Duplicate content is reported, never merged automatically. A source_id
reused for files with different content is reported as a conflict.
"""

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

from pydantic import ValidationError

from app.knowledge_ingestion.models import (
    DuplicateGroup,
    ExtractionResult,
    SourceIdConflict,
    SourceManifest,
    SourceMetadata,
    SourceRecord,
)


SIDECAR_SUFFIX = ".meta.json"


class SourceMetadataError(ValueError):
    """Raised when a metadata sidecar file is unreadable or invalid."""


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file in fixed-size chunks so large books are not loaded whole."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def derive_source_id(content_sha256: str) -> str:
    return f"src-{content_sha256[:16]}"


def sidecar_path(path: str | Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + SIDECAR_SUFFIX)


def load_source_metadata(path: str | Path) -> SourceMetadata:
    """Load and validate a metadata JSON file."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceMetadataError(
            f"Metadata file {path.name!r} could not be read "
            f"({type(exc).__name__})."
        ) from None
    try:
        return SourceMetadata.model_validate(raw)
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "(root)"
            for error in exc.errors()
        )
        raise SourceMetadataError(
            f"Metadata file {path.name!r} is invalid: {fields}."
        ) from None


def load_sidecar_metadata(path: str | Path) -> SourceMetadata | None:
    """Return metadata from '<file>.meta.json' next to the file, if any."""
    sidecar = sidecar_path(path)
    if not sidecar.is_file():
        return None
    return load_source_metadata(sidecar)


def build_source_record(
    path: Path,
    relative_path: str,
    content_sha256: str,
    extraction: ExtractionResult,
    metadata: SourceMetadata | None = None,
    extra_errors: Iterable[str] = (),
) -> SourceRecord:
    metadata = metadata or SourceMetadata()
    if metadata.source_id:
        source_id, origin = metadata.source_id, "metadata"
    else:
        source_id, origin = derive_source_id(content_sha256), "content_hash"

    return SourceRecord(
        source_id=source_id,
        source_id_origin=origin,
        file_name=path.name,
        relative_path=relative_path,
        source_format=extraction.source_format,
        file_size_bytes=path.stat().st_size,
        content_sha256=content_sha256,
        metadata=metadata,
        extraction_status=extraction.status,
        extractor=extraction.extractor,
        extractor_version=extraction.extractor_version,
        extracted_at=extraction.extracted_at,
        passage_count=len(extraction.passages),
        page_count=extraction.page_count,
        pages_needing_ocr=extraction.pages_needing_ocr,
        warnings=extraction.warnings,
        errors=[*extra_errors, *extraction.errors],
    )


def iter_source_files(root: str | Path) -> Iterator[tuple[Path | None, str]]:
    """Yield (path, relative_path) for candidate source files under root.

    Hidden entries and metadata sidecars are not sources. Symbolic links
    are yielded with path None so callers report them as skipped instead
    of following them outside the corpus directory.
    """
    root = Path(root)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            yield None, relative
            continue
        if not path.is_file() or path.name.endswith(SIDECAR_SUFFIX):
            continue
        yield path, relative


def find_duplicates(records: Iterable[SourceRecord]) -> list[DuplicateGroup]:
    by_hash: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_hash[record.content_sha256].append(record)
    return [
        DuplicateGroup(
            content_sha256=content_hash,
            relative_paths=[record.relative_path for record in group],
            source_ids=sorted({record.source_id for record in group}),
        )
        for content_hash, group in sorted(by_hash.items())
        if len(group) > 1
    ]


def find_source_id_conflicts(
    records: Iterable[SourceRecord],
) -> list[SourceIdConflict]:
    by_id: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_id[record.source_id].append(record)
    conflicts = []
    for source_id, group in sorted(by_id.items()):
        hashes = sorted({record.content_sha256 for record in group})
        if len(hashes) > 1:
            conflicts.append(
                SourceIdConflict(
                    source_id=source_id,
                    relative_paths=[record.relative_path for record in group],
                    content_sha256s=hashes,
                )
            )
    return conflicts


def assemble_manifest(
    records: list[SourceRecord],
    skipped_files: list[str] | None = None,
) -> SourceManifest:
    return SourceManifest(
        sources=records,
        duplicate_groups=find_duplicates(records),
        source_id_conflicts=find_source_id_conflicts(records),
        skipped_files=skipped_files or [],
    )


def write_manifest(manifest: SourceManifest, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def read_manifest(path: str | Path) -> SourceManifest:
    return SourceManifest.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )
