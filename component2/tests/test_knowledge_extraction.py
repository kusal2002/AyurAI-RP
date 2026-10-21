import codecs
import zipfile

import pytest

from app.config import IngestionSettings
from app.knowledge_ingestion.extractors import (
    SUSPECT_CHARACTERS_FLAG,
    detect_format,
    extract_document,
    text_quality_flags,
)
from app.knowledge_ingestion.models import (
    ExtractionStatus,
    PassageKind,
    SourceFormat,
)
from ingestion_test_support import (
    DEVANAGARI,
    ENGLISH,
    NBSP,
    SINHALA,
    TRANSLITERATED,
    ZWJ,
    ZWNJ,
    docx_paragraph,
    docx_table,
    make_docx,
    make_epub,
    make_pdf,
)


SETTINGS = IngestionSettings()


# --- format detection and dispatcher ----------------------------------------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("a.PDF", SourceFormat.PDF),
        ("a.docx", SourceFormat.DOCX),
        ("a.epub", SourceFormat.EPUB),
        ("a.txt", SourceFormat.TXT),
        ("a.md", SourceFormat.MARKDOWN),
        ("a.markdown", SourceFormat.MARKDOWN),
        ("a.doc", SourceFormat.UNKNOWN),
        ("a", SourceFormat.UNKNOWN),
    ],
)
def test_detect_format_by_extension(name, expected):
    assert detect_format(name) == expected


