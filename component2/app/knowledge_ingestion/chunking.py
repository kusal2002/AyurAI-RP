"""Boundary-aware chunking of extracted passages.

Passages are cut into units at the largest boundary that keeps each unit
within the size limit, in this order:

1. paragraphs (blank lines);
2. verse ends ('॥ 12 ॥', '॥', '|| 12 ||') and sentence ends ('.', '?',
   '!', Sinhala kunddaliya '෴');
3. half-verse dandas ('।'), clause punctuation and line breaks;
4. whitespace;
5. a hard cut that never separates a combining mark, virama, ZWJ or ZWNJ
   from its letter.

So a verse is only split when it alone is longer than the limit. Units are
then packed into chunks of at most chunk_max_chars normalized characters.
A heading, or a change of section heading or EPUB document, starts a new
chunk; otherwise consecutive chunks overlap by whole trailing units up to
chunk_overlap_chars. Chunks may span PDF pages; page_start/page_end and
passage_spans record exactly where the text came from.

Chunk IDs are derived from the source ID, the exact passage spans, the
chunk text and the chunker/normalization versions, so re-chunking
unchanged input yields the same IDs and an edit elsewhere in a book does
not change them.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from app.config import IngestionSettings
from app.knowledge_ingestion.models import (
    ExtractedPassage,
    PassageKind,
    PassageSpan,
    SourceMetadata,
    TextChunk,
)
from app.knowledge_ingestion.normalization import (
    NORMALIZATION_VERSION,
    ZWJ,
    ZWNJ,
    find_verse_numbers,
    normalize_text,
    profile_scripts,
)


CHUNKER_VERSION = "1"
EXCEEDS_MAX_FLAG = "exceeds_max_chars"

# Separator counted between two units when estimating chunk length. The
# normalized join is at most a blank line ("\n\n").
_JOIN_CHARS = 2

_PARAGRAPH = re.compile(r"\n[ \t]*\n")
_VERSE_OR_SENTENCE = re.compile(
    r"(?:॥|\|\|)\s*[०-९0-9]+(?:\s*[-–]\s*[०-९0-9]+)?\s*(?:॥|\|\|)"
    r"|॥"
    r"|[.?!෴](?=\s)"
)
_CLAUSE = re.compile(r"[।;:,](?=\s)|\n")
_WHITESPACE = re.compile(r"\s+")
_LEVELS = (_VERSE_OR_SENTENCE, _CLAUSE, _WHITESPACE)

_VIRAMAS = {chr(0x094D), chr(0x0DCA)}


def _trim(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _split(text: str, start: int, end: int, pattern) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    for match in pattern.finditer(text, start, end):
        cut = match.end()
        if cut <= cursor:
            continue
        span = _trim(text, cursor, cut)
        if span:
            spans.append(span)
        cursor = cut
    span = _trim(text, cursor, end)
    if span:
        spans.append(span)
    return spans


def _unsafe_cut(text: str, position: int) -> bool:
    """True if cutting before text[position] would break a cluster."""
    char = text[position]
    previous = text[position - 1]
    return (
        unicodedata.category(char).startswith("M")
        or char in (ZWJ, ZWNJ)
        or previous in _VIRAMAS
        or previous in (ZWJ, ZWNJ)
    )


def _hard_split(
    text: str, start: int, end: int, max_chars: int
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    while end - start > max_chars:
        cut = start + max_chars
        while cut > start + 1 and _unsafe_cut(text, cut):
            cut -= 1
        if cut == start + 1:
            cut = start + max_chars
        spans.append((start, cut))
        start = cut
    spans.append((start, end))
    return spans


def segment_spans(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Cut text into trimmed (start, end) spans of at most max_chars."""
    result: list[tuple[int, int]] = []

    def refine(start: int, end: int, level: int) -> None:
        if end - start <= max_chars:
            result.append((start, end))
            return
        if level >= len(_LEVELS):
            result.extend(_hard_split(text, start, end, max_chars))
            return
        pieces = _split(text, start, end, _LEVELS[level])
        if len(pieces) == 1 and pieces[0] == (start, end):
            refine(start, end, level + 1)
            return
        for piece_start, piece_end in pieces:
            refine(piece_start, piece_end, level + 1)

    for start, end in _split(text, 0, len(text), _PARAGRAPH):
        refine(start, end, 0)
    return result


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Split text into paragraphs, then sentences or verses (no size limit).

    Uses the same boundaries as chunking (blank lines, verse markers,
    '.', '?', '!', '෴'); half-verse dandas do not end a sentence.
    """
    spans: list[tuple[int, int]] = []
    for start, end in _split(text, 0, len(text), _PARAGRAPH):
        spans.extend(_split(text, start, end, _VERSE_OR_SENTENCE))
    return spans


@dataclass
class _Unit:
    passage: ExtractedPassage
    start: int
    end: int
    length: int
    is_heading: bool

    @property
    def section_key(self) -> tuple:
        location = self.passage.location
        return (location.section_heading, location.item_id)


def _units(
    passages: Iterable[ExtractedPassage], max_chars: int
) -> list[_Unit]:
    units = []
    for passage in passages:
        for start, end in segment_spans(passage.text, max_chars):
            normalized = normalize_text(passage.text[start:end]).text
            if not normalized:
                continue
            units.append(
                _Unit(
                    passage,
                    start,
                    end,
                    len(normalized),
                    passage.kind == PassageKind.HEADING,
                )
            )
    return units


def _estimated_length(units: list[_Unit]) -> int:
    if not units:
        return 0
    return sum(unit.length for unit in units) + _JOIN_CHARS * (len(units) - 1)


def _overlap_tail(units: list[_Unit], overlap_chars: int) -> list[_Unit]:
    tail: list[_Unit] = []
    for unit in reversed(units[1:]):
        if _estimated_length([unit, *tail]) > overlap_chars:
            break
        tail.insert(0, unit)
    return tail


def _same_or_nested(current: str | None, following: str | None) -> bool:
    """True if following is the same item or a division nested inside it.

    TEI and JATS item IDs are division paths ('div:6', 'div:6/16'). A part
    heading followed directly by a chapter heading belongs with that
    chapter's text, so it must not become a heading-only chunk. EPUB item
    IDs are document IDs, which never nest this way.
    """
    if current == following:
        return True
    return bool(current and following and following.startswith(current + "/"))


def _pack(
    units: list[_Unit], max_chars: int, overlap_chars: int
) -> list[list[_Unit]]:
    groups: list[list[_Unit]] = []
    current: list[_Unit] = []

    for unit in units:
        if not current:
            current = [unit]
            continue

        boundary = (
            unit.section_key != current[-1].section_key or unit.is_heading
        )
        # Keep consecutive headings (chapter title, then section title)
        # together with the text that follows them.
        if (
            boundary
            and all(item.is_heading for item in current)
            and _same_or_nested(
                current[-1].passage.location.item_id,
                unit.passage.location.item_id,
            )
        ):
            boundary = False
        too_long = _estimated_length([*current, unit]) > max_chars
        if not boundary and not too_long:
            current.append(unit)
            continue

        groups.append(current)
        overlap = [] if boundary else _overlap_tail(current, overlap_chars)
        if overlap and _estimated_length([*overlap, unit]) > max_chars:
            overlap = []
        current = [*overlap, unit]

    if current:
        groups.append(current)
    return groups


def _merged_spans(units: list[_Unit]) -> list[tuple[ExtractedPassage, int, int]]:
    merged: list[tuple[ExtractedPassage, int, int]] = []
    for unit in units:
        if merged and merged[-1][0].passage_index == unit.passage.passage_index:
            passage, start, _ = merged[-1]
            merged[-1] = (passage, start, unit.end)
        else:
            merged.append((unit.passage, unit.start, unit.end))
    return merged


def make_chunk_id(
    source_id: str, spans: list[PassageSpan], content_sha256: str
) -> str:
    payload = json.dumps(
        [
            source_id,
            CHUNKER_VERSION,
            NORMALIZATION_VERSION,
            [[s.passage_index, s.start, s.end] for s in spans],
            content_sha256,
        ],
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{source_id}#chk-{digest[:16]}"


def _line_number(passage: ExtractedPassage, offset: int) -> int | None:
    if passage.location.line_start is None:
        return None
    return passage.location.line_start + passage.text.count("\n", 0, offset)


def _build_chunk(
    source_id: str,
    index: int,
    units: list[_Unit],
    metadata: SourceMetadata,
    max_chars: int,
) -> TextChunk:
    merged = _merged_spans(units)
    original = "\n\n".join(passage.text[start:end] for passage, start, end in merged)
    normalized = normalize_text(original)
    spans = [
        PassageSpan(passage_index=passage.passage_index, start=start, end=end)
        for passage, start, end in merged
    ]
    content_sha256 = hashlib.sha256(normalized.text.encode("utf-8")).hexdigest()

    pages = [p.location.page for p, _, _ in merged if p.location.page is not None]
    first_passage, first_start, _ = merged[0]
    last_passage, _, last_end = merged[-1]

    flags: list[str] = []
    for passage, _, _ in merged:
        for flag in passage.quality_flags:
            if flag not in flags:
                flags.append(flag)
    for flag in normalized.flags:
        if flag not in flags:
            flags.append(flag)
    if len(normalized.text) > max_chars:
        flags.append(EXCEEDS_MAX_FLAG)

    citation_refs: list[str] = []
    printed_pages: list[str] = []
    for passage, _, _ in merged:
        location = passage.location
        if location.element_id and location.element_id not in citation_refs:
            citation_refs.append(location.element_id)
        if location.printed_page and location.printed_page not in printed_pages:
            printed_pages.append(location.printed_page)

    profile = profile_scripts(normalized.text)
    return TextChunk(
        chunk_id=make_chunk_id(source_id, spans, content_sha256),
        source_id=source_id,
        chunk_index=index,
        text=normalized.text,
        original_text=original,
        content_sha256=content_sha256,
        passage_spans=spans,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        line_start=_line_number(first_passage, first_start),
        line_end=_line_number(last_passage, last_end),
        section_heading=first_passage.location.section_heading,
        item_id=first_passage.location.item_id,
        verse_numbers=find_verse_numbers(original),
        citation_refs=citation_refs,
        printed_pages=printed_pages,
        primary_script=profile.primary_script,
        scripts=profile.scripts,
        iast_present=profile.iast_present,
        declared_source_language=metadata.source_language,
        declared_translation_language=metadata.translation_language,
        quality_flags=flags,
        chunker_version=CHUNKER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
    )


def chunk_passages(
    source_id: str,
    passages: list[ExtractedPassage],
    settings: IngestionSettings,
    metadata: SourceMetadata | None = None,
) -> list[TextChunk]:
    """Chunk one source's passages (in passage_index order)."""
    metadata = metadata or SourceMetadata()
    ordered = sorted(passages, key=lambda passage: passage.passage_index)
    units = _units(ordered, settings.chunk_max_chars)
    groups = _pack(units, settings.chunk_max_chars, settings.chunk_overlap_chars)
    return [
        _build_chunk(source_id, index, group, metadata, settings.chunk_max_chars)
        for index, group in enumerate(groups)
    ]


