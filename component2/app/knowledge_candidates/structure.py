"""Sentence-structure check: is a relation stated, or are terms only listed?

Indication lists and drug-group catalogues put many concepts and cue words
into one sentence ('Dipana, kapha vata hara, sopha, ..., pandu'). Two
concepts appearing in such a sentence, with a cue word somewhere near
them, does not mean the sentence relates them.

The sentence is split into list items at commas and semicolons that are
not inside parentheses or brackets. A relation is treated as stated only
when:

* the sentence is a single clause (no list items), or
* the cue, subject and object are in the same list item, or
* the cue is in the subject's item and governs the items that follow or
  precede it ('Triphala was composed of A, B and C').

Anything else is "list co-occurrence": the candidate is still produced so
a reviewer sees it, but it is flagged as not supported by the sentence and
cannot be approved or promoted. This is a conservative heuristic. A real
relation phrased with the cue next to the object only ('Useful in pandu:
triphala, punarnava') is also flagged, not dropped.
"""

from dataclasses import dataclass

SINGLE_CLAUSE = "single_clause"
SAME_LIST_ITEM = "same_list_item"
CUE_GOVERNS_ENUMERATION = "cue_governs_enumeration"

_OPEN = "([{"
_CLOSE = ")]}"


@dataclass(frozen=True)
class StructureAssessment:
    supported: bool
    basis: str | None
    items: int


def list_item_spans(sentence: str) -> list[tuple[int, int]]:
    """Spans of top-level list items, split at ',' and ';' outside brackets."""
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for index, char in enumerate(sentence):
        if char in _OPEN:
            depth += 1
        elif char in _CLOSE and depth:
            depth -= 1
        elif char in ",;" and depth == 0:
            spans.append((start, index))
            start = index + 1
    spans.append((start, len(sentence)))
    return [span for span in spans if sentence[span[0]:span[1]].strip()]


def _item_of(spans: list[tuple[int, int]], position: int) -> int:
    for index, (start, end) in enumerate(spans):
        if start <= position < end:
            return index
    return len(spans) - 1


def assess(
    sentence: str,
    subject_span: tuple[int, int],
    object_span: tuple[int, int],
    cue_span: tuple[int, int],
) -> StructureAssessment:
    """Decide whether the sentence states the relation (sentence offsets)."""
    spans = list_item_spans(sentence)
    if len(spans) <= 1:
        return StructureAssessment(True, SINGLE_CLAUSE, len(spans))
    subject_item = _item_of(spans, subject_span[0])
    object_item = _item_of(spans, object_span[0])
    cue_item = _item_of(spans, cue_span[0])
    if subject_item == object_item == cue_item:
        return StructureAssessment(True, SAME_LIST_ITEM, len(spans))
    if cue_item == subject_item:
        return StructureAssessment(True, CUE_GOVERNS_ENUMERATION, len(spans))
    return StructureAssessment(False, None, len(spans))