def test_missing_file_is_reported_not_raised(tmp_path):
    result = extract_document(tmp_path / "absent.pdf", SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert result.errors == ["File not found."]
    assert result.passages == []


def test_unsupported_format(tmp_path):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0 legacy word")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.UNSUPPORTED_FORMAT
    assert ".doc" in result.errors[0]


def test_file_size_limit(tmp_path):
    path = tmp_path / "big.txt"
    path.write_text("x" * 200, encoding="utf-8")

    result = extract_document(
        path, IngestionSettings(max_file_bytes=100)
    )

    assert result.status == ExtractionStatus.FAILED
    assert "maximum size" in result.errors[0]


def test_extension_content_mismatch_is_rejected(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("plain text, not a PDF", encoding="utf-8")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert "does not look like a PDF" in result.errors[0]


def test_result_records_file_name_not_full_path(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("text", encoding="utf-8")

    dumped = extract_document(path, SETTINGS).model_dump_json()

    assert str(tmp_path) not in dumped
    assert "notes.txt" in dumped


# --- plain text and Markdown -------------------------------------------------

def test_txt_preserves_sinhala_devanagari_and_mixed_text(tmp_path):
    mixed = f"{DEVANAGARI} ({TRANSLITERATED}) — {ENGLISH}"
    content = f"{SINHALA}\n\n{DEVANAGARI}\n{TRANSLITERATED}\n\n\n{mixed}\n"
    path = tmp_path / "mixed.txt"
    path.write_text(content, encoding="utf-8")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert [p.text for p in result.passages] == [
        SINHALA,
        f"{DEVANAGARI}\n{TRANSLITERATED}",
        mixed,
    ]
    assert ZWJ in result.passages[0].text
    assert [
        (p.location.line_start, p.location.line_end) for p in result.passages
    ] == [(1, 1), (3, 4), (7, 7)]
    assert [p.location.block_index for p in result.passages] == [0, 1, 2]
    assert result.extractor == "plain_text"


def test_txt_with_utf8_bom_and_crlf(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(
        codecs.BOM_UTF8 + f"{SINHALA}\r\n\r\n{ENGLISH}\r\n".encode("utf-8")
    )

    result = extract_document(path, SETTINGS)

    assert [p.text for p in result.passages] == [SINHALA, ENGLISH]
    assert not result.passages[0].text.startswith(codecs.BOM_UTF8.decode())
    assert "Decoded as utf-8-sig." in result.warnings


def test_txt_with_utf16_bom(tmp_path):
    path = tmp_path / "utf16.txt"
    path.write_bytes(f"{DEVANAGARI}\n".encode("utf-16"))

    result = extract_document(path, SETTINGS)

    assert result.passages[0].text == DEVANAGARI


def test_txt_invalid_utf8_is_not_guessed(tmp_path):
    path = tmp_path / "legacy.txt"
    path.write_bytes("Ayurveda café".encode("cp1252"))

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert "not valid UTF-8" in result.errors[0]
    assert "offset 12" in result.errors[0]
    assert result.passages == []


def test_binary_content_in_txt_fails(tmp_path):
    path = tmp_path / "binary.txt"
    path.write_bytes(b"abc\x00def")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED


def test_empty_text_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("\n   \n", encoding="utf-8")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EMPTY_OR_UNREADABLE


def test_markdown_headings_and_sections(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text(
        "Preface line\n\n# Pandu Roga\n\nFirst paragraph.\n\n"
        f"## {SINHALA} ##\n{DEVANAGARI}\n",
        encoding="utf-8",
    )

    result = extract_document(path, SETTINGS)

    assert result.source_format == SourceFormat.MARKDOWN
    assert [(p.kind, p.text) for p in result.passages] == [
        (PassageKind.PARAGRAPH, "Preface line"),
        (PassageKind.HEADING, "# Pandu Roga"),
        (PassageKind.PARAGRAPH, "First paragraph."),
        (PassageKind.HEADING, f"## {SINHALA} ##"),
        (PassageKind.PARAGRAPH, DEVANAGARI),
    ]
    assert [p.location.section_heading for p in result.passages] == [
        None, "Pandu Roga", "Pandu Roga", SINHALA, SINHALA,
    ]


def test_hash_is_heading_only_in_markdown(tmp_path):
    path = tmp_path / "plain.txt"
    path.write_text("# not a heading in txt\n", encoding="utf-8")

    result = extract_document(path, SETTINGS)

    assert result.passages[0].kind == PassageKind.PARAGRAPH


def test_garbled_text_is_flagged_for_review(tmp_path):
    path = tmp_path / "garbled.txt"
    path.write_text(chr(0xFFFD) * 10 + " abc", encoding="utf-8")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.NEEDS_OCR_OR_REVIEW
    assert result.passages[0].quality_flags == [SUSPECT_CHARACTERS_FLAG]
    assert result.warnings


def test_quality_flags_accept_clean_indic_text():
    text = f"{SINHALA} {DEVANAGARI} {TRANSLITERATED} {ZWNJ}"
    assert text_quality_flags(text, SETTINGS) == []
    assert text_quality_flags(chr(0xE000) * 5, SETTINGS) == [
        SUSPECT_CHARACTERS_FLAG
    ]


# --- PDF ---------------------------------------------------------------------

def test_pdf_text_pages_keep_page_numbers(tmp_path):
    path = make_pdf(
        tmp_path / "book.pdf",
        [
            "Chapter one describes pandu roga.",
            "Second page lists herbs.\nAnother line on page two.",
        ],
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.page_count == 2
    assert [p.location.page for p in result.passages] == [1, 2]
    assert all(p.kind == PassageKind.PAGE for p in result.passages)
    assert "pandu roga" in result.passages[0].text
    assert "Another line" in result.passages[1].text
    assert result.extractor == "pypdf"
    assert result.extractor_version


def test_scanned_pdf_needs_ocr(tmp_path):
    path = make_pdf(
        tmp_path / "scan.pdf", [None, None, None], image_pages={1, 2, 3}
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.NEEDS_OCR_OR_REVIEW
    assert result.pages_needing_ocr == [1, 2, 3]
    assert result.passages == []


def test_partially_scanned_pdf_reports_pages(tmp_path):
    path = make_pdf(
        tmp_path / "mixed.pdf",
        ["A page with a proper text layer.", None, "Third page text layer."],
        image_pages={2},
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.PARTIAL_EXTRACTION
    assert result.pages_needing_ocr == [2]
    assert [p.location.page for p in result.passages] == [1, 3]


def test_blank_pdf_page_is_reported_not_dropped(tmp_path):
    path = make_pdf(
        tmp_path / "blank.pdf", ["Text on the first page only.", None]
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.blank_pages == [2]
    assert any("blank" in warning for warning in result.warnings)


def test_pdf_without_any_text_or_images_is_empty(tmp_path):
    path = make_pdf(tmp_path / "empty.pdf", [None, None])

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EMPTY_OR_UNREADABLE
    assert result.blank_pages == [1, 2]


def test_short_page_text_is_kept_but_flagged(tmp_path):
    path = make_pdf(tmp_path / "short.pdf", ["12"], image_pages={1})

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.NEEDS_OCR_OR_REVIEW
    assert result.passages[0].text.strip() == "12"
    assert "short_page_text" in result.passages[0].quality_flags
    assert result.pages_needing_ocr == [1]


def test_corrupted_pdf_fails_gracefully(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\n this is not a real pdf body \x00\xff")

    result = extract_document(path, SETTINGS)

    assert result.status in {
        ExtractionStatus.FAILED,
        ExtractionStatus.EMPTY_OR_UNREADABLE,
    }
    assert result.errors
    assert result.passages == []


# --- DOCX --------------------------------------------------------------------

def test_docx_paragraphs_headings_and_tables_in_order(tmp_path):
    body = (
        docx_paragraph("Pandu Roga", style="Heading1")
        + docx_paragraph(SINHALA)
        + docx_paragraph("")
        + docx_table([["Herb", "Part"], [DEVANAGARI, "root"]])
        + docx_paragraph(ENGLISH)
    )
    path = make_docx(tmp_path / "book.docx", body, title="Synthetic DOCX")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert [(p.kind, p.text) for p in result.passages] == [
        (PassageKind.HEADING, "Pandu Roga"),
        (PassageKind.PARAGRAPH, SINHALA),
        (PassageKind.TABLE_ROW, "Herb | Part"),
        (PassageKind.TABLE_ROW, f"{DEVANAGARI} | root"),
        (PassageKind.PARAGRAPH, ENGLISH),
    ]
    rows = [p for p in result.passages if p.kind == PassageKind.TABLE_ROW]
    assert [(r.location.table_index, r.location.row_index) for r in rows] == [
        (0, 0), (0, 1)
    ]
    # The empty paragraph still occupies a block position.
    assert [p.location.block_index for p in result.passages] == [0, 1, 3, 3, 4]
    assert all(
        p.location.section_heading == "Pandu Roga" for p in result.passages
    )
    assert result.embedded_metadata == {"title": "Synthetic DOCX"}


def test_docx_table_text_is_not_duplicated_as_paragraphs(tmp_path):
    path = make_docx(tmp_path / "t.docx", docx_table([["only in table"]]))

    result = extract_document(path, SETTINGS)

    texts = [p.text for p in result.passages]
    assert texts == ["only in table"]


def test_docx_skips_deleted_tracked_changes(tmp_path):
    body = (
        "<w:p><w:r><w:t>kept </w:t></w:r>"
        "<w:del><w:r><w:delText>removed</w:delText></w:r></w:del>"
        "<w:r><w:tab/><w:t>tail</w:t></w:r></w:p>"
    )
    path = make_docx(tmp_path / "tracked.docx", body)

    result = extract_document(path, SETTINGS)

    assert result.passages[0].text == "kept \ttail"


def test_corrupted_docx(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"PK\x03\x04 truncated archive")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert "not a valid DOCX" in result.errors[0]


def test_docx_missing_document_part(tmp_path):
    path = tmp_path / "nodoc.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("other.xml", "<x/>")

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert "word/document.xml" in result.errors[0]


def test_docx_archive_member_size_limit(tmp_path):
    path = make_docx(tmp_path / "big.docx", docx_paragraph("x" * 5000))

    result = extract_document(
        path, IngestionSettings(max_archive_member_bytes=1000)
    )

    assert result.status == ExtractionStatus.FAILED
    assert "size limit" in result.errors[0]


# --- EPUB --------------------------------------------------------------------

def test_epub_spine_order_headings_and_unicode(tmp_path):
    path = make_epub(
        tmp_path / "book.epub",
        [
            (
                "ch1",
                f"<h1>Adhyaya 1</h1><p>{DEVANAGARI}</p>"
                "<script>var hidden = 'script text';</script>"
                f"<p>{TRANSLITERATED}<br/>second   line</p>",
            ),
            (
                "ch2",
                f"<h2>{SINHALA}</h2><div><p>Nested{NBSP}text"
                f" with{ZWNJ}joiner</p>tail text</div>",
            ),
        ],
        title="Synthetic EPUB",
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.EXTRACTED
    assert [(p.kind, p.text) for p in result.passages] == [
        (PassageKind.HEADING, "Adhyaya 1"),
        (PassageKind.PARAGRAPH, DEVANAGARI),
        (PassageKind.PARAGRAPH, f"{TRANSLITERATED}\nsecond line"),
        (PassageKind.HEADING, SINHALA),
        (PassageKind.PARAGRAPH, f"Nested{NBSP}text with{ZWNJ}joiner"),
        (PassageKind.PARAGRAPH, "tail text"),
    ]
    assert [p.location.item_id for p in result.passages] == [
        "ch1", "ch1", "ch1", "ch2", "ch2", "ch2",
    ]
    assert result.passages[0].location.item_href == "OEBPS/text/ch1.xhtml"
    assert result.passages[4].location.section_heading == SINHALA
    assert all("script text" not in p.text for p in result.passages)
    assert all("ignored head title" not in p.text for p in result.passages)
    assert result.embedded_metadata == {
        "title": "Synthetic EPUB",
        "language": "sa",
    }


def test_epub_without_container_fails(tmp_path):
    path = make_epub(
        tmp_path / "bad.epub", [("c", "<p>x</p>")], include_container=False
    )

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.FAILED
    assert "container.xml" in result.errors[0]


def test_epub_with_unreadable_item_is_partial(tmp_path):
    path = make_epub(tmp_path / "part.epub", [("ok", "<p>readable</p>")])
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("OEBPS/text/bad.xhtml", b"<p>\x80\x81 broken</p>")
    # Add the broken item to the spine by rewriting the package file.
    with zipfile.ZipFile(path) as archive:
        members = {
            name: archive.read(name) for name in archive.namelist()
        }
    opf = members["OEBPS/content.opf"].decode("utf-8")
    opf = opf.replace(
        "<manifest>",
        '<manifest><item id="bad" href="text/bad.xhtml" '
        'media-type="application/xhtml+xml"/>',
    ).replace("<spine>", '<spine><itemref idref="bad"/>')
    members["OEBPS/content.opf"] = opf.encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    result = extract_document(path, SETTINGS)

    assert result.status == ExtractionStatus.PARTIAL_EXTRACTION
    assert [p.text for p in result.passages] == ["readable"]
    assert "bad" in result.errors[0]


def test_pdf_library_warnings_are_recorded_not_printed(tmp_path, capsys):
    path = make_pdf(tmp_path / "book.pdf", ["Text layer present on page."])

    def noisy_extract(path, settings):
        import logging
        from app.knowledge_ingestion import extractors

        for _ in range(3):
            logging.getLogger("pypdf._cmap").warning(
                "fontTools is required to fully parse the encoding "
                "in font dictionary {'/BaseFont': '/X'}"
            )
        return extractors._base_result(
            path, SourceFormat.PDF, "pypdf", "test",
            status=ExtractionStatus.EXTRACTED,
        )

    from unittest.mock import patch

    with patch(
        "app.knowledge_ingestion.extractors._extract_pdf", noisy_extract
    ):
        result = extract_document(path, SETTINGS)

    assert result.warnings == [
        "pypdf: fontTools is required to fully parse the encoding (x3)"
    ]
    captured = capsys.readouterr()
    assert "fontTools" not in captured.err + captured.out
