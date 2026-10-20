import json
import unicodedata

import pytest

from app.config import IngestionSettings
from app.knowledge_ingestion.chunking import (
    EXCEEDS_MAX_FLAG,
    chunk_passages,
    segment_spans,
    validate_chunks,
)
from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.models import (
    ExtractedPassage,
    PassageKind,
    SourceLocation,
    SourceMetadata,
)
from app.knowledge_ingestion.normalization import (
    DETACHED_DIACRITICS_FLAG,
    LETTER_SPACED_FLAG,
    PRIVATE_USE_REMOVED_FLAG,
    find_verse_numbers,
    normalize_text,
    profile_scripts,
)
from app.knowledge_ingestion.service import (
    chunks_path,
    load_chunks,
    process_source,
    write_extraction,
)
from ingestion_test_support import (
    DEVANAGARI,
    ENGLISH,
    NBSP,
    SINHALA,
    TRANSLITERATED,
    ZWJ,
    ZWNJ,
    make_pdf,
)


VIRAMA = chr(0x094D)
SOFT_HYPHEN = chr(0x00AD)
VERSE_7 = (
    "तेहेंतुभिः समुद्दिष्टं पित्तं रक्तं प्रपद्यते । "
    "तयोनित्यात् प्रपन्नं च वर्धते तत् प्रदूषयत् ॥ ७ ॥"
)
VERSE_9 = (
    "संयोगाद्दूषणात्तत्तु सामान्याद्गन्धवर्णयोः । "
    "रक्तस्य पित्तमाख्यातं रक्तपित्तं मनीषिभिः ॥ ९ ॥"
)


def passage(index, text, kind=PassageKind.PARAGRAPH, **location):
    return ExtractedPassage(
        passage_index=index,
        kind=kind,
        text=text,
        location=SourceLocation(**location),
    )


def settings(max_chars=200, overlap=60):
    return IngestionSettings(
        chunk_max_chars=max_chars, chunk_overlap_chars=overlap
    )


# --- normalization -----------------------------------------------------------

def test_nfc_composes_equivalent_sequences():
    decomposed = "Pen" + chr(0x0303) + "a ka" + chr(0x0304) + "s" + chr(0x0323)
    assert normalize_text(decomposed).text == normalize_text("Peña kāṣ").text
    assert unicodedata.is_normalized("NFC", normalize_text(decomposed).text)


def test_normalization_keeps_joiners_and_indic_text():
    text = f"{SINHALA} {DEVANAGARI} क{ZWNJ}ष {TRANSLITERATED}"
    result = normalize_text(text)
    assert ZWJ in result.text and ZWNJ in result.text
    assert result.text == unicodedata.normalize("NFC", text)
    assert result.flags == []


def test_normalization_cleans_layout_artifacts_only():
    original = (
        f"  de{chr(0xFB01)}ciency\tand{NBSP}{NBSP}anaemia  \r\n"
        f"cyto{SOFT_HYPHEN}plasm {chr(0xF034)}\n\n\n\nnext"
    )
    result = normalize_text(original)
    assert result.text == "deficiency and anaemia\ncytoplasm\n\nnext"
    assert PRIVATE_USE_REMOVED_FLAG in result.flags


def test_normalization_is_idempotent():
    text = f"{VERSE_7}\n\n{ENGLISH}  {chr(0xFB02)}ow"
    once = normalize_text(text).text
    assert normalize_text(once).text == once


def test_quality_flags_for_conversion_artifacts():
    assert DETACHED_DIACRITICS_FLAG in normalize_text(
        "Parra-Pe" + chr(0x02DC) + "na"
    ).flags
    spaced = " ".join("thisisletterspacedtextfromabadconversion")
    assert LETTER_SPACED_FLAG in normalize_text(spaced).flags
    assert LETTER_SPACED_FLAG not in normalize_text(ENGLISH * 3).flags