def validate_chunks(
    chunks: list[TextChunk],
    passages: list[ExtractedPassage],
    settings: IngestionSettings,
) -> list[str]:
    """Check chunks against their passages. Returns problem descriptions.

    Verifies unique IDs and order, that every span lies inside its passage
    and reproduces original_text, that text is the normalization of
    original_text, that IDs and hashes recompute, that size limits hold,
    and that no passage content was left out of every chunk.
    """
    problems: list[str] = []
    by_index = {passage.passage_index: passage for passage in passages}
    seen: set[str] = set()
    covered: dict[int, bytearray] = {
        passage.passage_index: bytearray(len(passage.text))
        for passage in passages
    }

    for position, chunk in enumerate(chunks):
        label = f"chunk {chunk.chunk_index} ({chunk.chunk_id})"
        if chunk.chunk_id in seen:
            problems.append(f"{label}: duplicate chunk_id")
        seen.add(chunk.chunk_id)
        if chunk.chunk_index != position:
            problems.append(f"{label}: chunk_index out of order")

        pieces = []
        spans_ok = True
        for span in chunk.passage_spans:
            passage = by_index.get(span.passage_index)
            if passage is None or not 0 <= span.start < span.end <= len(passage.text):
                problems.append(f"{label}: span outside passage {span.passage_index}")
                spans_ok = False
                continue
            pieces.append(passage.text[span.start:span.end])
            covered[span.passage_index][span.start:span.end] = (
                b"\x01" * (span.end - span.start)
            )
        if not spans_ok:
            continue

        if "\n\n".join(pieces) != chunk.original_text:
            problems.append(f"{label}: original_text does not match passages")
        if normalize_text(chunk.original_text).text != chunk.text:
            problems.append(f"{label}: text is not the normalized original")
        digest = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
        if digest != chunk.content_sha256:
            problems.append(f"{label}: content_sha256 mismatch")
        expected_id = make_chunk_id(chunk.source_id, chunk.passage_spans, digest)
        if chunk.chunk_id != expected_id:
            problems.append(f"{label}: chunk_id does not recompute")
        if (
            len(chunk.text) > settings.chunk_max_chars
            and EXCEEDS_MAX_FLAG not in chunk.quality_flags
        ):
            problems.append(f"{label}: longer than chunk_max_chars")

    for passage in passages:
        mask = covered[passage.passage_index]
        missing = [
            offset
            for offset, char in enumerate(passage.text)
            if not mask[offset]
            and not char.isspace()
            and normalize_text(char).text
        ]
        if missing:
            problems.append(
                f"passage {passage.passage_index}: {len(missing)} "
                "character(s) not covered by any chunk"
            )
    return problems
