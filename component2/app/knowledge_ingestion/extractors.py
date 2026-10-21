"""Format-specific text extraction that keeps source locations.

Extractors never raise for a bad input file: every outcome is returned as
an ExtractionResult with an explicit status, so a damaged or scanned book
is reported rather than silently skipped. Passage text is kept as decoded
from the file. Unicode normalization belongs to a later, separate stage.

DOCX, EPUB and TEI XML are read with the standard library (zipfile,
ElementTree, html.parser). PDF text extraction uses the pypdf package; OCR is not
performed here. Pages without a text layer are reported for OCR instead.
"""

import codecs
import logging
import posixpath
import re
import unicodedata
import zipfile
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from app.config import IngestionSettings, load_ingestion_settings
from app.knowledge_ingestion.models import (
    ExtractedPassage,
    ExtractionResult,
    ExtractionStatus,
    PageIssue,
    PassageKind,
    SourceFormat,
    SourceLocation,
)


logger = logging.getLogger(__name__)

# Revision of the in-house DOCX, EPUB and plain-text extractors. Increase
# it when their output changes so stored results can be told apart.
EXTRACTOR_REVISION = "1"

EXTENSION_FORMATS = {
    ".pdf": SourceFormat.PDF,
    ".docx": SourceFormat.DOCX,
    ".epub": SourceFormat.EPUB,
    ".txt": SourceFormat.TXT,
    ".md": SourceFormat.MARKDOWN,
    ".markdown": SourceFormat.MARKDOWN,
    # TEI P5 and JATS documents are accepted; other XML is reported as
    # unsupported by extract_xml.
    ".xml": SourceFormat.XML,
}

SUSPECT_CHARACTERS_FLAG = "suspect_characters"
SHORT_PAGE_TEXT_FLAG = "short_page_text"


class _ArchiveError(Exception):
    """Raised for unusable DOCX/EPUB archive content (message is safe)."""


def detect_format(path: str | Path) -> SourceFormat:
    return EXTENSION_FORMATS.get(Path(path).suffix.lower(), SourceFormat.UNKNOWN)


