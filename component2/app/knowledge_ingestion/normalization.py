"""Unicode-safe normalization and script profiling for source text.

normalize_text() always returns a new, derived string; the extracted
original is stored alongside it and is never modified. Normalization is
deliberately conservative:

* Unicode NFC (not NFKC, which would also rewrite compatibility characters
  that can carry meaning).
* Latin typographic ligatures (U+FB00-FB06) are expanded, because PDF text
  layers often contain them and they break word matching.
* Soft hyphens, stray control characters, byte-order marks and private-use
  code points (icon fonts, unmapped PDF glyphs) are removed.
* Space separators become a plain space and runs of spaces collapse; line
  breaks are kept, because verse lines and half-verses are meaningful.

ZWJ and ZWNJ are never removed: they change how Sinhala and Devanagari
conjuncts render. No transliteration, translation or spelling correction is
performed. Language is not detected; only scripts are profiled, from
Unicode code-point ranges.
"""

import re
import unicodedata
from dataclasses import dataclass, field


NORMALIZATION_VERSION = "1"

ZWNJ = chr(0x200C)
ZWJ = chr(0x200D)
SOFT_HYPHEN = chr(0x00AD)
BOM = chr(0xFEFF)

_LIGATURES = {
    chr(0xFB00): "ff",
    chr(0xFB01): "fi",
    chr(0xFB02): "fl",
    chr(0xFB03): "ffi",
    chr(0xFB04): "ffl",
    chr(0xFB05): "st",
    chr(0xFB06): "st",
}

# Spacing accents that PDF text layers emit next to a base letter instead
# of a combined character, e.g. "Pe" + U+02DC + "na" for "Peña".
_DETACHED_ACCENTS = {
    chr(0x02DC), chr(0x00B4), chr(0x00A8), chr(0x02C6), chr(0x02D8),
    chr(0x02D9), chr(0x02DA), chr(0x02DD), chr(0x00B8),
}

# Letters specific to IAST (and ISO 15919) romanization of Sanskrit.
IAST_LETTERS = frozenset(
    "āīūṛṝḷḹṃṁḥṅñṭḍṇśṣĀĪŪṚṜḶḸṂṀḤṄÑṬḌṆŚṢ"
)

LETTER_SPACED_FLAG = "letter_spaced"
SYMBOL_NOISE_FLAG = "symbol_noise"
REPETITIVE_TEXT_FLAG = "repetitive_text"
DETACHED_DIACRITICS_FLAG = "detached_diacritics"
PRIVATE_USE_REMOVED_FLAG = "private_use_removed"

_SPACES = re.compile(r"[ ]{2,}")
_MANY_NEWLINES = re.compile(r"\n{3,}")


@dataclass
class NormalizedText:
    text: str
    flags: list[str] = field(default_factory=list)


def normalize_text(original: str) -> NormalizedText:
    """Return a normalized copy of original plus quality flags."""
    text = unicodedata.normalize("NFC", original)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out: list[str] = []
    removed_private_use = False
    for char in text:
        if char in _LIGATURES:
            out.append(_LIGATURES[char])
            continue
        if char in (ZWJ, ZWNJ, "\n"):
            out.append(char)
            continue
        if char in (SOFT_HYPHEN, BOM):
            continue
        category = unicodedata.category(char)
        if category == "Co":
            removed_private_use = True
            continue
        if category == "Cc":
            # Tabs become spaces; other control characters are dropped.
            if char == "\t":
                out.append(" ")
            continue
        if category == "Zs" or category in ("Zl", "Zp"):
            out.append("\n" if category in ("Zl", "Zp") else " ")
            continue
        out.append(char)

    lines = [_SPACES.sub(" ", line).strip(" ") for line in "".join(out).split("\n")]
    normalized = _MANY_NEWLINES.sub("\n\n", "\n".join(lines)).strip("\n ")

    flags: list[str] = []
    if removed_private_use:
        flags.append(PRIVATE_USE_REMOVED_FLAG)
    if has_detached_diacritics(normalized):
        flags.append(DETACHED_DIACRITICS_FLAG)
    if is_letter_spaced(normalized):
        flags.append(LETTER_SPACED_FLAG)
    if has_symbol_noise(normalized):
        flags.append(SYMBOL_NOISE_FLAG)
    if is_repetitive(normalized):
        flags.append(REPETITIVE_TEXT_FLAG)
    return NormalizedText(normalized, flags)


def has_detached_diacritics(text: str) -> bool:
    for index, char in enumerate(text):
        if char not in _DETACHED_ACCENTS:
            continue
        before = text[index - 1] if index else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if before.isalpha() or after.isalpha():
            return True
    return False


def is_letter_spaced(text: str, min_tokens: int = 20) -> bool:
    """Detect text like 'y o g a  i s' produced by bad PDF/OCR conversion.

    Checked on Latin letters only: Sinhala and Devanagari tokens can
    legitimately be one code point long.
    """
    tokens = text.split()
    if len(tokens) < min_tokens:
        return False
    single = sum(
        1 for token in tokens
        if len(token) == 1 and token.isascii() and token.isalpha()
    )
    return single / len(tokens) >= 0.6