@pytest.mark.parametrize(
    "text, primary, scripts, iast",
    [
        (DEVANAGARI, "Deva", ["Deva"], False),
        (SINHALA, "Sinh", ["Sinh"], False),
        (ENGLISH, "Latn", ["Latn"], False),
        (TRANSLITERATED, "Latn", ["Latn"], True),
        (f"{DEVANAGARI} {ENGLISH}", "mixed", ["Latn", "Deva"], False),
        ("12 ॥ ३ ॥", "unknown", [], False),
    ],
)
def test_script_profile(text, primary, scripts, iast):
    profile = profile_scripts(text)
    assert profile.primary_script == primary
    assert profile.scripts == scripts
    assert profile.iast_present is iast


def test_verse_numbers_from_danda_markers():
    text = f"{VERSE_7} text || 12 || more ॥ १३-१४ ॥ again ॥ ७ ॥"
    assert find_verse_numbers(text) == ["7", "12", "13-14"]
    assert find_verse_numbers("Chapter 7. [ 5-6 ]") == []


# --- segmentation ------------------------------------------------------------

def test_segment_prefers_paragraphs_then_verses():
    text = f"{VERSE_7} {VERSE_9}\n\nShort paragraph."
    spans = segment_spans(text, max_chars=100)
    pieces = [text[s:e] for s, e in spans]
    assert pieces == [VERSE_7, VERSE_9, "Short paragraph."]


def test_half_verse_danda_is_used_only_when_needed():
    spans = segment_spans(VERSE_7, max_chars=60)
    pieces = [VERSE_7[s:e] for s, e in spans]
    assert pieces[0].endswith("।")
    assert "".join(p.replace(" ", "") for p in pieces) == VERSE_7.replace(" ", "")


def test_hard_cut_never_splits_a_cluster():
    word = "क्षत्रियाणां" * 20  # no spaces or punctuation
    spans = segment_spans(word, max_chars=17)
    assert "".join(word[s:e] for s, e in spans) == word
    for start, end in spans:
        piece = word[start:end]
        assert not unicodedata.category(piece[0]).startswith("M")
        assert not piece.endswith(VIRAMA)
        assert end - start <= 17


def test_sinhala_sentences_split_at_full_stop():
    text = f"{SINHALA}. {SINHALA}. {SINHALA}."
    spans = segment_spans(text, max_chars=len(SINHALA) + 5)
    assert [text[s:e] for s, e in spans] == [f"{SINHALA}."] * 3


# --- chunking ----------------------------------------------------------------

def test_small_paragraphs_are_packed_and_traceable():
    passages = [passage(i, f"Paragraph {i} about pandu.") for i in range(5)]

    chunks = chunk_passages("src-a", passages, settings(max_chars=80))

    assert len(chunks) > 1
    assert all(len(c.text) <= 80 for c in chunks)
    first = chunks[0]
    assert first.original_text.split("\n\n")[0] == passages[0].text
    assert [s.passage_index for s in first.passage_spans][0] == 0
    assert validate_chunks(chunks, passages, settings(max_chars=80)) == []


def test_overlap_repeats_whole_trailing_units():
    text = " ".join(f"Sentence number {i} ends here." for i in range(12))
    passages = [passage(0, text)]
    config = settings(max_chars=120, overlap=60)

    chunks = chunk_passages("src-a", passages, config)

    assert len(chunks) >= 3
    for previous, current in zip(chunks, chunks[1:]):
        # The new chunk starts with whole sentences that ended the previous
        # one, totalling no more than the overlap limit.
        first_sentence = current.text.split(". ", 1)[0] + "."
        assert first_sentence in previous.text
        shared = previous.text[previous.text.index(first_sentence):]
        assert current.text.startswith(shared)
        assert len(shared) <= 60
    assert validate_chunks(chunks, passages, config) == []


def test_no_overlap_when_disabled():
    text = " ".join(f"Sentence {i}." for i in range(40))
    chunks = chunk_passages("src-a", [passage(0, text)], settings(100, 0))
    words = [c.text.split()[1] for c in chunks]
    assert len(set(words)) == len(words)


