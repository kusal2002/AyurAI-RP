"""Data models for source documents, extraction results and manifests."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


SOURCE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class SourceFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    EPUB = "epub"
    TXT = "txt"
    MARKDOWN = "markdown"
    # XML documents: TEI P5 (e.g. SARIT editions of classical texts) and
    # JATS (open-access journal articles). Other XML is unsupported.
    XML = "xml"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    # Every page or block yielded usable text.
    EXTRACTED = "extracted"
    # No usable text layer; pages carry images, so OCR or manual review is
    # needed before the source can be used.
    NEEDS_OCR_OR_REVIEW = "needs_ocr_or_review"
    # Some text was extracted, but some pages need OCR, failed, or look
    # garbled.
    PARTIAL_EXTRACTION = "partial_extraction"
    # The file was read but contained no usable text and no images.
    EMPTY_OR_UNREADABLE = "empty_or_unreadable"
    UNSUPPORTED_FORMAT = "unsupported_format"
    FAILED = "failed"


class EvidenceCategory(str, Enum):
    """What kind of source a passage comes from, as declared by a curator.

    Never inferred from text. A traditional text is not clinical evidence,
    and a candidate extracted by software is not reviewed knowledge.
    """

    TRADITIONAL_TEXT = "traditional_text"
    MODERN_CLINICAL_RESEARCH = "modern_clinical_research"
    SYSTEMATIC_REVIEW = "systematic_review"
    PRACTITIONER_INTERPRETATION = "practitioner_interpretation"
    OTHER = "other"


class PassageKind(str, Enum):
    PAGE = "page"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE_ROW = "table_row"


class SourceLocation(BaseModel):
    """Where a passage came from. Only fields relevant to the format are set.

    Page numbers are 1-based physical page positions in the file, not the
    printed folio numbers of the book.
    """

    model_config = ConfigDict(extra="forbid")

    page: int | None = Field(default=None, ge=1)
    block_index: int | None = Field(
        default=None,
        ge=0,
        description="Position of the block in reading order (0-based).",
    )
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    table_index: int | None = Field(default=None, ge=0)
    row_index: int | None = Field(default=None, ge=0)
    item_id: str | None = Field(
        default=None, description="EPUB manifest item id."
    )
    item_href: str | None = None
    section_heading: str | None = Field(
        default=None,
        description="Nearest preceding heading, when the format exposes one.",
    )
    element_id: str | None = Field(
        default=None,
        description=(
            "Identifier printed or encoded in the source for this block, "
            "such as a TEI xml:id verse reference ('Ca.6.16.5'). Copied as "
            "found, never validated against a canonical numbering."
        ),
    )
    printed_page: str | None = Field(
        default=None,
        description=(
            "Printed page label of the edition the file was made from "
            "(TEI <pb n>), as found. Not a physical page of this file."
        ),
    )


class ExtractedPassage(BaseModel):
    """One passage of text exactly as the extractor produced it."""

    model_config = ConfigDict(extra="forbid")

    passage_index: int = Field(ge=0)
    kind: PassageKind
    text: str = Field(min_length=1)
    location: SourceLocation
    quality_flags: list[str] = Field(default_factory=list)


class PageIssue(BaseModel):
    page: int = Field(ge=1)
    issue: str


class ExtractionResult(BaseModel):
    """Outcome of extracting one source file.

    Paths are recorded as file names only so results can be shared without
    revealing local directory layouts.
    """

    model_config = ConfigDict(extra="forbid")

    file_name: str
    source_format: SourceFormat
    status: ExtractionStatus
    extractor: str
    extractor_version: str | None = None
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    passages: list[ExtractedPassage] = Field(default_factory=list)
    page_count: int | None = Field(default=None, ge=0)
    pages_needing_ocr: list[int] = Field(default_factory=list)
    blank_pages: list[int] = Field(default_factory=list)
    page_issues: list[PageIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    # Metadata stored inside the file itself (PDF info, DOCX core
    # properties, EPUB OPF). Reported as found, never completed or guessed.
    embedded_metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def text_char_count(self) -> int:
        return sum(len(passage.text) for passage in self.passages)


class PassageSpan(BaseModel):
    """Character range [start, end) of one extracted passage's text."""

    model_config = ConfigDict(extra="forbid")

    passage_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class TextChunk(BaseModel):
    """A retrieval-sized piece of a source, traceable to its passages.

    original_text is the exact source wording (spans joined by a blank
    line); text is its normalized form used for search. Language fields are
    declared by curated metadata, never inferred; scripts are detected from
    Unicode ranges only.
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    passage_spans: list[PassageSpan] = Field(min_length=1)
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    section_heading: str | None = None
    item_id: str | None = None
    verse_numbers: list[str] = Field(
        default_factory=list,
        description=(
            "Numbers found in danda verse markers (e.g. '॥ 12 ॥') inside "
            "the chunk, digits converted to ASCII. Not validated."
        ),
    )
    citation_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Element identifiers (e.g. TEI verse IDs) of the passages in "
            "the chunk, in order. Empty for formats without them."
        ),
    )
    printed_pages: list[str] = Field(
        default_factory=list,
        description="Printed page labels of the source edition, as found.",
    )
    primary_script: str
    scripts: list[str] = Field(default_factory=list)
    iast_present: bool = False
    declared_source_language: str | None = None
    declared_translation_language: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    chunker_version: str
    normalization_version: str


class SourceMetadata(BaseModel):
    """Bibliographic metadata supplied by the person curating the corpus.

    Every field is optional. Missing values stay null; nothing is filled in
    automatically. Set source_id explicitly to keep a stable identifier for
    a specific edition or translation across file corrections.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str | None = Field(default=None, pattern=SOURCE_ID_PATTERN)
    title: str | None = None
    author: str | None = None
    editor: str | None = None
    edition: str | None = None
    publication_year: int | None = Field(default=None, ge=0, le=9999)
    publisher: str | None = None
    source_language: str | None = None
    script: str | None = None
    translation_language: str | None = None
    translator: str | None = None
    usage_notes: str | None = Field(
        default=None,
        description="Copyright, licence or usage restrictions.",
    )
    evidence_category: EvidenceCategory | None = Field(
        default=None,
        description="Declared source category; null when not curated.",
    )


class SourceRecord(BaseModel):
    """Manifest entry describing one source file and its extraction."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    source_id_origin: str = Field(
        description="'metadata' when supplied, 'content_hash' when derived."
    )
    file_name: str
    relative_path: str
    source_format: SourceFormat
    file_size_bytes: int = Field(ge=0)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    extraction_status: ExtractionStatus
    extractor: str
    extractor_version: str | None = None
    extracted_at: datetime
    passage_count: int = Field(ge=0)
    page_count: int | None = None
    pages_needing_ocr: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DuplicateGroup(BaseModel):
    content_sha256: str
    relative_paths: list[str]
    source_ids: list[str]


class SourceIdConflict(BaseModel):
    """One source_id was given to files with different content."""

    source_id: str
    relative_paths: list[str]
    content_sha256s: list[str]


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int = 1
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sources: list[SourceRecord] = Field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    source_id_conflicts: list[SourceIdConflict] = Field(
        default_factory=list
    )
    skipped_files: list[str] = Field(default_factory=list)
