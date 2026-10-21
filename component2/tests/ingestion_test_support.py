"""Synthetic document builders for ingestion tests (not collected as tests).

All files are generated in temporary directories. No real books are used.
"""

import zipfile
from pathlib import Path


ZWJ = chr(0x200D)
ZWNJ = chr(0x200C)
NBSP = chr(0x00A0)

# Short synthetic phrases in each script. "ශ්‍රී" needs a ZWJ to render as
# the conjunct form, so it checks that invisible joiners survive.
SINHALA = "ශ්" + ZWJ + "රී ලංකාවේ ආයුර්වේද ග්‍රන්ථ"
DEVANAGARI = "पाण्डुरोगः धातुक्षयः"
TRANSLITERATED = "pāṇḍuroga dhātukṣaya"
ENGLISH = "Pandu is described in classical texts."


def _pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )


def make_pdf(
    path: Path,
    pages: list[str | None],
    image_pages: set[int] = frozenset(),
) -> Path:
    """Write a minimal PDF. pages[i] is ASCII text or None for no text.

    image_pages holds 1-based page numbers that draw a 1x1 image, which is
    how a scanned page looks to the extractor.
    """
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
            b"stream\n\x80\nendstream"
        ),
    }
    kids = []
    next_id = 5
    for number, text in enumerate(pages, start=1):
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(f"{page_id} 0 R")

        commands = []
        if number in image_pages:
            commands.append("q 200 0 0 200 50 400 cm /Im1 Do Q")
        if text:
            commands.append("BT /F1 12 Tf 72 720 Td 14 TL")
            for line in text.split("\n"):
                commands.append(f"({_pdf_escape(line)}) Tj T*")
            commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )

        xobject = "/XObject << /Im1 4 0 R >>" if number in image_pages else ""
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> {xobject} >> "
            f"/Contents {content_id} 0 R >>"
        ).encode()

    objects[2] = (
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    ).encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n".encode() + objects[object_id]
        out += b"\nendobj\n"
    xref_at = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode()
    out += b"0000000000 65535 f \n"
    for object_id in range(1, size):
        out += f"{offsets[object_id]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    path.write_bytes(bytes(out))
    return path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_paragraph(text: str, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{props}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def docx_table(rows: list[list[str]]) -> str:
    body = "".join(
        "<w:tr>"
        + "".join(f"<w:tc>{docx_paragraph(cell)}</w:tc>" for cell in row)
        + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{body}</w:tbl>"


def make_docx(path: Path, body_xml: str, title: str | None = None) -> Path:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{body_xml}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"/>',
        )
        archive.writestr("word/document.xml", document.encode("utf-8"))
        if title:
            archive.writestr(
                "docProps/core.xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
                'package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f"<dc:title>{title}</dc:title></cp:coreProperties>",
            )
    return path


def make_epub(
    path: Path,
    chapters: list[tuple[str, str]],
    title: str = "Synthetic EPUB",
    language: str = "sa",
    include_container: bool = True,
) -> Path:
    """chapters: list of (item_id, body_html)."""
    manifest = "".join(
        f'<item id="{item_id}" href="text/{item_id}.xhtml" '
        'media-type="application/xhtml+xml"/>'
        for item_id, _ in chapters
    )
    spine = "".join(f'<itemref idref="{item_id}"/>' for item_id, _ in chapters)
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{title}</dc:title><dc:language>{language}</dc:language>"
        "</metadata>"
        f"<manifest>{manifest}"
        '<item id="css" href="style.css" media-type="text/css"/></manifest>'
        f"<spine>{spine}</spine></package>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        if include_container:
            archive.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?>'
                '<container version="1.0" xmlns="urn:oasis:names:tc:'
                'opendocument:xmlns:container"><rootfiles>'
                '<rootfile full-path="OEBPS/content.opf" '
                'media-type="application/oebps-package+xml"/>'
                "</rootfiles></container>",
            )
        archive.writestr("OEBPS/content.opf", opf.encode("utf-8"))
        archive.writestr("OEBPS/style.css", "p { color: black; }")
        for item_id, body in chapters:
            archive.writestr(
                f"OEBPS/text/{item_id}.xhtml",
                (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                    "<title>ignored head title</title>"
                    "<style>p { margin: 0 }</style></head>"
                    f"<body>{body}</body></html>"
                ).encode("utf-8"),
            )
    return path