def test_headings_start_chunks_and_keep_sections():
    passages = [
        passage(0, "# Pandu", PassageKind.HEADING, section_heading="Pandu"),
        passage(1, "Body about pandu.", section_heading="Pandu"),
        passage(2, "# Kamala", PassageKind.HEADING, section_heading="Kamala"),
        passage(3, "## Lakshana", PassageKind.HEADING, section_heading="Lakshana"),
        passage(4, "Body about kamala.", section_heading="Lakshana"),
    ]

    chunks = chunk_passages("src-a", passages, settings(max_chars=500))

    assert [c.text for c in chunks] == [
        "# Pandu\n\nBody about pandu.",
        "# Kamala\n\n## Lakshana\n\nBody about kamala.",
    ]
    assert [c.section_heading for c in chunks] == ["Pandu", "Kamala"]


def test_epub_documents_are_not_merged():
    passages = [
        passage(0, "End of chapter one.", item_id="ch1"),
        passage(1, "Start of chapter two.", item_id="ch2"),
    ]
    chunks = chunk_passages("src-a", passages, settings(max_chars=500))
    assert [c.item_id for c in chunks] == ["ch1", "ch2"]


def test_chunks_span_pdf_pages_with_page_range():
    passages = [
        passage(0, "The verse begins on one page and", PassageKind.PAGE, page=4),
        passage(1, "continues on the next page.", PassageKind.PAGE, page=5),
    ]
    chunks = chunk_passages("src-a", passages, settings(max_chars=500))
    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (4, 5)


def test_verses_stay_whole_with_metadata():
    page = f"{VERSE_7}\nPitta aggravated by these causes reaches rakta.\n\n{VERSE_9}"
    passages = [passage(0, page, PassageKind.PAGE, page=87)]
    metadata = SourceMetadata(source_language="sa", translation_language="en")

    chunks = chunk_passages("src-c", passages, settings(160, 0), metadata)

    joined = [c.original_text for c in chunks]
    assert any(VERSE_7 in text for text in joined)
    assert any(VERSE_9 in text for text in joined)
    assert [c.verse_numbers for c in chunks] == [["7"], ["9"]]
    assert all(c.page_start == 87 for c in chunks)
    assert chunks[0].declared_source_language == "sa"
    assert chunks[0].declared_translation_language == "en"
    assert chunks[0].primary_script == "mixed"


def test_line_numbers_follow_offsets_for_text_files():
    text = "line one\nline two\nline three"
    passages = [passage(0, text, line_start=10, line_end=12)]
    chunks = chunk_passages("src-a", passages, settings(max_chars=500))
    assert (chunks[0].line_start, chunks[0].line_end) == (10, 12)


def test_chunk_ids_are_stable_and_local():
    passages = [passage(i, f"Paragraph {i}. " * 6) for i in range(6)]
    config = settings(max_chars=120, overlap=0)
    first = chunk_passages("src-a", passages, config)
    again = chunk_passages("src-a", passages, config)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in again]
    assert all(c.chunk_id.startswith("src-a#chk-") for c in first)

    other_source = chunk_passages("src-b", passages, config)
    assert not {c.chunk_id for c in first} & {c.chunk_id for c in other_source}

    edited = list(passages)
    edited[0] = passage(0, "Corrected first paragraph.")
    changed = chunk_passages("src-a", edited, config)
    unchanged_ids = {c.chunk_id for c in first if c.passage_spans[0].passage_index >= 2}
    assert unchanged_ids <= {c.chunk_id for c in changed}
    assert first[0].chunk_id not in {c.chunk_id for c in changed}


def test_passage_flags_propagate_and_private_use_is_removed():
    flagged = ExtractedPassage(
        passage_index=0,
        kind=PassageKind.PAGE,
        text=f"Text with icon {chr(0xE934)} glyph.",
        location=SourceLocation(page=1),
        quality_flags=["short_page_text"],
    )
    chunk = chunk_passages("src-a", [flagged], settings())[0]
    assert chunk.text == "Text with icon glyph."
    assert chunk.quality_flags == ["short_page_text", PRIVATE_USE_REMOVED_FLAG]


def test_oversize_unit_is_flagged():
    text = chr(0xFB01) * 60  # every ligature expands to two characters
    config = settings(max_chars=60, overlap=0)
    chunks = chunk_passages("src-a", [passage(0, text)], config)
    assert chunks[0].quality_flags == [EXCEEDS_MAX_FLAG]
    assert validate_chunks(chunks, [passage(0, text)], config) == []


