"""AyurAI Component 1: patient-specific A4 PDF screening report (reportlab).

Content comes only from the existing screening report (component1.api.server._build_report) and the session's own
files; nothing is recalculated and no measurement is invented. Missing values are printed as "Not recorded".
The reliability score is always labelled as a heuristic, never as a probability or calibrated confidence.
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

DISCLAIMER = ("Research prototype. Experimental screening output only. Not a medical diagnosis. "
              "Clinical interpretation and laboratory confirmation are required.")
GREEN = colors.HexColor("#047857")
GREEN_DARK = colors.HexColor("#065F46")
GREEN_LIGHT = colors.HexColor("#ECFDF5")
GREEN_LINE = colors.HexColor("#A7F3D0")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
RULE = colors.HexColor("#E2E8F0")
AMBER_BG, AMBER_LINE = colors.HexColor("#FFFBEB"), colors.HexColor("#F59E0B")
RED_BG, RED_LINE, RED_INK = colors.HexColor("#FEF2F2"), colors.HexColor("#DC2626"), colors.HexColor("#991B1B")
NOT_RECORDED = "Not recorded"
TIER_LABELS = {"low": "Low", "moderate": "Moderate", "high": "High", "insufficient_evidence": "Insufficient evidence"}
REGION_LABELS = {"conjunctiva": "Conjunctiva", "nails": "Nail beds", "tongue": "Tongue"}
SOURCE_LABELS = {**REGION_LABELS, "ppg": "PPG", "questionnaire": "Questionnaire"}
SECTION_LABELS = {
    "immediate_safety": "Immediate safety", "pregnancy_history": "Pregnancy", "core_screening": "Symptoms and history",
    "followup_symptoms": "Follow-up questions", "child_history": "Child history", "ppg_acquisition": "Finger-comfort check",
}
PAGE_W, PAGE_H = A4
MARGIN = 16 * mm

# ---------------------------------------------------------------- fonts

_FONT_CANDIDATES = [  # (regular, bold); first pair found is used for all text
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
_SCRIPT_FONTS = [  # extra fonts tried for names in other scripts (e.g. Sinhala, Tamil)
    ("/usr/share/fonts/truetype/noto/NotoSansSinhala-Regular.ttf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf", 0),
    ("C:/Windows/Fonts/Nirmala.ttc", 0),
]
_fonts: dict[str, str] = {}


def _register_fonts() -> tuple[str, str]:
    if not _fonts:
        _fonts.update(regular="Helvetica", bold="Helvetica-Bold")
        override = os.environ.get("C1_PDF_FONT_DIR")
        candidates = ([(f"{override}/DejaVuSans.ttf", f"{override}/DejaVuSans-Bold.ttf")] if override else []) + _FONT_CANDIDATES
        for regular, bold in candidates:
            if Path(regular).is_file() and Path(bold).is_file():
                pdfmetrics.registerFont(TTFont("C1Sans", regular))
                pdfmetrics.registerFont(TTFont("C1Sans-Bold", bold))
                _fonts.update(regular="C1Sans", bold="C1Sans-Bold")
                break
    return _fonts["regular"], _fonts["bold"]


def _covers(font_name: str, text: str) -> bool:
    font = pdfmetrics.getFont(font_name)
    glyphs = getattr(getattr(font, "face", None), "charToGlyph", None)
    if glyphs is None:  # Built-in Type 1 fonts: Latin-1 only
        return all(ord(ch) < 256 for ch in text)
    return all(ord(ch) in glyphs or ch.isspace() for ch in text)


def _font_for(text: str) -> str:
    regular, _ = _register_fonts()
    if _covers(regular, text):
        return regular
    for index, (path, sub) in enumerate(_SCRIPT_FONTS):
        name = f"C1Script{index}"
        if Path(path).is_file():
            if name not in pdfmetrics.getRegisteredFontNames():
                try:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub))
                except Exception:  # noqa: BLE001 - an unusable system font is simply skipped
                    continue
            if _covers(name, text):
                return name
    return regular


# ---------------------------------------------------------------- styles and helpers


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()
    base = dict(fontName=regular, textColor=INK, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", fontName=bold, fontSize=17, leading=21, textColor=GREEN_DARK),
        "subtitle": ParagraphStyle("subtitle", **base, fontSize=10.5, leading=14),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=11.5, leading=15, textColor=GREEN_DARK, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", **base, fontSize=9, leading=12),
        "small": ParagraphStyle("small", **{**base, "textColor": MUTED}, fontSize=7.8, leading=10),
        "cell": ParagraphStyle("cell", **base, fontSize=8.4, leading=10.6),
        "cell_bold": ParagraphStyle("cell_bold", fontName=bold, textColor=INK, fontSize=8.4, leading=10.6),
        "head": ParagraphStyle("head", fontName=bold, textColor=colors.white, fontSize=8.4, leading=10.6),
        "sub": ParagraphStyle("sub", fontName=bold, textColor=INK, fontSize=8.8, leading=11, spaceBefore=6, spaceAfter=1),
        "badge": ParagraphStyle("badge", fontName=bold, textColor=GREEN_DARK, fontSize=8.4, leading=11),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(NOT_RECORDED if text is None or text == "" else str(text)), style)


def _value(value: Any) -> str:
    if value is None or value == "" or value == []:
        return NOT_RECORDED
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return "; ".join(_value(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {_value(v)}" for k, v in value.items() if v not in (None, ""))
    return str(value).replace("_", " ")


def _table(rows: list[list[Any]], widths: list[float], s: dict, header: bool = True, zebra: bool = True) -> Table:
    data = []
    for r, row in enumerate(rows):
        style = s["head"] if header and r == 0 else s["cell"]
        data.append([cell if isinstance(cell, (Paragraph, Image, Table)) else _p(cell, style) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), GREEN))
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if r % 2 == (0 if header else 1):
                commands.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F8FAFC")))
    table.setStyle(TableStyle(commands))
    return table


def _key_values(pairs: Iterable[tuple[str, Any]], s: dict, width: float) -> Table:
    rows = [[_p(k, s["cell_bold"]), v if isinstance(v, Paragraph) else _p(_value(v) if not isinstance(v, str) else v, s["cell"])]
            for k, v in pairs]
    return _table(rows, [width * 0.34, width * 0.66], s, header=False)


def _box(flowables: list, s: dict, width: float, background=GREEN_LIGHT, line=GREEN_LINE) -> Table:
    box = Table([[flowables]], colWidths=[width])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background), ("BOX", (0, 0), (-1, -1), 0.8, line),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return box


def _bullets(items: Iterable[Any], s: dict) -> list[Paragraph]:
    items = [item for item in items if item not in (None, "")]
    if not items:
        return [_p(NOT_RECORDED, s["body"])]
    return [Paragraph("•&nbsp;&nbsp;" + escape(str(item)), s["body"]) for item in items]


def _age(months: Any) -> str:
    if not isinstance(months, int) or isinstance(months, bool):
        return NOT_RECORDED
    years, rest = divmod(months, 12)
    return f"{years} years" + (f" {rest} months" if rest else "") + f" ({months} months)"


def _when(iso: Any) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%d %b %Y %H:%M UTC")
    except ValueError:
        return NOT_RECORDED


def _tier(level: Any) -> str:
    return f"{TIER_LABELS.get(level, _value(level))} (experimental, not clinically validated)" if level else "No risk tier produced"


# ---------------------------------------------------------------- page frame


class _NumberedCanvas(canvas.Canvas):
    """Draws the header/footer with 'Page X of Y' once the total page count is known."""

    def __init__(self, *args, session_id: str = "", generated: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict] = []
        self._session_id, self._generated = session_id, generated

    def showPage(self):  # noqa: N802 - reportlab API
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._frame(total)
            super().showPage()
        super().save()

    def _frame(self, total: int) -> None:
        regular, bold = _register_fonts()
        self.setFillColor(GREEN)
        self.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, stroke=0, fill=1)
        self.setFillColor(colors.white)
        self.setFont(bold, 8.5)
        self.drawString(MARGIN, PAGE_H - 6 * mm, "AyurAI  ·  Component 1: Anaemia Screening Report")
        self.setFont(regular, 8)
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 6 * mm, f"Session {self._session_id}")
        self.setStrokeColor(GREEN_LINE)
        self.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        self.setFillColor(MUTED)
        self.setFont(regular, 7.3)
        self.drawString(MARGIN, 8 * mm, "Research prototype · Experimental screening output · Not a diagnosis · Clinician review required")
        self.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Generated {self._generated}  ·  Page {self._pageNumber} of {total}")


def _logo(s: dict) -> Table:
    _, bold = _register_fonts()
    mark = Table([[Paragraph("<font color='white'>A</font>", ParagraphStyle("mark", fontName=bold, fontSize=16, leading=18, alignment=1))]],
                 colWidths=[11 * mm], rowHeights=[11 * mm])
    mark.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("ROUNDEDCORNERS", [3, 3, 3, 3])]))
    title = [Paragraph("AyurAI", s["title"]), Paragraph("Component 1: Anaemia Screening Report", s["subtitle"])]
    logo = Table([[mark, title]], colWidths=[14 * mm, None], hAlign="LEFT")
    logo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return logo


# ---------------------------------------------------------------- report


def build_pdf(
    report: dict,
    *,
    patient: dict | None,
    include_contact: bool,
    generated_at: datetime,
    quality_images: list[dict] | None = None,
    ppg_duration_s: float | None = None,
    thumbnails: list[tuple[str, Path]] | None = None,
    compress: bool = True,
) -> bytes:
    """Render the screening report. patient: {full_name, phone_display} or None for a coded session."""
    s = _styles()
    width = PAGE_W - 2 * MARGIN
    session_id = report.get("session_id", "")
    referral = report.get("outcome") == "safety_referral"
    result = report.get("screening_result", {})
    fusion = report.get("fusion") or {}
    modalities = report.get("modalities", {})
    profile = report.get("patient", {})
    generated = generated_at.strftime("%d %b %Y %H:%M UTC")
    story: list = []

    # Header
    story += [_logo(s), Spacer(1, 4)]
    story.append(_box([Paragraph("RESEARCH PROTOTYPE · CLINICIAN REVIEW REQUIRED", s["badge"]),
                       _p("Experimental screening evidence for a qualified clinician. Not a diagnosis.", s["small"])], s, width))
    story.append(Spacer(1, 6))
    story.append(_key_values([
        ("Session ID", session_id),
        ("Report generated", generated),
        ("Screening record saved", _when((report.get("storage") or {}).get("record_saved_utc"))),
        ("Outcome", "Safety referral (routine screening stopped)" if referral else "Screening"),
    ], s, width))
    if report.get("analysis_outdated"):
        story += [Spacer(1, 6), _box([Paragraph("<b>Images changed after this analysis.</b> The results below are outdated: "
                                                "re-run the analysis before relying on them.", s["body"])], s, width, RED_BG, RED_LINE)]

    # B. Patient information
    story.append(Paragraph("Patient information", s["h2"]))
    name = (patient or {}).get("full_name")
    pregnancy = profile.get("pregnancy_status")
    story.append(_key_values([
        ("Patient name", Paragraph(escape(name), ParagraphStyle("name", parent=s["cell"], fontName=_font_for(name))) if name
         else "Not registered (coded session; no name stored)"),
        ("Contact number", ((patient or {}).get("phone_display") or NOT_RECORDED) if include_contact else "Withheld (not authorised)"),
        ("Age", _age(profile.get("age_months"))),
        ("Sex (as recorded)", _value(profile.get("sex"))),
        ("Pregnancy status", _value(pregnancy) if pregnancy not in (None, "not_applicable") else "Not applicable / not recorded"),
    ], s, width))

    # G. Safety status (shown early: it changes how everything else is read)
    story.append(Paragraph("Safety status", s["h2"]))
    if referral:
        ref = report.get("referral", {})
        story.append(_box([
            Paragraph("<b>SAFETY REFERRAL: immediate clinician assessment required.</b>", ParagraphStyle("r", parent=s["body"], textColor=RED_INK)),
            _p(ref.get("reason"), s["body"]),
            _p("Further screening was blocked: no images, PPG, models or fusion were used and no anaemia-risk tier was produced.", s["body"]),
            _p(f"Urgent answers: {_value(ref.get('urgent_response_ids'))} · Unresolved: {_value(ref.get('unresolved_safety_ids'))} · "
               f"Not asked before referral: {_value(ref.get('not_asked_safety_ids'))}", s["small"]),
        ], s, width, RED_BG, RED_LINE))
    else:
        flags = fusion.get("safety_flags") or []
        story.append(_box([_p("Normal screening pathway: no urgent or unresolved safety answer.", s["body"])]
                          + ([Paragraph("<b>Safety flags for review:</b>", s["body"])] + _bullets(flags, s) if flags else []),
                          s, width, AMBER_BG if flags else GREEN_LIGHT, AMBER_LINE if flags else GREEN_LINE))

    # C. Screening inputs
    story.append(Paragraph("Screening inputs", s["h2"]))
    answers = {r["question_id"]: r for r in report.get("questionnaire", {}).get("responses", [])}
    consent = lambda qid: _value(answers.get(qid, {}).get("answer"))  # noqa: E731
    story.append(_key_values([
        ("Consent to screening", consent("REG05")),
        ("Consent to webcam photographs", consent("REG07")),
        ("Consent to finger PPG", consent("REG06")),
    ], s, width))
    q_evidence = fusion.get("questionnaire_evidence") or {}
    story.append(Spacer(1, 5))
    story.append(_key_values([
        ("Reported symptoms (present)", _value([x.replace("_", " ") for x in q_evidence.get("present_symptoms", [])]) if q_evidence else NOT_RECORDED),
        ("Symptoms reported absent", _value([x.replace("_", " ") for x in q_evidence.get("absent_symptoms", [])]) if q_evidence else NOT_RECORDED),
        ("Current medicines / supplements", _value(answers.get("MED01", {}).get("answer")) if "MED01" in answers else consent("C15")),
        ("Ayurvedic / herbal products", _value(answers.get("MED02", {}).get("answer")) if "MED02" in answers else consent("C16")),
        ("Allergies", _value(answers.get("ALG01", {}).get("answer")) if "ALG01" in answers else consent("C17")),
    ], s, width))
    rows = [["Section", "Question", "Answer"]]
    for item in report.get("questionnaire", {}).get("responses", []):
        if item.get("section") == "registration" or item["question_id"] in ("MED01", "MED02", "ALG01"):
            continue
        rows.append([SECTION_LABELS.get(item.get("section"), _value(item.get("section"))), item.get("question"), _value(item.get("answer"))])
    story += [Spacer(1, 5), Paragraph("Questionnaire responses", s["cell_bold"]), Spacer(1, 2)]
    story.append(_table(rows, [width * 0.2, width * 0.55, width * 0.25], s) if len(rows) > 1 else _p(NOT_RECORDED, s["body"]))

    if not referral:
        # D. Image evidence
        story += [CondPageBreak(60 * mm), Paragraph("Image evidence", s["h2"])]
        images = modalities.get("images") or {}
        regions = images.get("regions") or {}
        rows = [["Region", "Captures", "Technical checks passed", "Model outputs (uncalibrated)", "Experimental Hb (g/dL)", "Models disagree"]]
        for key, label in REGION_LABELS.items():
            region = regions.get(key)
            if not region:
                rows.append([label, "0", "—", "Not captured", "—", "—"])
                continue
            votes = region.get("model_votes") or []
            vote_text = "; ".join(f"{v.get('source')}: {v.get('score_uncalibrated')}" for v in votes) or "None"
            hb = region.get("experimental_hb_estimates_g_dl") or []
            hb_text = "; ".join(f"{e.get('source')}: {e.get('estimate_g_dl')}" for e in hb) or "None"
            rows.append([label, region.get("captures", 0), f"{region.get('technical_passes', 0)} of {region.get('captures', 0)}",
                         vote_text, hb_text, "Yes" if region.get("cross_model_disagreement") else "No"])
        story.append(_table(rows, [width * w for w in (0.13, 0.1, 0.14, 0.3, 0.21, 0.12)], s))
        if quality_images:
            rows = [["Region", "Technical quality", "Flags"]] + [
                [REGION_LABELS.get(q.get("modality"), _value(q.get("modality"))), _value(q.get("status")), _value(q.get("flags")) if q.get("flags") else "None"]
                for q in quality_images]
            story += [Spacer(1, 5), Paragraph("Per-image technical quality", s["cell_bold"]), Spacer(1, 2),
                      _table(rows, [width * 0.2, width * 0.35, width * 0.45], s)]
        story.append(_p("Technical quality checks are resolution, brightness, blur, contrast and exposure only. Model outputs are "
                        "uncalibrated scores from public-dataset models and are not diagnoses.", s["small"]))
        if thumbnails:
            cells = [[Image(str(path), width=width / 3 - 8, height=(width / 3 - 8) * 0.62, kind="proportional"),
                      _p(label, s["small"])] for label, path in thumbnails[:6]]
            grid = [cells[i:i + 3] for i in range(0, len(cells), 3)]
            grid = [[Table([[c[0]], [c[1]]]) for c in row] + [""] * (3 - len(row)) for row in grid]
            story += [Spacer(1, 4), Table(grid, colWidths=[width / 3] * 3, hAlign="LEFT")]

        # E. PPG evidence
        story += [CondPageBreak(45 * mm), Paragraph("PPG evidence", s["h2"])]
        ppg = modalities.get("ppg") or {}
        if ppg.get("available"):
            windows = ppg.get("quality_windows_checked")
            story.append(_key_values([
                ("Sensor recording", f"Available (recording #{ppg.get('recording_id')})"),
                ("Recording duration", f"{ppg_duration_s:.1f} s" if ppg_duration_s is not None else NOT_RECORDED),
                ("RED/IR samples", ppg.get("sample_count")),
                ("Observed receive rate", f"{ppg.get('observed_receive_rate_hz')} Hz" if ppg.get("observed_receive_rate_hz") is not None else NOT_RECORDED),
                ("Signal quality", f"{_value(ppg.get('quality_status'))}; {ppg.get('quality_windows_passed', 0)} of {windows} five-second windows passed"
                 if windows else _value(ppg.get("quality_status"))),
                ("Experimental heart rate (device)", f"{ppg['median_experimental_hr_bpm']} bpm (median)" if ppg.get("median_experimental_hr_bpm") is not None else NOT_RECORDED),
                ("Experimental SpO2 (device)", f"{ppg['median_experimental_spo2_percent']}% (median)" if ppg.get("median_experimental_spo2_percent") is not None else NOT_RECORDED),
                ("Hb from PPG", "Not applied (live PPG Hb transfer is not validated)"),
            ], s, width))
        else:
            story.append(_p("No PPG recording was used (not consented, not cleared by the finger-comfort check, or not recorded).", s["body"]))
        story.append(_p("Heart rate and SpO2 are experimental device estimates. HR and SpO2 alone are not validated anaemia evidence.", s["small"]))

    # F. Screening result
    story += [CondPageBreak(55 * mm), Paragraph("Screening result", s["h2"])]
    if referral:
        story.append(_p("No risk tier: this is a safety-referral-only record.", s["body"]))
    else:
        reliability = fusion.get("reliability_aware_fusion") or {}
        conventional = fusion.get("conventional_fusion") or {}
        score = result.get("reliability_score")
        story.append(_key_values([
            ("Experimental risk tier", Paragraph(f"<b>{escape(_tier(result.get('risk_level')))}</b>", s["cell"])),
            ("Reliability score", f"{score} (heuristic from image quality and held-out model performance; not a probability or calibrated confidence)"
             if score is not None else NOT_RECORDED),
            ("Decision status", _value(result.get("decision_status"))),
            ("Weighted evidence score", _value(reliability.get("weighted_evidence_score"))),
            ("Evidence conflict ratio", _value(reliability.get("conflict_ratio"))),
            ("Hb cut-off applied", _value(fusion.get("hb_threshold_basis"))),
            ("Conventional equal-vote baseline", f"{TIER_LABELS.get(conventional.get('tier'), _value(conventional.get('tier')))} (comparison only)"
             if conventional else NOT_RECORDED),
        ], s, width))
        rows = [["Evidence source", "Evidence", "Weight", "Basis"]]
        for item in fusion.get("evidence_items") or []:
            used = (item.get("reliability_weight") or 0) > 0 and item.get("evidence") is not None
            rows.append([f"{SOURCE_LABELS.get(item.get('modality'), _value(item.get('modality')))} · {item.get('source')}",
                         _value(item.get("evidence")), f"{item.get('reliability_weight')}" + ("" if used else " (excluded)"),
                         _value(item.get("weight_basis"))])
        if len(rows) > 1:
            story += [Spacer(1, 5), Paragraph("Contributing and excluded evidence", s["cell_bold"]), Spacer(1, 2),
                      _table(rows, [width * 0.27, width * 0.12, width * 0.15, width * 0.46], s)]
        disagree = [REGION_LABELS.get(k, k) for k, v in ((modalities.get("images") or {}).get("regions") or {}).items() if v.get("cross_model_disagreement")]
        story += [Spacer(1, 5), Paragraph("Rationale", s["sub"])] + _bullets(fusion.get("rationale") or [], s)
        story += [Paragraph("Missing inputs", s["sub"])] + _bullets(report.get("missing_inputs") or ["None"], s)
        story += [Paragraph("Conflicting model predictions", s["sub"])] + _bullets(
            [f"{region}: the image models disagree" for region in disagree] or ["None detected"], s)
        story += [Paragraph("Limitations", s["sub"])] + _bullets((report.get("doctor_report") or {}).get("limitations") or [], s)
    recommendations = list((report.get("doctor_report") or {}).get("recommendations") or [])
    lab = "Confirm with laboratory haemoglobin / complete blood count (CBC) before any clinical decision."
    if not any("laboratory" in str(r).lower() for r in recommendations):
        recommendations.append(lab)
    story += [Paragraph("Recommendations", s["sub"])] + _bullets(recommendations, s)

    # H. Doctor review
    review = Table([
        [_p("Review status", s["cell_bold"]), _p("Pending review: no practitioner decision has been recorded.", s["cell"])],
        [_p("Practitioner name", s["cell_bold"]), ""],
        [_p("Review date", s["cell_bold"]), ""],
        [_p("Decision", s["cell_bold"]), Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;".join(f"[&nbsp;&nbsp;&nbsp;]&nbsp;{label}" for label in ("Approve", "Request further assessment", "Reject")), s["cell"])],
        [_p("Doctor's notes", s["cell_bold"]), ""],
    ], colWidths=[width * 0.25, width * 0.75], rowHeights=[None, 9 * mm, 9 * mm, None, 32 * mm])
    review.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, GREEN_LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BACKGROUND", (0, 0), (0, -1), GREEN_LIGHT)]))
    story.append(KeepTogether([Paragraph("Doctor review", s["h2"]), review,
                               _p("Decisions are recorded in the AyurAI practitioner workflow (Component 4). This printed form is "
                                  "not a record of approval.", s["small"])]))

    # I. Disclaimer
    story.append(Spacer(1, 8))
    story.append(_box([Paragraph("<b>Disclaimer.</b> " + escape(DISCLAIMER), s["body"])], s, width, AMBER_BG, AMBER_LINE))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm, bottomMargin=17 * mm,
                            title=f"AyurAI Component 1 screening report {session_id}", author="AyurAI Component 1",
                            subject="Experimental anaemia screening report (research prototype)", pageCompression=1 if compress else 0)
    doc.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, session_id=session_id, generated=generated, **k))
    return buffer.getvalue()
