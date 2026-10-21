"""Source registry: which datasets may be acquired, from where, under what terms.

The registry (`corpus/source_registry.csv`) is curated by hand. It records
every existing corpus file and every candidate source with its licence,
permitted uses, checksum and an explicit inclusion decision. Nothing here
decides licences: values are copied from the source pages named in the
`licence_evidence` column.

Acquisition is reproducible and conservative:

- Only rows with decision `include` or `include_reference_only` and an
  https `download_url` are planned.
- The default is a dry run. `apply=True` is needed to touch the network.
- Downloads go to `<target>.part` and resume with an HTTP Range request.
  The file is moved into place only after its checksum matches the
  registry. A mismatch leaves the `.part` file for inspection.
- An existing file is never overwritten. A file that is present with a
  different checksum is reported as a conflict.
- A `.meta.json` sidecar is written from the registry only when none
  exists, so curated metadata is never replaced.
- Requests are sequential, identify the project in the User-Agent, and
  pause between files.
"""

import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

from pydantic import BaseModel, ConfigDict, field_validator

from app.knowledge_ingestion.manifest import SIDECAR_SUFFIX
from app.knowledge_ingestion.models import EvidenceCategory, SourceMetadata


REGISTRY_COLUMNS = (
    "registry_id", "status", "decision", "decision_reason",
    "source_id", "title", "author", "editor", "translator", "edition",
    "publication_year", "publisher_institution", "canonical_url",
    "download_url", "source_version", "access_date", "source_language",
    "translation_language", "scripts", "content_type", "subject_coverage",
    "evidence_category", "licence", "licence_url", "licence_evidence",
    "download_permitted", "processing_permitted", "modification_permitted",
    "redistribution_permitted", "file_format", "size_bytes",
    "checksum_type", "checksum", "local_relative_path", "corpus_source_id",
    "relevance", "quality_limitations", "ingestion_method",
)
DECISIONS = {
    "include", "include_reference_only", "defer", "exclude",
    "quarantine_recommended",
}
ACQUIRABLE = {"include", "include_reference_only"}
CHECKSUM_TYPES = {"sha256", "sha1", "md5", "git-blob-sha1"}
USER_AGENT = "AyurAI-research-corpus/1.0 (academic research; SLIIT J26-SE-320)"
_CHUNK = 1024 * 1024


class RegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_id: str
    status: str
    decision: str
    decision_reason: str = ""
    source_id: str = ""
    title: str = ""
    author: str = ""
    editor: str = ""
    translator: str = ""
    edition: str = ""
    publication_year: str = ""
    publisher_institution: str = ""
    canonical_url: str = ""
    download_url: str = ""
    source_version: str = ""
    access_date: str = ""
    source_language: str = ""
    translation_language: str = ""
    scripts: str = ""
    content_type: str = ""
    subject_coverage: str = ""
    evidence_category: str = ""
    licence: str = ""
    licence_url: str = ""
    licence_evidence: str = ""
    download_permitted: str = ""
    processing_permitted: str = ""
    modification_permitted: str = ""
    redistribution_permitted: str = ""
    file_format: str = ""
    size_bytes: str = ""
    checksum_type: str = ""
    checksum: str = ""
    local_relative_path: str = ""
    corpus_source_id: str = ""
    relevance: str = ""
    quality_limitations: str = ""
    ingestion_method: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @property
    def acquirable(self) -> bool:
        return self.decision in ACQUIRABLE and bool(self.download_url)


def load_registry(path: str | Path) -> list[RegistryEntry]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(REGISTRY_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "Registry is missing columns: " + ", ".join(sorted(missing))
            )
        return [RegistryEntry.model_validate(row) for row in reader]


def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and "\\" not in value
        and not path.is_absolute()
        and ".." not in path.parts
        and ":" not in value
    )


def validate_registry(entries: list[RegistryEntry]) -> list[str]:
    """Return problems that make a registry unsafe or ambiguous to use."""
    problems: list[str] = []
    seen_ids: set[str] = set()
    seen_sources: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for entry in entries:
        rid = entry.registry_id or "(blank id)"
        if entry.registry_id in seen_ids:
            problems.append(f"{rid}: duplicate registry_id")
        seen_ids.add(entry.registry_id)
        if entry.decision not in DECISIONS:
            problems.append(f"{rid}: unknown decision {entry.decision!r}")
        if not entry.decision_reason and entry.decision != "include":
            problems.append(f"{rid}: decision_reason is required")
        if entry.source_id:
            other = seen_sources.get(entry.source_id)
            if other:
                problems.append(f"{rid}: source_id also used by {other}")
            seen_sources[entry.source_id] = rid
            try:
                SourceMetadata(source_id=entry.source_id)
            except ValueError:
                problems.append(f"{rid}: source_id has invalid characters")
        if entry.evidence_category and entry.evidence_category not in {
            category.value for category in EvidenceCategory
        }:
            problems.append(f"{rid}: unknown evidence_category")
        if entry.local_relative_path:
            if not _safe_relative(entry.local_relative_path.rstrip("/")):
                problems.append(f"{rid}: local_relative_path must be relative and stay inside the corpus")
            other = seen_paths.get(entry.local_relative_path)
            if other:
                problems.append(f"{rid}: local_relative_path also used by {other}")
            seen_paths[entry.local_relative_path] = rid
        if entry.decision in ACQUIRABLE and entry.status == "candidate":
            if not entry.licence or entry.licence.lower().startswith("unknown"):
                problems.append(f"{rid}: included without a recorded licence")
            if not entry.licence_evidence:
                problems.append(f"{rid}: included without licence_evidence")
        if entry.download_url:
            if not entry.download_url.startswith("https://"):
                problems.append(f"{rid}: download_url must use https")
            if entry.decision in ACQUIRABLE:
                if not entry.local_relative_path:
                    problems.append(f"{rid}: download_url without local_relative_path")
                if entry.checksum_type and entry.checksum_type not in CHECKSUM_TYPES and entry.checksum:
                    problems.append(f"{rid}: unsupported checksum_type {entry.checksum_type!r}")
    return problems