# Symbols that legacy (non-Unicode) Devanagari/Sinhala fonts turn into when
# their glyphs are read as ASCII, e.g. "f^fcbfrHd <*j|". Brackets are not
# included because "word[12]" citation markers are ordinary text.
_NOISE_SYMBOLS = frozenset("^<>|£■*#@{}~`=+_$§¬¦%")
_TOKEN_EDGE = "\"'()[]{}.,;:!?«»“”‘’*#"


def has_symbol_noise(
    text: str, threshold: float = 0.25, min_tokens: int = 20
) -> bool:
    """Detect text where many words have symbols embedded inside them.

    A word counts when, after trimming edge punctuation, it contains both a
    letter and one of the noise symbols. Calibrated on the AyurAI corpus:
    0.25 flags legacy-font extraction and markup debris; lower thresholds
    also flagged useful mixed verse-and-translation chunks.
    """
    tokens = text.split()
    if len(tokens) < min_tokens:
        return False
    noisy = 0
    for token in tokens:
        core = token.strip(_TOKEN_EDGE)
        if (
            len(core) >= 2
            and any(char.isalpha() for char in core)
            and any(char in _NOISE_SYMBOLS for char in core)
        ):
            noisy += 1
    return noisy / len(tokens) > threshold


def is_repetitive(
    text: str, min_tokens: int = 30, max_distinct_share: float = 0.2
) -> bool:
    """Detect table/menu debris such as 'TTA TTA TTAA TTAA ...'."""
    tokens = text.split()
    if len(tokens) < min_tokens:
        return False
    return len(set(tokens)) / len(tokens) < max_distinct_share


# --- Script profiling --------------------------------------------------------

_SCRIPT_RANGES = (
    ("Deva", 0x0900, 0x097F),
    ("Deva", 0xA8E0, 0xA8FF),
    ("Deva", 0x1CD0, 0x1CFF),
    ("Sinh", 0x0D80, 0x0DFF),
    ("Sinh", 0x111E0, 0x111FF),
    ("Latn", 0x0041, 0x024F),
    ("Latn", 0x0300, 0x036F),
    ("Latn", 0x1E00, 0x1EFF),
    ("Latn", 0x2C60, 0x2C7F),
    ("Latn", 0xA720, 0xA7FF),
)


def _script_of(char: str) -> str | None:
    category = unicodedata.category(char)
    if not (category.startswith("L") or category.startswith("M")):
        return None
    code = ord(char)
    for script, low, high in _SCRIPT_RANGES:
        if low <= code <= high:
            return script
    return "Zyyy"


@dataclass(frozen=True)
class ScriptProfile:
    primary_script: str
    scripts: list[str]
    iast_present: bool


def profile_scripts(
    text: str,
    dominant_share: float = 0.8,
    minor_share: float = 0.05,
) -> ScriptProfile:
    """Summarize which scripts the letters of text are written in.

    primary_script is an ISO 15924 code when one script holds at least
    dominant_share of the letters, "mixed" otherwise, and "unknown" when
    there are fewer than three letters. "Zyyy" groups other scripts.
    """
    counts: dict[str, int] = {}
    iast = False
    for char in text:
        script = _script_of(char)
        if script is None:
            continue
        counts[script] = counts.get(script, 0) + 1
        if char in IAST_LETTERS:
            iast = True

    total = sum(counts.values())
    if total < 3:
        return ScriptProfile("unknown", [], iast)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    scripts = [script for script, count in ordered if count / total >= minor_share]
    top, top_count = ordered[0]
    primary = top if top_count / total >= dominant_share else "mixed"
    return ScriptProfile(primary, scripts, iast)


# --- Verse markers -----------------------------------------------------------

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_SINHALA_DIGITS = str.maketrans(
    "".join(chr(code) for code in range(0x0DE6, 0x0DF0)), "0123456789"
)
_VERSE_MARKER = re.compile(
    r"(?:॥|\|\|)\s*([०-९0-9]+(?:\s*[-–]\s*[०-९0-9]+)?)\s*(?:॥|\|\|)"
)


def find_verse_numbers(text: str) -> list[str]:
    """Return verse numbers from danda markers such as '॥ १२ ॥' or '|| 12 ||'.

    The numbers are reported as found (ASCII digits), in order, without
    duplicates. They are labels printed in the source, not verified
    references.
    """
    found: list[str] = []
    for match in _VERSE_MARKER.finditer(text):
        value = re.sub(r"\s+", "", match.group(1))
        value = value.translate(_DEVANAGARI_DIGITS).translate(_SINHALA_DIGITS)
        value = value.replace("–", "-")
        if value not in found:
            found.append(value)
    return found
