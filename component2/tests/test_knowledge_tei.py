"""TEI P5 reader (SARIT-style classical texts). Synthetic files only."""

from app.config import IngestionSettings
from app.knowledge_ingestion.chunking import chunk_passages, validate_chunks
from app.knowledge_ingestion.extractors import (
    EDITORIAL_NOTES_FLAG,
    detect_format,
    extract_document,
)
from app.knowledge_ingestion.models import (
    ExtractionStatus,
    PassageKind,
    SourceFormat,
)
from ingestion_test_support import SYNTHETIC_TEI_BODY, make_tei


SETTINGS = IngestionSettings()


def _extract(tmp_path, body=SYNTHETIC_TEI_BODY):
    return extract_document(make_tei(tmp_path / "syn.xml", body), SETTINGS)


def test_xml_extension_maps_to_xml():
    assert detect_format("a.XML") == SourceFormat.XML


def test_tei_blocks_keep_verse_ids_pages_and_sections(tmp_path):
    result = _extract(tmp_path)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.extractor == "tei_xml"
    by_id = {p.location.element_id: p for p in result.passages}
    verse = by_id["Syn.6.16.1"]
    assert verse.kind == PassageKind.PARAGRAPH
    # Verse lines stay separate lines; indentation is collapsed; the
    # label and the editorial note are not part of the text.
    assert verse.text == "pāṇḍuroge lakṣaṇāni vakṣyāmi/\ntvak pāṇḍutā ca dṛśyate//"
    assert EDITORIAL_NOTES_FLAG in verse.quality_flags
    assert verse.location.printed_page == "512"
    assert verse.location.section_heading == "pāṇḍurogacikitsitam"
    assert verse.location.item_id == "div:6/16"
    # Footnote markers are dropped; <lb/> becomes a line break.
    assert by_id["Syn.6.16.2"].text == "Pallor is a symptom of pandu."
    assert by_id["Syn.6.16.3"].text == "triphalā\npunarnavā ca"
    assert by_id["Syn.6.16.3"].location.printed_page == "513"
    assert by_id["Syn.6.17.1"].location.item_id == "div:6/17"
    assert any("1 editorial <note>" in w for w in result.warnings)


def test_tei_headings_are_heading_passages(tmp_path):
    result = _extract(tmp_path)
    headings = [p.text for p in result.passages if p.kind == PassageKind.HEADING]
    assert headings == ["cikitsāsthānam", "pāṇḍurogacikitsitam", "hikkāśvāsacikitsitam"]


def test_tei_header_metadata_is_reported_not_trusted(tmp_path):
    result = _extract(tmp_path)
    assert result.embedded_metadata["title"] == "Synthetic Samhita"
    assert "CC BY-SA 3.0" in result.embedded_metadata["availability"]


def test_tei_chunks_carry_citation_refs_and_stop_at_chapters(tmp_path):
    result = _extract(tmp_path)
    chunks = chunk_passages("syn", result.passages, SETTINGS)

    assert validate_chunks(chunks, result.passages, SETTINGS) == []
    first = next(c for c in chunks if "Syn.6.16.1" in c.citation_refs)
    assert first.citation_refs == ["Syn.6.16.1", "Syn.6.16.2", "Syn.6.16.3"]
    assert first.printed_pages == ["512", "513"]
    assert first.iast_present
    # Adhyaya 17 starts a new chunk.
    assert "Syn.6.17.1" not in first.citation_refs
    assert any(c.citation_refs == ["Syn.6.17.1"] for c in chunks)


def test_tei_chunk_ids_are_stable(tmp_path):
    result = _extract(tmp_path)
    again = _extract(tmp_path)
    ids = [c.chunk_id for c in chunk_passages("syn", result.passages, SETTINGS)]
    assert ids == [c.chunk_id for c in chunk_passages("syn", again.passages, SETTINGS)]