# --- checksums ---------------------------------------------------------------

def file_checksum(path: Path, checksum_type: str) -> str:
    if checksum_type == "git-blob-sha1":
        digest = hashlib.sha1()
        digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
    else:
        digest = hashlib.new(checksum_type)
    with path.open("rb") as handle:
        while block := handle.read(_CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _verifiable(entry: RegistryEntry) -> bool:
    return entry.checksum_type in CHECKSUM_TYPES and bool(entry.checksum)


# --- planning ----------------------------------------------------------------

@dataclass
class AcquisitionItem:
    registry_id: str
    target: str
    url: str
    state: str          # missing | partial | present_verified | present_unverified | conflict
    detail: str = ""
    size_bytes: str = ""


def plan_acquisition(entries: list[RegistryEntry], raw_root: str | Path,
                     only: set[str] | None = None) -> list[AcquisitionItem]:
    """Describe what acquisition would do. Reads local files only."""
    raw_root = Path(raw_root)
    items = []
    for entry in entries:
        if not entry.acquirable or (only and entry.registry_id not in only):
            continue
        target = raw_root / entry.local_relative_path
        item = AcquisitionItem(entry.registry_id, entry.local_relative_path,
                               entry.download_url, "missing", size_bytes=entry.size_bytes)
        if target.is_file():
            if not _verifiable(entry):
                item.state, item.detail = "present_unverified", "no checksum in registry"
            elif file_checksum(target, entry.checksum_type) == entry.checksum:
                item.state = "present_verified"
            else:
                item.state, item.detail = "conflict", "existing file checksum differs; not overwritten"
        elif target.with_name(target.name + ".part").is_file():
            item.state = "partial"
        if not _verifiable(entry) and item.state in {"missing", "partial"}:
            item.detail = "no checksum in registry: sha256 will be reported for recording"
        items.append(item)
    return items


# --- download ----------------------------------------------------------------

Opener = Callable[[urllib.request.Request, float], object]


def _default_opener(request, timeout):
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 (https enforced)


def _download(url: str, part: Path, opener: Opener, timeout: float) -> None:
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with opener(request, timeout) as response:
        status = getattr(response, "status", 200)
        if offset and status != 206:
            # Server ignored the range: start again rather than append.
            offset = 0
        with part.open("ab" if offset else "wb") as handle:
            while block := response.read(_CHUNK):
                handle.write(block)


def _sidecar(entry: RegistryEntry) -> dict:
    usage = "; ".join(
        value for value in (
            f"Licence: {entry.licence}" if entry.licence else "",
            f"Redistribution: {entry.redistribution_permitted}" if entry.redistribution_permitted else "",
            f"Registry: {entry.registry_id}; source page {entry.canonical_url}" if entry.canonical_url else "",
            f"Version: {entry.source_version}" if entry.source_version else "",
        ) if value
    )
    year = entry.publication_year
    metadata = SourceMetadata(
        source_id=entry.source_id or None,
        title=entry.title or None,
        author=entry.author or None,
        editor=entry.editor or None,
        edition=entry.edition or None,
        publication_year=int(year) if year.isdigit() else None,
        publisher=entry.publisher_institution or None,
        source_language=entry.source_language or None,
        script=entry.scripts or None,
        translation_language=entry.translation_language or None,
        translator=entry.translator or None,
        usage_notes=usage or None,
        evidence_category=entry.evidence_category or None,
    )
    return metadata.model_dump(mode="json")


@dataclass
class AcquisitionReport:
    items: list[AcquisitionItem] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    recorded_checksums: dict[str, str] = field(default_factory=dict)
    sidecars_written: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def acquire(entries: list[RegistryEntry], raw_root: str | Path, *,
            apply: bool = False, only: set[str] | None = None,
            opener: Opener | None = None, timeout: float = 60.0,
            pause_seconds: float = 2.0) -> AcquisitionReport:
    """Plan, and with apply=True perform, registry downloads."""
    raw_root = Path(raw_root)
    opener = opener or _default_opener
    by_id = {entry.registry_id: entry for entry in entries}
    report = AcquisitionReport(items=plan_acquisition(entries, raw_root, only))
    if not apply:
        return report

    first = True
    for item in report.items:
        entry = by_id[item.registry_id]
        target = raw_root / entry.local_relative_path
        if item.state in {"missing", "partial"}:
            if not first:
                time.sleep(pause_seconds)
            first = False
            part = target.with_name(target.name + ".part")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                _download(entry.download_url, part, opener, timeout)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                report.errors[entry.registry_id] = f"download failed ({type(exc).__name__}); partial file kept for resume"
                continue
            if _verifiable(entry):
                actual = file_checksum(part, entry.checksum_type)
                if actual != entry.checksum:
                    report.errors[entry.registry_id] = (
                        f"{entry.checksum_type} mismatch (got {actual}); "
                        f"kept as {part.name} and not used"
                    )
                    continue
            else:
                report.recorded_checksums[entry.registry_id] = file_checksum(part, "sha256")
            part.replace(target)
            item.state = "present_verified" if _verifiable(entry) else "present_unverified"
            report.downloaded.append(entry.registry_id)
        if item.state in {"present_verified", "present_unverified"}:
            sidecar = target.with_name(target.name + SIDECAR_SUFFIX)
            if not sidecar.exists():
                sidecar.write_text(
                    json.dumps(_sidecar(entry), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                report.sidecars_written.append(entry.registry_id)
    return report