def _visible_length(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def text_quality_flags(text: str, settings: IngestionSettings) -> list[str]:
    """Flag text that is probably garbled rather than real content.

    Counts U+FFFD replacement characters, private-use code points (common
    when a PDF font has no Unicode mapping) and stray control characters.
    Legacy non-Unicode Sinhala fonts produce plausible-looking Latin text
    and are NOT detected by this check.
    """
    visible = _visible_length(text)
    if visible == 0:
        return []
    suspect = 0
    for char in text:
        if char == "\ufffd":
            suspect += 1
            continue
        category = unicodedata.category(char)
        if category == "Co" or (category == "Cc" and char not in "\t\n\r"):
            suspect += 1
    if suspect / visible > settings.max_suspect_char_ratio:
        return [SUSPECT_CHARACTERS_FLAG]
    return []


def _base_result(
    path: Path,
    source_format: SourceFormat,
    extractor: str,
    extractor_version: str | None,
    **fields,
) -> ExtractionResult:
    return ExtractionResult(
        file_name=path.name,
        source_format=source_format,
        extractor=extractor,
        extractor_version=extractor_version,
        **fields,
    )


def _failed(
    path: Path,
    source_format: SourceFormat,
    extractor: str,
    message: str,
    status: ExtractionStatus = ExtractionStatus.FAILED,
    extractor_version: str | None = EXTRACTOR_REVISION,
) -> ExtractionResult:
    return _base_result(
        path,
        source_format,
        extractor,
        extractor_version,
        status=status,
        errors=[message],
    )


def _classify(
    passages: list[ExtractedPassage],
    has_issues: bool,
) -> ExtractionStatus:
    if not passages:
        return ExtractionStatus.EMPTY_OR_UNREADABLE
    flagged = sum(
        1 for passage in passages
        if SUSPECT_CHARACTERS_FLAG in passage.quality_flags
    )
    if flagged == len(passages):
        return ExtractionStatus.NEEDS_OCR_OR_REVIEW
    if flagged or has_issues:
        return ExtractionStatus.PARTIAL_EXTRACTION
    return ExtractionStatus.EXTRACTED


def _flag_warning(passages: list[ExtractedPassage]) -> list[str]:
    flagged = sum(
        1 for passage in passages
        if SUSPECT_CHARACTERS_FLAG in passage.quality_flags
    )
    if not flagged:
        return []
    return [
        f"{flagged} passage(s) contain many replacement, private-use or "
        "control characters; the text is probably garbled."
    ]


# --- Plain text and Markdown -------------------------------------------------

_MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$")


def _decode_text_bytes(data: bytes) -> tuple[str, str]:
    """Decode UTF-8 (with or without BOM) or BOM-marked UTF-16/UTF-32.

    Other encodings are not guessed: guessing can silently turn Sinhala
    or Devanagari into wrong characters.
    """
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8-sig"
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return data.decode("utf-32"), "utf-32"
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16"), "utf-16"
    return data.decode("utf-8"), "utf-8"


def extract_plain_text(
    path: Path,
    settings: IngestionSettings,
    source_format: SourceFormat = SourceFormat.TXT,
) -> ExtractionResult:
    """Split a text file into blank-line separated paragraphs.

    Line terminators are normalized to "\\n"; line content is unchanged.
    For Markdown, ATX headings ("# Title") become separate heading passages
    and set section_heading for the following passages.
    """
    extractor = "plain_text"
    data = path.read_bytes()
    try:
        text, encoding = _decode_text_bytes(data)
    except UnicodeDecodeError as exc:
        return _failed(
            path,
            source_format,
            extractor,
            "Text is not valid UTF-8 or BOM-marked UTF-16/UTF-32 "
            f"(first invalid byte at offset {exc.start}). Convert the file "
            "to UTF-8; legacy encodings are not guessed.",
        )
    if "\x00" in text:
        return _failed(
            path,
            source_format,
            extractor,
            "File contains NUL characters and does not look like text.",
        )

    is_markdown = source_format == SourceFormat.MARKDOWN
    passages: list[ExtractedPassage] = []
    block_index = 0
    section: str | None = None
    buffer: list[str] = []
    buffer_start = 0

    def emit(kind: PassageKind, lines: list[str], first: int, last: int):
        nonlocal block_index
        body = "\n".join(lines)
        if body.strip():
            passages.append(
                ExtractedPassage(
                    passage_index=len(passages),
                    kind=kind,
                    text=body,
                    location=SourceLocation(
                        block_index=block_index,
                        line_start=first,
                        line_end=last,
                        section_heading=section,
                    ),
                    quality_flags=text_quality_flags(body, settings),
                )
            )
            block_index += 1

    def flush():
        nonlocal buffer
        if buffer:
            emit(
                PassageKind.PARAGRAPH,
                buffer,
                buffer_start,
                buffer_start + len(buffer) - 1,
            )
        buffer = []

    for number, line in enumerate(text.splitlines(), start=1):
        heading = _MARKDOWN_HEADING.match(line) if is_markdown else None
        if heading:
            flush()
            heading_text = heading.group(2).strip()
            if heading_text:
                section = heading_text
                emit(PassageKind.HEADING, [line], number, number)
            continue
        if not line.strip():
            flush()
            continue
        if not buffer:
            buffer_start = number
        buffer.append(line)
    flush()

    warnings = _flag_warning(passages)
    if encoding != "utf-8":
        warnings.append(f"Decoded as {encoding}.")
    return _base_result(
        path,
        source_format,
        extractor,
        EXTRACTOR_REVISION,
        status=_classify(passages, has_issues=False),
        passages=passages,
        warnings=warnings,
    )


def extract_markdown(path: Path, settings: IngestionSettings) -> ExtractionResult:
    return extract_plain_text(path, settings, SourceFormat.MARKDOWN)


# --- PDF ---------------------------------------------------------------------

def _resources_have_images(resources, depth: int = 0) -> bool:
    if resources is None or depth > 3:
        return False
    resources = resources.get_object()
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return False
    xobjects = xobjects.get_object()
    for name in xobjects:
        xobject = xobjects[name].get_object()
        subtype = xobject.get("/Subtype")
        if subtype == "/Image":
            return True
        if subtype == "/Form" and _resources_have_images(
            xobject.get("/Resources"), depth + 1
        ):
            return True
    return False


def _page_has_images(page) -> bool:
    try:
        return _resources_have_images(page.get("/Resources"))
    except Exception:
        return False


def _pdf_metadata(reader) -> dict[str, str]:
    try:
        info = reader.metadata
    except Exception:
        return {}
    if not info:
        return {}
    found = {}
    for key, name in (
        ("/Title", "title"),
        ("/Author", "author"),
        ("/Subject", "subject"),
        ("/Creator", "creator"),
        ("/Producer", "producer"),
    ):
        try:
            value = info.get(key)
        except Exception:
            continue
        if value is not None and str(value).strip():
            found[name] = str(value).strip()
    return found


class _WarningCollector(logging.Handler):
    """Collect a library's warning messages instead of printing them."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.counts: dict[str, int] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        # Keep only the leading sentence; pypdf appends whole font
        # dictionaries to some messages.
        message = message.split(" in font dictionary", 1)[0]
        message = " ".join(message.split())[:160]
        self.counts[message] = self.counts.get(message, 0) + 1

    def summary(self, prefix: str, limit: int = 5) -> list[str]:
        ordered = sorted(self.counts.items(), key=lambda item: -item[1])
        lines = [
            f"{prefix}: {message} (x{count})" for message, count in ordered
        ][:limit]
        if len(ordered) > limit:
            lines.append(
                f"{prefix}: {len(ordered) - limit} further warning type(s)."
            )
        return lines


@contextmanager
def _collect_warnings(logger_name: str) -> Iterator[_WarningCollector]:
    """Route a library logger into a collector for the duration of a call.

    Not safe for concurrent extractions in one process; the CLI and
    service run one file at a time.
    """
    library_logger = logging.getLogger(logger_name)
    collector = _WarningCollector()
    previous = library_logger.propagate
    library_logger.addHandler(collector)
    library_logger.propagate = False
    try:
        yield collector
    finally:
        library_logger.removeHandler(collector)
        library_logger.propagate = previous


def extract_pdf(path: Path, settings: IngestionSettings) -> ExtractionResult:
    """Extract a PDF, reporting pypdf parser warnings in the result.

    Font-encoding warnings matter: they can mean some characters were
    mapped incorrectly, so they are kept as extraction warnings.
    """
    with _collect_warnings("pypdf") as collector:
        result = _extract_pdf(path, settings)
    result.warnings.extend(collector.summary("pypdf"))
    return result


def _extract_pdf(path: Path, settings: IngestionSettings) -> ExtractionResult:
    """Extract the text layer page by page; flag image-only pages for OCR.

    A page with fewer than settings.min_page_text_chars visible characters
    is listed in pages_needing_ocr when it carries images, or in
    blank_pages when it carries none. No page is dropped silently.
    """
    extractor = "pypdf"
    try:
        import pypdf
    except ImportError:
        return _failed(
            path,
            SourceFormat.PDF,
            extractor,
            "PDF extraction requires the 'pypdf' package "
            "(listed in requirements.txt).",
            extractor_version=None,
        )
    version = getattr(pypdf, "__version__", None)

    try:
        reader = pypdf.PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            try:
                opened = reader.decrypt("")
            except Exception:
                opened = 0
            if not opened:
                return _failed(
                    path,
                    SourceFormat.PDF,
                    extractor,
                    "PDF is encrypted and cannot be opened without a "
                    "password.",
                    extractor_version=version,
                )
        page_count = len(reader.pages)
    except Exception as exc:
        return _failed(
            path,
            SourceFormat.PDF,
            extractor,
            f"PDF could not be parsed ({type(exc).__name__}).",
            extractor_version=version,
        )

    if page_count == 0:
        return _failed(
            path,
            SourceFormat.PDF,
            extractor,
            "PDF has no pages.",
            status=ExtractionStatus.EMPTY_OR_UNREADABLE,
            extractor_version=version,
        )

    passages: list[ExtractedPassage] = []
    pages_needing_ocr: list[int] = []
    blank_pages: list[int] = []
    page_issues: list[PageIssue] = []

    for number in range(1, page_count + 1):
        try:
            page = reader.pages[number - 1]
            text = page.extract_text() or ""
        except Exception as exc:
            page_issues.append(
                PageIssue(
                    page=number,
                    issue=f"text extraction failed ({type(exc).__name__})",
                )
            )
            continue

        visible = _visible_length(text)
        flags = text_quality_flags(text, settings)
        too_short = visible < settings.min_page_text_chars
        if visible and too_short:
            flags.append(SHORT_PAGE_TEXT_FLAG)
        if visible:
            passages.append(
                ExtractedPassage(
                    passage_index=len(passages),
                    kind=PassageKind.PAGE,
                    text=text,
                    location=SourceLocation(page=number),
                    quality_flags=flags,
                )
            )
        if too_short:
            if _page_has_images(page):
                pages_needing_ocr.append(number)
            elif not visible:
                blank_pages.append(number)

    garbled_pages = [
        passage.location.page
        for passage in passages
        if SUSPECT_CHARACTERS_FLAG in passage.quality_flags
    ]
    usable = [
        passage for passage in passages
        if SUSPECT_CHARACTERS_FLAG not in passage.quality_flags
        and SHORT_PAGE_TEXT_FLAG not in passage.quality_flags
    ]

    if not usable:
        if pages_needing_ocr or garbled_pages:
            status = ExtractionStatus.NEEDS_OCR_OR_REVIEW
        elif len(page_issues) == page_count:
            status = ExtractionStatus.FAILED
        else:
            status = ExtractionStatus.EMPTY_OR_UNREADABLE
    elif pages_needing_ocr or garbled_pages or page_issues:
        status = ExtractionStatus.PARTIAL_EXTRACTION
    else:
        status = ExtractionStatus.EXTRACTED

    warnings = _flag_warning(passages)
    if pages_needing_ocr:
        warnings.append(
            f"{len(pages_needing_ocr)} page(s) have images but no usable "
            "text layer and need OCR."
        )
    if blank_pages:
        warnings.append(
            f"{len(blank_pages)} page(s) have no text and no images "
            "(possibly blank); review if unexpected."
        )
    errors = []
    if page_issues:
        errors.append(f"Text extraction failed on {len(page_issues)} page(s).")

    return _base_result(
        path,
        SourceFormat.PDF,
        extractor,
        version,
        status=status,
        passages=passages,
        page_count=page_count,
        pages_needing_ocr=pages_needing_ocr,
        blank_pages=blank_pages,
        page_issues=page_issues,
        warnings=warnings,
        errors=errors,
        embedded_metadata=_pdf_metadata(reader),
    )


# --- ZIP-based formats -------------------------------------------------------

def _read_member(
    archive: zipfile.ZipFile,
    name: str,
    settings: IngestionSettings,
) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise _ArchiveError(f"Archive member {name!r} is missing.") from None
    limit = settings.max_archive_member_bytes
    if info.file_size > limit:
        raise _ArchiveError(
            f"Archive member {name!r} exceeds the configured size limit."
        )
    with archive.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise _ArchiveError(
            f"Archive member {name!r} exceeds the configured size limit."
        )
    return data


def _parse_xml(data: bytes, name: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise _ArchiveError(f"{name!r} is not well-formed XML.") from None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _dublin_core(root: ET.Element, wanted: tuple[str, ...]) -> dict[str, str]:
    found: dict[str, str] = {}
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        if not element.tag.startswith("{http://purl.org/dc/elements/1.1/}"):
            continue
        name = _local_name(element.tag)
        value = "".join(element.itertext()).strip()
        if name in wanted and value and name not in found:
            found[name] = value
    return found


# --- DOCX --------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_STYLE_NAME = re.compile(r"^(heading\s*\d+|title)$", re.IGNORECASE)


def _docx_heading_styles(archive, settings) -> set[str]:
    """Style IDs that represent headings, from word/styles.xml if present.

    Style IDs are localized in some Word installations, so the style name
    and outline level are checked as well as the ID.
    """
    styles = {"Title"} | {f"Heading{level}" for level in range(1, 10)}
    try:
        root = _parse_xml(
            _read_member(archive, "word/styles.xml", settings),
            "word/styles.xml",
        )
    except _ArchiveError:
        return styles
    for style in root.iter(f"{_W}style"):
        style_id = style.get(f"{_W}styleId")
        if not style_id:
            continue
        name = style.find(f"{_W}name")
        name_value = name.get(f"{_W}val", "") if name is not None else ""
        outline = style.find(f"{_W}pPr/{_W}outlineLvl")
        if _HEADING_STYLE_NAME.match(name_value) or outline is not None:
            styles.add(style_id)
    return styles


def _docx_paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for element in paragraph.iter():
        tag = element.tag
        if tag == f"{_W}t":
            parts.append(element.text or "")
        elif tag == f"{_W}tab":
            parts.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
        elif tag == f"{_W}noBreakHyphen":
            parts.append("\u2011")
    # Deleted tracked-change text is stored in w:delText and is skipped.
    return "".join(parts)


def _docx_is_heading(paragraph: ET.Element, heading_styles: set[str]) -> bool:
    properties = paragraph.find(f"{_W}pPr")
    if properties is None:
        return False
    if properties.find(f"{_W}outlineLvl") is not None:
        return True
    style = properties.find(f"{_W}pStyle")
    return style is not None and style.get(f"{_W}val") in heading_styles


def _docx_blocks(container: ET.Element) -> Iterator[ET.Element]:
    """Yield body-level paragraphs and tables in reading order.

    Only direct children are visited (plus content controls), so table
    cell paragraphs are never also reported as body paragraphs.
    """
    for child in container:
        if child.tag in (f"{_W}p", f"{_W}tbl"):
            yield child
        elif child.tag == f"{_W}sdt":
            content = child.find(f"{_W}sdtContent")
            if content is not None:
                yield from _docx_blocks(content)
        elif child.tag == f"{_W}customXml":
            yield from _docx_blocks(child)


def _docx_cell_text(cell: ET.Element) -> str:
    parts: list[str] = []
    for block in _docx_blocks(cell):
        if block.tag == f"{_W}p":
            parts.append(_docx_paragraph_text(block))
        else:
            for row in block.iter(f"{_W}tr"):
                parts.append(
                    " | ".join(
                        _docx_cell_text(nested).strip()
                        for nested in row.findall(f"{_W}tc")
                    )
                )
    return "\n".join(part for part in parts if part.strip())


def extract_docx(path: Path, settings: IngestionSettings) -> ExtractionResult:
    """Extract body paragraphs and table rows in reading order.

    Each table row becomes one passage with its cells joined by " | ".
    Headers, footers, footnotes and comments are not extracted.
    """
    extractor = "docx_ooxml"
    try:
        with zipfile.ZipFile(path) as archive:
            root = _parse_xml(
                _read_member(archive, "word/document.xml", settings),
                "word/document.xml",
            )
            heading_styles = _docx_heading_styles(archive, settings)
            metadata: dict[str, str] = {}
            if "docProps/core.xml" in archive.namelist():
                try:
                    metadata = _dublin_core(
                        _parse_xml(
                            _read_member(
                                archive, "docProps/core.xml", settings
                            ),
                            "docProps/core.xml",
                        ),
                        ("title", "creator", "language", "subject"),
                    )
                except _ArchiveError:
                    metadata = {}
    except zipfile.BadZipFile:
        return _failed(
            path, SourceFormat.DOCX, extractor,
            "File is not a valid DOCX (ZIP) archive.",
        )
    except _ArchiveError as exc:
        return _failed(path, SourceFormat.DOCX, extractor, str(exc))

    body = root.find(f"{_W}body")
    if body is None:
        return _failed(
            path, SourceFormat.DOCX, extractor,
            "word/document.xml has no document body.",
        )

    passages: list[ExtractedPassage] = []
    section: str | None = None
    table_index = 0

    def add(kind, text, location):
        passages.append(
            ExtractedPassage(
                passage_index=len(passages),
                kind=kind,
                text=text,
                location=location,
                quality_flags=text_quality_flags(text, settings),
            )
        )

    for block_index, block in enumerate(_docx_blocks(body)):
        if block.tag == f"{_W}p":
            text = _docx_paragraph_text(block)
            if not text.strip():
                continue
            if _docx_is_heading(block, heading_styles):
                section = text.strip()
                kind = PassageKind.HEADING
            else:
                kind = PassageKind.PARAGRAPH
            add(
                kind,
                text,
                SourceLocation(
                    block_index=block_index, section_heading=section
                ),
            )
            continue

        for row_index, row in enumerate(block.findall(f"{_W}tr")):
            cells = [
                _docx_cell_text(cell).strip()
                for cell in row.findall(f"{_W}tc")
            ]
            if not any(cells):
                continue
            add(
                PassageKind.TABLE_ROW,
                " | ".join(cells),
                SourceLocation(
                    block_index=block_index,
                    table_index=table_index,
                    row_index=row_index,
                    section_heading=section,
                ),
            )
        table_index += 1

    return _base_result(
        path,
        SourceFormat.DOCX,
        extractor,
        EXTRACTOR_REVISION,
        status=_classify(passages, has_issues=False),
        passages=passages,
        warnings=_flag_warning(passages),
        embedded_metadata=metadata,
    )


# --- EPUB --------------------------------------------------------------------

_CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"
_OPF_NS = "{http://www.idpf.org/2007/opf}"
_XHTML_TYPES = {"application/xhtml+xml", "text/html"}
_XML_ENCODING = re.compile(rb"""^<\?xml[^>]*encoding=["']([A-Za-z0-9._-]+)["']""")
_ASCII_WHITESPACE = re.compile(r"[ \t\n\r\f]+")


class _XhtmlBlockParser(HTMLParser):
    """Collect block-level text from XHTML, skipping scripts and styles.

    Only ASCII whitespace is collapsed (as browsers do), so no-break
    spaces, ZWJ and ZWNJ used in Sinhala and Devanagari are kept.
    """

    SKIP = {"head", "script", "style", "template", "svg", "math"}
    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    BLOCKS = HEADINGS | {
        "p", "div", "section", "article", "aside", "header", "footer",
        "nav", "blockquote", "li", "dd", "dt", "pre", "tr", "table",
        "caption", "figcaption", "ul", "ol", "dl", "body", "hr",
        "address", "figure",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[bool, str]] = []
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._heading_depth = 0
        self._pre_depth = 0

    def _flush(self) -> None:
        raw = "".join(self._buffer)
        self._buffer = []
        lines = [line.strip(" \t\r\f") for line in raw.split("\n")]
        text = "\n".join(line for line in lines if line)
        if text:
            self.blocks.append((self._heading_depth > 0, text))

    def handle_starttag(self, tag, attrs):
        if self._skip_depth or tag in self.SKIP:
            if tag in self.SKIP:
                self._skip_depth += 1
            return
        if tag in self.BLOCKS:
            self._flush()
            if tag in self.HEADINGS:
                self._heading_depth += 1
            if tag == "pre":
                self._pre_depth += 1
        elif tag == "br":
            self._buffer.append("\n")
        elif tag in ("td", "th"):
            if "".join(self._buffer).strip():
                self._buffer.append(" | ")

    def handle_startendtag(self, tag, attrs):
        if tag in self.SKIP:
            return
        self.handle_starttag(tag, attrs)
        if tag in self.BLOCKS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCKS:
            self._flush()
            if tag in self.HEADINGS and self._heading_depth:
                self._heading_depth -= 1
            if tag == "pre" and self._pre_depth:
                self._pre_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        if not self._pre_depth:
            data = _ASCII_WHITESPACE.sub(" ", data)
        self._buffer.append(data)

    def close(self):
        super().close()
        self._flush()


def _decode_xhtml(data: bytes) -> str:
    declared = _XML_ENCODING.match(data.lstrip(codecs.BOM_UTF8))
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    encoding = declared.group(1).decode("ascii") if declared else "utf-8"
    return data.decode(encoding)


def _epub_spine(archive, settings) -> tuple[str, list[tuple[str, str]], dict]:
    container = _parse_xml(
        _read_member(archive, "META-INF/container.xml", settings),
        "META-INF/container.xml",
    )
    rootfile = container.find(f".//{_CONTAINER_NS}rootfile")
    opf_path = rootfile.get("full-path") if rootfile is not None else None
    if not opf_path:
        raise _ArchiveError("EPUB container does not name a package file.")

    package = _parse_xml(_read_member(archive, opf_path, settings), opf_path)
    opf_dir = posixpath.dirname(opf_path)
    manifest = {}
    for item in package.iter(f"{_OPF_NS}item"):
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            manifest[item_id] = (href, item.get("media-type", ""))

    spine: list[tuple[str, str]] = []
    for itemref in package.iter(f"{_OPF_NS}itemref"):
        item_id = itemref.get("idref")
        if item_id not in manifest:
            continue
        href, media_type = manifest[item_id]
        if media_type not in _XHTML_TYPES:
            continue
        member = posixpath.normpath(posixpath.join(opf_dir, unquote(href)))
        spine.append((item_id, member))

    metadata = _dublin_core(
        package, ("title", "creator", "language", "publisher", "date")
    )
    return opf_path, spine, metadata


def extract_epub(path: Path, settings: IngestionSettings) -> ExtractionResult:
    """Extract spine documents in reading order, one passage per block."""
    extractor = "epub_xhtml"
    passages: list[ExtractedPassage] = []
    item_issues: list[str] = []
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(path) as archive:
            _, spine, metadata = _epub_spine(archive, settings)
            if not spine:
                return _failed(
                    path, SourceFormat.EPUB, extractor,
                    "EPUB spine lists no XHTML documents.",
                    status=ExtractionStatus.EMPTY_OR_UNREADABLE,
                )
            has_encryption = (
                "META-INF/encryption.xml" in archive.namelist()
            )
            section: str | None = None
            for item_id, member in spine:
                try:
                    markup = _decode_xhtml(
                        _read_member(archive, member, settings)
                    )
                except (_ArchiveError, UnicodeDecodeError, LookupError):
                    item_issues.append(item_id)
                    continue
                parser = _XhtmlBlockParser()
                parser.feed(markup)
                parser.close()
                for block_index, (is_heading, text) in enumerate(
                    parser.blocks
                ):
                    if is_heading:
                        section = text
                    passages.append(
                        ExtractedPassage(
                            passage_index=len(passages),
                            kind=(
                                PassageKind.HEADING
                                if is_heading
                                else PassageKind.PARAGRAPH
                            ),
                            text=text,
                            location=SourceLocation(
                                block_index=block_index,
                                item_id=item_id,
                                item_href=member,
                                section_heading=section,
                            ),
                            quality_flags=text_quality_flags(text, settings),
                        )
                    )
    except zipfile.BadZipFile:
        return _failed(
            path, SourceFormat.EPUB, extractor,
            "File is not a valid EPUB (ZIP) archive.",
        )
    except _ArchiveError as exc:
        return _failed(path, SourceFormat.EPUB, extractor, str(exc))

    errors = []
    if item_issues:
        errors.append(
            f"{len(item_issues)} spine document(s) could not be read: "
            + ", ".join(item_issues[:10])
        )
        if has_encryption:
            warnings.append(
                "EPUB declares encrypted resources (DRM or font "
                "obfuscation); encrypted documents cannot be extracted."
            )
    warnings.extend(_flag_warning(passages))

    return _base_result(
        path,
        SourceFormat.EPUB,
        extractor,
        EXTRACTOR_REVISION,
        status=_classify(passages, has_issues=bool(item_issues)),
        passages=passages,
        warnings=warnings,
        errors=errors,
        embedded_metadata=metadata,
    )


# --- TEI P5 XML --------------------------------------------------------------

_TEI_NS = "{http://www.tei-c.org/ns/1.0}"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
# Elements that form one passage each. A <head> is a heading; the others
# are body text. <l> outside an <lg> is its own passage.
_TEI_BLOCKS = {"head", "lg", "p", "ab", "l", "item"}
# Elements whose content is not part of the passage text: editorial notes
# (variant readings, commentary references), printed reference labels
# (kept in element_id instead) and footnote markers.
_TEI_SKIP_CONTENT = {"note", "label", "fw", "figDesc"}
_ASCII_SPACE = re.compile(r"[ \t\r\n]+")
EDITORIAL_NOTES_FLAG = "editorial_notes_omitted"


def _tei_attr_id(element: ET.Element) -> str | None:
    return element.get(_XML_ID) or element.get("n")


def _tei_is_footnote_marker(element: ET.Element) -> bool:
    return _local_name(element.tag) == "ref" and "footnote" in (
        element.get("rend") or ""
    )


class _TeiBlock:
    """Collects the text of one block element in document order."""

    def __init__(self) -> None:
        self.lines: list[list[str]] = [[]]
        self.element_ids: list[str] = []
        self.notes = 0
        self.page_breaks: list[str] = []

    def newline(self) -> None:
        if self.lines[-1]:
            self.lines.append([])

    def text(self) -> str:
        lines = [
            _ASCII_SPACE.sub(" ", "".join(parts)).strip()
            for parts in self.lines
        ]
        return "\n".join(line for line in lines if line)


def _tei_collect(element: ET.Element, block: _TeiBlock, root: bool) -> None:
    name = _local_name(element.tag) if isinstance(element.tag, str) else ""
    if not root:
        if name == "note":
            block.notes += 1
        if name == "pb" and element.get("n"):
            block.page_breaks.append(element.get("n"))
        if name in _TEI_SKIP_CONTENT or _tei_is_footnote_marker(element):
            # The tail belongs to the parent and is still text.
            if element.tail:
                block.lines[-1].append(element.tail)
            return
        if name == "l":
            block.newline()
        if name == "lb":
            block.newline()
    identifier = element.get(_XML_ID)
    if identifier:
        block.element_ids.append(identifier)
    if element.text:
        block.lines[-1].append(element.text)
    for child in element:
        _tei_collect(child, block, root=False)
    if not root:
        if name == "l":
            block.newline()
        if element.tail:
            block.lines[-1].append(element.tail)


def _tei_header_metadata(root: ET.Element) -> dict[str, str]:
    found: dict[str, str] = {}
    header = root.find(f"{_TEI_NS}teiHeader")
    if header is None:
        return found
    paths = {
        "title": f"{_TEI_NS}fileDesc/{_TEI_NS}titleStmt/{_TEI_NS}title",
        "publisher": f"{_TEI_NS}fileDesc/{_TEI_NS}publicationStmt/{_TEI_NS}publisher",
        "availability": f"{_TEI_NS}fileDesc/{_TEI_NS}publicationStmt/{_TEI_NS}availability",
        "source_description": f"{_TEI_NS}fileDesc/{_TEI_NS}sourceDesc",
    }
    for key, path in paths.items():
        element = header.find(path)
        if element is None:
            continue
        value = _ASCII_SPACE.sub(" ", "".join(element.itertext())).strip()
        if value:
            # Licence statements can be long; keep enough to identify them.
            found[key] = value[:1000]
    return found


def extract_xml(path: Path, settings: IngestionSettings) -> ExtractionResult:
    """Parse an XML file once and hand it to the TEI or JATS reader.

    ElementTree does not fetch external entities or DTDs; a document that
    references one fails to parse instead.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return _failed(
            path, SourceFormat.XML, "xml",
            f"File is not well-formed XML ({exc.position[0]}:{exc.position[1]}).",
        )
    if root.tag == f"{_TEI_NS}TEI":
        return extract_tei(path, root, settings)
    if _local_name(root.tag) == "article":
        return extract_jats(path, root, settings)
    return _failed(
        path, SourceFormat.XML, "xml",
        "XML root is neither a TEI P5 <TEI> nor a JATS <article> element; "
        "other XML is not supported.",
        status=ExtractionStatus.UNSUPPORTED_FORMAT,
        extractor_version=None,
    )


def extract_tei(
    path: Path, root: ET.Element, settings: IngestionSettings
) -> ExtractionResult:
    """Extract a TEI P5 document, one passage per block element.

    Locations carry the TEI xml:id of each block (verse references such as
    'Ca.6.16.5' in SARIT editions), the printed page from the nearest
    preceding <pb n>, the nearest <head> as section heading and the
    division path as item_id, so a new chapter starts a new chunk.

    Editorial <note> elements are left out of passage text: they hold
    variant readings and cross-references, not the root text. Every
    passage that lost a note is flagged, and the total is a warning.
    Whitespace from XML indentation is collapsed; verse lines (<l>) and
    <lb/> are kept as line breaks. Characters are otherwise unchanged.
    """
    extractor = "tei_xml"
    body = root.find(f"{_TEI_NS}text/{_TEI_NS}body")
    if body is None:
        return _failed(
            path, SourceFormat.XML, extractor,
            "TEI document has no <text>/<body>.",
            status=ExtractionStatus.EMPTY_OR_UNREADABLE,
        )

    passages: list[ExtractedPassage] = []
    state = {"page": None, "notes": 0}
    # One entry per open <div>: [path label, heading or None].
    divisions: list[list] = []

    def section() -> str | None:
        for _, heading in reversed(divisions):
            if heading:
                return heading
        return None

    def walk(element: ET.Element) -> None:
        for position, child in enumerate(element, start=1):
            if not isinstance(child.tag, str):
                continue
            name = _local_name(child.tag)
            if name == "pb":
                state["page"] = child.get("n") or state["page"]
                continue
            if name == "div":
                label = child.get("n") or str(position)
                divisions.append([label, None])
                walk(child)
                divisions.pop()
                continue
            if name in _TEI_SKIP_CONTENT:
                if name == "note":
                    state["notes"] += 1
                continue
            if name not in _TEI_BLOCKS:
                walk(child)
                continue

            block = _TeiBlock()
            _tei_collect(child, block, root=True)
            text = block.text()
            page_at_start = state["page"]
            if block.page_breaks:
                state["page"] = block.page_breaks[-1]
            state["notes"] += block.notes
            if not text:
                continue
            is_heading = name == "head"
            if is_heading and divisions and divisions[-1][1] is None:
                divisions[-1][1] = text.replace("\n", " ")
            flags = text_quality_flags(text, settings)
            if block.notes:
                flags.append(EDITORIAL_NOTES_FLAG)
            passages.append(
                ExtractedPassage(
                    passage_index=len(passages),
                    kind=PassageKind.HEADING if is_heading else PassageKind.PARAGRAPH,
                    text=text,
                    location=SourceLocation(
                        block_index=len(passages),
                        item_id=(
                            "div:" + "/".join(label for label, _ in divisions)
                            if divisions else None
                        ),
                        section_heading=section(),
                        element_id=(
                            block.element_ids[0] if block.element_ids
                            else _tei_attr_id(child)
                        ),
                        printed_page=page_at_start,
                    ),
                    quality_flags=flags,
                )
            )

    walk(body)
    warnings = _flag_warning(passages)
    if state["notes"]:
        warnings.append(
            f"{state['notes']} editorial <note> element(s) were left out of "
            "passage text (variant readings and cross-references)."
        )
    return _base_result(
        path,
        SourceFormat.XML,
        extractor,
        EXTRACTOR_REVISION,
        status=_classify(passages, has_issues=False),
        passages=passages,
        warnings=warnings,
        embedded_metadata=_tei_header_metadata(root),
    )


# --- JATS XML (journal articles) ---------------------------------------------

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
# Elements read as their own passages when found inside <body>/<abstract>.
_JATS_NESTED_BLOCKS = {"table-wrap", "fig", "list", "disp-quote", "boxed-text"}


def _jats_text(element: ET.Element, skip: set[str] = _JATS_NESTED_BLOCKS) -> str:
    """Element text without nested block elements, whitespace collapsed."""
    parts: list[str] = []

    def collect(node: ET.Element, top: bool) -> None:
        if not top and _local_name(node.tag) in skip:
            if node.tail:
                parts.append(node.tail)
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            if isinstance(child.tag, str):
                collect(child, False)
        if not top and node.tail:
            parts.append(node.tail)

    collect(element, True)
    return _ASCII_SPACE.sub(" ", "".join(parts)).strip()


def _jats_metadata(root: ET.Element) -> dict[str, str]:
    found: dict[str, str] = {}
    meta = root.find("front/article-meta")
    journal = root.find("front/journal-meta/journal-title-group/journal-title")
    if journal is not None:
        found["journal"] = _jats_text(journal)
    if meta is None:
        return found
    title = meta.find("title-group/article-title")
    if title is not None:
        found["title"] = _jats_text(title)
    for article_id in meta.findall("article-id"):
        kind = article_id.get("pub-id-type")
        if kind in {"doi", "pmcid", "pmid"} and article_id.text:
            found[kind] = article_id.text.strip()
    year = meta.find("pub-date/year")
    if year is not None and year.text:
        found["year"] = year.text.strip()
    licence = meta.find("permissions/license")
    if licence is not None:
        href = licence.get(_XLINK_HREF)
        if href:
            found["license_url"] = href
        text = _jats_text(licence)
        if text:
            found["license"] = text[:1000]
    return found


def extract_jats(
    path: Path, root: ET.Element, settings: IngestionSettings
) -> ExtractionResult:
    """Extract a JATS article: title, abstract and body in reading order.

    Section titles are heading passages and become section_heading for
    the text below them; item_id is the section path, so each top-level
    section starts a new chunk. Table rows are passages with cells joined
    by ' | ' (as in DOCX). The reference list, acknowledgements and other
    <back> matter are not extracted. Licence and identifiers from the
    article front matter are reported in embedded_metadata.
    """
    extractor = "jats_xml"
    passages: list[ExtractedPassage] = []

    def add(kind: PassageKind, text: str, section: str | None,
            item: str | None, element: ET.Element, **location) -> None:
        if not text:
            return
        passages.append(
            ExtractedPassage(
                passage_index=len(passages),
                kind=kind,
                text=text,
                location=SourceLocation(
                    block_index=len(passages),
                    section_heading=section,
                    item_id=item,
                    element_id=element.get("id"),
                    **location,
                ),
                quality_flags=text_quality_flags(text, settings),
            )
        )

    def blocks(element, section: str | None, item: str | None) -> None:
        for child in element:
            if not isinstance(child.tag, str):
                continue
            name = _local_name(child.tag)
            if name == "sec":
                title = child.find("title")
                heading = _jats_text(title) if title is not None else None
                label = child.get("id") or heading or str(len(passages))
                child_item = f"{item}/{label}" if item else f"sec:{label}"
                if heading:
                    add(PassageKind.HEADING, heading, heading, child_item, child)
                blocks(child, heading or section, child_item)
            elif name == "title":
                continue  # handled by the enclosing <sec>
            elif name == "p":
                add(PassageKind.PARAGRAPH, _jats_text(child), section, item, child)
                blocks_nested(child, section, item)
            elif name in {"table-wrap", "fig"}:
                caption = child.find("caption")
                if caption is not None:
                    add(PassageKind.PARAGRAPH, _jats_text(caption, set()), section, item, child)
                for table_index, table in enumerate(child.iter("table")):
                    for row_index, row in enumerate(table.iter("tr")):
                        cells = [
                            _jats_text(cell, set())
                            for cell in row
                            if isinstance(cell.tag, str)
                            and _local_name(cell.tag) in {"td", "th"}
                        ]
                        add(PassageKind.TABLE_ROW, " | ".join(c for c in cells if c),
                            section, item, child,
                            table_index=table_index, row_index=row_index)
            elif name in {"list", "list-item", "disp-quote", "boxed-text"}:
                blocks(child, section, item)

    def blocks_nested(paragraph: ET.Element, section, item) -> None:
        # Lists and tables inside a <p> follow the paragraph's own text.
        nested = [
            child for child in paragraph
            if isinstance(child.tag, str)
            and _local_name(child.tag) in _JATS_NESTED_BLOCKS
        ]
        blocks(nested, section, item)

    title = root.find("front/article-meta/title-group/article-title")
    if title is not None:
        add(PassageKind.HEADING, _jats_text(title), None, "front", title)
    for abstract in root.findall("front/article-meta/abstract"):
        add(PassageKind.HEADING, "Abstract", "Abstract", "abstract", abstract)
        blocks(abstract, "Abstract", "abstract")
    body = root.find("body")
    if body is not None:
        blocks(body, None, None)

    warnings = _flag_warning(passages)
    if body is None:
        warnings.append("Article has no <body>; only front matter was extracted.")
    return _base_result(
        path,
        SourceFormat.XML,
        extractor,
        EXTRACTOR_REVISION,
        status=_classify(passages, has_issues=body is None and bool(passages)),
        passages=passages,
        warnings=warnings,
        embedded_metadata=_jats_metadata(root),
    )


# --- Dispatcher --------------------------------------------------------------

_EXTRACTORS: dict[
    SourceFormat, Callable[[Path, IngestionSettings], ExtractionResult]
] = {
    SourceFormat.PDF: extract_pdf,
    SourceFormat.DOCX: extract_docx,
    SourceFormat.EPUB: extract_epub,
    SourceFormat.TXT: extract_plain_text,
    SourceFormat.MARKDOWN: extract_markdown,
    SourceFormat.XML: extract_xml,
}

_SIGNATURES = {
    SourceFormat.DOCX: b"PK\x03\x04",
    SourceFormat.EPUB: b"PK\x03\x04",
}


def _signature_error(path: Path, source_format: SourceFormat) -> str | None:
    with path.open("rb") as handle:
        head = handle.read(1024)
    if source_format == SourceFormat.PDF and b"%PDF-" not in head:
        return "File content does not look like a PDF."
    expected = _SIGNATURES.get(source_format)
    if expected and not head.startswith(expected):
        return (
            f"File content does not look like a {source_format.value.upper()} "
            "(ZIP) archive."
        )
    return None


def extract_document(
    path: str | Path,
    settings: IngestionSettings | None = None,
) -> ExtractionResult:
    """Extract one local source file. Never raises for bad file content."""
    path = Path(path)
    settings = settings or load_ingestion_settings()
    source_format = detect_format(path)
    extractor = f"{source_format.value}_extractor"

    if not path.is_file():
        return _failed(path, source_format, extractor, "File not found.")
    if source_format == SourceFormat.UNKNOWN:
        return _failed(
            path,
            source_format,
            "none",
            f"Unsupported file extension {path.suffix.lower() or '(none)'!r}.",
            status=ExtractionStatus.UNSUPPORTED_FORMAT,
            extractor_version=None,
        )

    try:
        if path.stat().st_size > settings.max_file_bytes:
            return _failed(
                path, source_format, extractor,
                "File exceeds the configured maximum size.",
            )
        problem = _signature_error(path, source_format)
        if problem:
            return _failed(path, source_format, extractor, problem)
        return _EXTRACTORS[source_format](path, settings)
    except OSError as exc:
        return _failed(
            path, source_format, extractor,
            f"File could not be read ({type(exc).__name__}).",
        )
    except Exception as exc:
        # Last-resort guard: report the failure instead of crashing a batch.
        logger.warning(
            "c2.ingestion.extraction_error format=%s error=%s",
            source_format.value,
            type(exc).__name__,
        )
        return _failed(
            path, source_format, extractor,
            f"Unexpected extraction error ({type(exc).__name__}).",
        )
