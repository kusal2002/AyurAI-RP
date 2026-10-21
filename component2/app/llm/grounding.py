"""Deterministic checks applied to LLM text: IDs, labels, unsafe phrasing.

These checks are heuristics for research scoring and for the explanation
guard. They do not judge clinical correctness.
"""

import json
import re

PROVISIONAL_LABEL = "Unverified — practitioner review pending"

# Graph identifiers: claim and evidence IDs (CL-…, EV-…, PCL-<hash>,
# PEV-<hash>) and concept IDs (R-PANDU, DO-PITTA, H-…).
ID_PATTERN = re.compile(r"\b[A-Z]{1,4}(?:-[A-Za-z0-9]+)+\b")
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")
_LABEL_PATTERN = re.compile(
    r"^\s*\[?\s*unverified\s*[—–-]+\s*practitioner review pending\s*\]?\s*[:.]?\s*",
    re.IGNORECASE,
)
_LABEL_ANYWHERE = re.compile(
    r"unverified\s*[—–-]+\s*practitioner review pending", re.IGNORECASE
)

# Phrases that would turn decision support into a medical conclusion,
# prescription or efficacy promise.
UNSAFE_PATTERNS = {
    "diagnosis": re.compile(
        r"\b(you have|you are suffering|diagnos(?:is|ed|e) (?:is|of|with|you))\b",
        re.IGNORECASE,
    ),
    "prescription": re.compile(r"\b(prescri(?:be|bed|ption)|you should take)\b", re.IGNORECASE),
    "dosage": re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:mg|g|ml|grams?|tablets?|capsules?|times (?:a|per) day)\b",
        re.IGNORECASE,
    ),
    "efficacy_promise": re.compile(
        r"\b(will cure|cures|guaranteed|proven to (?:cure|treat))\b", re.IGNORECASE
    ),
}


def extract_ids(text: str) -> set[str]:
    return set(ID_PATTERN.findall(text or ""))


def unsafe_phrases(text: str) -> list[str]:
    return sorted(name for name, pattern in UNSAFE_PATTERNS.items() if pattern.search(text or ""))


def has_provisional_label(text: str) -> bool:
    return bool(_LABEL_ANYWHERE.search(text or ""))


def with_provisional_label(text: str) -> str:
    """Prefix the exact label once, replacing any variant already present."""
    return f"{PROVISIONAL_LABEL}: {_LABEL_PATTERN.sub('', text, count=1).strip()}"


def parse_json_object(text: str) -> dict | None:
    """Parse the first JSON object in a model answer (code fences allowed)."""
    if not text:
        return None
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except ValueError:
        pass
    start = cleaned.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