def test_non_tei_xml_is_unsupported(tmp_path):
    path = tmp_path / "other.xml"
    path.write_text("<?xml version='1.0'?><catalog><book/></catalog>", encoding="utf-8")
    result = extract_document(path, SETTINGS)
    assert result.status == ExtractionStatus.UNSUPPORTED_FORMAT
    assert "TEI" in result.errors[0] and "JATS" in result.errors[0]


def test_malformed_xml_fails_without_raising(tmp_path):
    path = tmp_path / "broken.xml"
    path.write_text("<TEI><text>", encoding="utf-8")
    result = extract_document(path, SETTINGS)
    assert result.status == ExtractionStatus.FAILED
    assert "well-formed" in result.errors[0]


def test_tei_without_body_is_empty(tmp_path):
    path = tmp_path / "nobody.xml"
    path.write_text('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/></TEI>', encoding="utf-8")
    result = extract_document(path, SETTINGS)
    assert result.status == ExtractionStatus.EMPTY_OR_UNREADABLE


def test_xml_entities_are_not_resolved_from_outside(tmp_path):
    path = tmp_path / "xxe.xml"
    path.write_text(
        '<?xml version="1.0"?><!DOCTYPE TEI [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>a &x; b</p></body></text></TEI>',
        encoding="utf-8",
    )
    result = extract_document(path, SETTINGS)
    # ElementTree refuses undefined external entities instead of reading them.
    assert result.status == ExtractionStatus.FAILED


# --- JATS -----------------------------------------------------------------

from ingestion_test_support import make_jats  # noqa: E402


def test_jats_article_sections_tables_and_metadata(tmp_path):
    result = extract_document(make_jats(tmp_path / "a.xml"), SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.extractor == "jats_xml"
    texts = [p.text for p in result.passages]
    assert texts[0] == "Synthetic review of pandu"
    assert "Pallor is described in pandu [1]." in texts
    intro = next(p for p in result.passages if p.text == "Pandu is discussed.")
    assert intro.location.section_heading == "Introduction"
    assert intro.location.element_id == "p1"
    assert "first point" in texts
    nested = next(p for p in result.passages if p.text == "Nested text.")
    assert nested.location.item_id == "sec:s1/s1a"
    rows = [p.text for p in result.passages if p.kind == PassageKind.TABLE_ROW]
    assert rows == ["Group | Hb", "A | 10.1"]
    # Reference list (<back>) is not extracted.
    assert "Ref text" not in " ".join(texts)
    meta = result.embedded_metadata
    assert meta["doi"] == "10.0000/synthetic.1"
    assert meta["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert meta["journal"] == "Synthetic Journal"
    chunks = chunk_passages("a", result.passages, SETTINGS)
    assert validate_chunks(chunks, result.passages, SETTINGS) == []
    assert "p1" in next(c for c in chunks if "Pandu is discussed." in c.text).citation_refs


def test_nested_division_headings_never_form_heading_only_chunks(tmp_path):
    body = """
<div n="4"><head>Part 4 Cikitsāsthānam</head>
  <div n="1"><head>prathamo 'dhyāyaḥ</head>
    <lg><l xml:id="X.4.1.1">atha khalu verse text of the first chapter//</l></lg>
  </div>
</div>
"""
    result = _extract(tmp_path, body)
    chunks = chunk_passages("x", result.passages, SETTINGS)
    assert validate_chunks(chunks, result.passages, SETTINGS) == []
    [chunk] = chunks
    assert chunk.text.startswith("Part 4 Cikitsāsthānam")
    assert chunk.citation_refs == ["X.4.1.1"]


def test_unrelated_divisions_still_split():
    from app.knowledge_ingestion.chunking import _same_or_nested
    assert _same_or_nested("div:4", "div:4/1")
    assert not _same_or_nested("div:4", "div:41")
    assert not _same_or_nested("div:4/1", "div:4")
    assert not _same_or_nested(None, "div:4")