def test_empty_input_gives_no_chunks():
    assert chunk_passages("src-a", [], settings()) == []


def test_settings_reject_bad_overlap():
    with pytest.raises(ValueError):
        IngestionSettings(chunk_max_chars=100, chunk_overlap_chars=100)
    with pytest.raises(ValueError):
        IngestionSettings(chunk_max_chars=10)


# --- validation --------------------------------------------------------------

def test_validation_detects_tampering_and_gaps():
    passages = [passage(0, f"{ENGLISH} {DEVANAGARI}"), passage(1, "Second.")]
    config = settings()
    chunks = chunk_passages("src-a", passages, config)
    assert validate_chunks(chunks, passages, config) == []

    tampered = chunks[0].model_copy(update={"text": "changed"})
    problems = validate_chunks([tampered], passages, config)
    assert any("not the normalized original" in p for p in problems)
    assert any("content_sha256" in p for p in problems)

    duplicate = validate_chunks([chunks[0], chunks[0]], passages, config)
    assert any("duplicate chunk_id" in p for p in duplicate)

    missing = validate_chunks([], passages, config)
    assert len([p for p in missing if "not covered" in p]) == 2


# --- service and CLI ---------------------------------------------------------

def test_cli_chunk_and_validate_round_trip(tmp_path, capsys):
    book = tmp_path / "book.md"
    book.write_text(
        f"# Adhyaya\n\n{VERSE_7}\n\n{ENGLISH}\n\n{SINHALA}", encoding="utf-8"
    )
    out = tmp_path / "extracted"
    extraction = process_source(book)
    write_extraction(extraction, out)
    source_id = extraction.record.source_id

    assert main(["chunk", str(out)]) == 0
    path = chunks_path(out, source_id)
    first = path.read_text(encoding="utf-8")
    chunks = load_chunks(path)
    assert chunks and chunks[0].source_id == source_id
    assert SINHALA in first  # stored as UTF-8 text

    assert main(["chunk", str(out)]) == 0
    assert path.read_text(encoding="utf-8") == first  # idempotent

    assert main(["validate", str(out)]) == 0
    assert "0 with problems" in capsys.readouterr().out

    lines = first.splitlines()
    broken = json.loads(lines[0])
    broken["original_text"] = "tampered"
    path.write_text(
        "\n".join([json.dumps(broken, ensure_ascii=False), *lines[1:]]) + "\n",
        encoding="utf-8",
    )
    assert main(["validate", str(out)]) == 1


def test_cli_chunk_scanned_pdf_has_no_chunks(tmp_path, capsys):
    pdf = make_pdf(tmp_path / "text.pdf", ["A real text layer on page one."])
    out = tmp_path / "extracted"
    write_extraction(process_source(pdf), out)

    assert main(["chunk", str(out), "--verbose"]) == 0
    output = capsys.readouterr().out
    assert "chunks=1" in output
    assert main(["validate", str(out)]) == 0


def test_cli_chunk_missing_path(tmp_path):
    assert main(["chunk", str(tmp_path / "absent")]) == 2


def test_symbol_noise_and_repetitive_flags():
    from app.knowledge_ingestion.normalization import (
        REPETITIVE_TEXT_FLAG,
        SYMBOL_NOISE_FLAG,
    )

    legacy_font = " ".join(["f^fcbfrHd", "<*j|ae", "Mi^ft", "q^Tf&T"] * 6)
    assert SYMBOL_NOISE_FLAG in normalize_text(legacy_font).flags

    # Mixed verse debris with a real translation stays unflagged.
    mixed = "^I^IM^H^K : " + " ".join(["The patient should take light food."] * 4)
    assert SYMBOL_NOISE_FLAG not in normalize_text(mixed).flags
    cited = " ".join(["Ayurveda[12] is described in texts[3]."] * 6)
    assert SYMBOL_NOISE_FLAG not in normalize_text(cited).flags

    assert REPETITIVE_TEXT_FLAG in normalize_text("TTA TTAA " * 20).flags
    assert REPETITIVE_TEXT_FLAG not in normalize_text(
        " ".join(f"word{i}" for i in range(40))
    ).flags