def make_tei(path: Path, body: str, availability: str = "CC BY-SA 3.0 test licence") -> Path:
    """Write a minimal TEI P5 file whose <body> is the given markup.

    The markup is synthetic and imitates the SARIT layout: <div> per
    sthana and adhyaya, <head>, <lg>/<l> verses with xml:id references,
    <label> elements repeating those references, editorial <note>s and
    <pb n> printed page breaks.
    """
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        "  <teiHeader><fileDesc>\n"
        "    <titleStmt><title>Synthetic Samhita</title></titleStmt>\n"
        "    <publicationStmt><publisher>Test fixture</publisher>\n"
        f"      <availability><p>{availability}</p></availability>\n"
        "    </publicationStmt>\n"
        "    <sourceDesc><p>Synthetic, no real edition.</p></sourceDesc>\n"
        "  </fileDesc></teiHeader>\n"
        f"  <text><body>{body}</body></text>\n"
        "</TEI>\n",
        encoding="utf-8",
    )
    return path


# Two adhyayas of a synthetic text. Verse wording is invented: it only
# reuses lexicon terms so candidate extraction can be exercised.
SYNTHETIC_TEI_BODY = """
<div n="6"><head>cikitsāsthānam</head>
  <div n="16"><head>pāṇḍurogacikitsitam</head>
    <pb n="512"/>
    <lg>
      <l xml:id="Syn.6.16.1"><label>Syn.6.16.1 </label>pāṇḍuroge
        lakṣaṇāni vakṣyāmi/</l>
      <l>tvak pāṇḍutā ca dṛśyate// <note type="variants">pāṇḍuratā iti pā-</note></l>
    </lg>
    <p xml:id="Syn.6.16.2"><label>Syn.6.16.2 </label>Pallor is a symptom of pandu.<ref rend="superscript footnote marker">†</ref></p>
    <pb n="513"/>
    <ab xml:id="Syn.6.16.3"><label>Syn.6.16.3</label> triphalā<lb/>punarnavā ca</ab>
  </div>
  <div n="17"><head>hikkāśvāsacikitsitam</head>
    <lg><l xml:id="Syn.6.17.1">śvāsa iti/</l></lg>
  </div>
</div>
"""


def make_jats(path: Path) -> Path:
    """Write a minimal synthetic JATS article (no real publication)."""
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="review-article">\n'
        "<front><journal-meta><journal-title-group><journal-title>Synthetic Journal"
        "</journal-title></journal-title-group></journal-meta>\n"
        "<article-meta><article-id pub-id-type=\"doi\">10.0000/synthetic.1</article-id>"
        "<article-id pub-id-type=\"pmcid\">PMC0000001</article-id>"
        "<title-group><article-title>Synthetic review of pandu</article-title></title-group>"
        "<pub-date><year>2025</year></pub-date>"
        '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">'
        "<license-p>This is an open access article (synthetic).</license-p></license></permissions>"
        "<abstract><p>Pallor is described in <italic>pandu</italic> [1].</p></abstract>"
        "</article-meta></front>\n"
        '<body><sec id="s1"><title>Introduction</title><p id="p1">Pandu is discussed.'
        "<list><list-item><p>first point</p></list-item></list></p>"
        '<sec id="s1a"><title>Background</title><p>Nested text.</p></sec></sec>'
        '<sec id="s2"><title>Results</title>'
        '<table-wrap id="t1"><caption><p>Table 1. Synthetic values</p></caption>'
        "<table><tr><th>Group</th><th>Hb</th></tr><tr><td>A</td><td>10.1</td></tr></table></table-wrap>"
        "</sec></body>\n"
        "<back><ref-list><ref><mixed-citation>Ref text</mixed-citation></ref></ref-list></back>\n"
        "</article>\n",
        encoding="utf-8",
    )
    return path
