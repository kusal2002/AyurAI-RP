"""Rule-based candidate extraction (no language model, no network).

For each sentence or verse of a chunk, the extractor finds lexicon
concepts and proposes a candidate only when two concepts of compatible
types appear together with a cue phrase for a candidate predicate (for
example 'indicated in', 'symptoms', 'लक्षण', 'contraindicated'). Plain
co-occurrence is recorded as a mention, never as a claim.

Negation and dosage wording are not interpreted: they are attached as
uncertainty notes so a reviewer reads the sentence. No confidence score is
produced, because these rules have no calibrated probability.

Extractors implement the CandidateExtractor protocol, so a different
extractor (for example a local model) can be added later behind the same
review workflow. None is called by default.
"""

import hashlib
import json
import re
from typing import Iterable, Protocol

from app.knowledge_candidates.lexicon import LexiconMatcher
from app.knowledge_candidates.structure import CUE_GOVERNS_ENUMERATION, assess
from app.knowledge_candidates.models import (
    AMBIGUOUS_TERM,
    CANDIDATE_PREDICATES,
    COMPOUND_MATCH,
    DOSAGE_STATEMENT,
    EVIDENCE_CATEGORY_UNKNOWN,
    LIST_CONTEXT,
    NEGATION_CUE,
    QUALIFIED_STATEMENT,
    SOURCE_QUALITY_FLAGGED,
    STRUCTURE_UNSUPPORTED,
    CandidateClaim,
    ChunkMentions,
    ConceptMention,
    SupportingPassage,
)
from app.knowledge_ingestion.chunking import sentence_spans
from app.knowledge_ingestion.models import EvidenceCategory, TextChunk


EXTRACTOR_NAME = "lexicon_cue_rules"
# v3: sentence-structure check for list co-occurrence.
# v4: bare dosha words are no longer a relation cue; period/proportion
#     qualifier note.
EXTRACTOR_VERSION = "4"
# Candidate IDs are computed with the v2 scheme so that re-extraction with
# v3 keeps existing candidate IDs, review history and decisions. Change this
# only when the identity of a candidate (chunk, sentence, triple) changes.
CLAIM_ID_SCHEME_VERSION = "2"
# Upper bound on candidates from one sentence, so a long list of herbs in
# one verse cannot flood the review queue.
MAX_CANDIDATES_PER_SENTENCE = 12
# The subject must lie within this many characters of the cue phrase, and
# so must the object unless the cue governs an enumeration that includes it
# ('Triphala was composed of A, B, and C'). Sentence structure, not distance,
# decides whether a nearby pair is a relation (see structure.py).
CUE_WINDOW_CHARS = 80
# Sentences with at least this many commas/semicolons read as lists; their
# candidates get a list_context note.
LIST_SEPARATORS = 5

_CUES = {
    "HAS_SYMPTOM": (
        r"\bsymptoms?\b|\bsigns?\b|\bcharacteri[sz]ed by\b|\bpresents? with\b"
        r"|\blak[sṣ]a[nṇ]a|\brūpa\b|लक्षण"
    ),
    "TRADITIONALLY_INDICATED_FOR": (
        r"\bindicated (?:in|for)\b|\buseful (?:in|for)\b|\bused (?:in|for)\b"
        r"|\bbeneficial (?:in|for)\b|\bcures?\b|\btreat(?:s|ment of|ing)?\b"
        r"|\bremed(?:y|ies) for\b|\bprescribed (?:in|for)\b|\bcurative\b"
        r"|\bhita\b|\bnā?[sś]ana\b|हित|नाशन|उपयोगी"
    ),
    "HAS_CAUTION": (
        r"\bcontra-?indicat|\bshould not be (?:used|given|taken)\b"
        r"|\bavoid(?:ed)?\b|\bnot (?:be )?(?:given|used) in\b|\bcaution\b"
        r"|\bni[sṣ]iddh|निषिद्ध|वर्ज्य"
    ),
    # Only causal or aggravation wording. The bare word 'dosha' is not a
    # cue: it also occurs inside disease names such as 'grahani dosha' and
    # in lists of actions ('kapha vata hara').
    "ASSOCIATED_WITH_DOSHA": (
        r"\bvitiat|\baggravat|\bpredominan|\bprakopa|\bdue to\b|\bcaused by\b"
        r"|प्रकोप"
    ),
    "AFFECTS_DHATU": (
        r"\bdeplet|\bk[sṣ]aya\b|\bvitiat|\baffect|\bdu[sṣ][tṭ]i\b|क्षय|दुष्टि"
    ),
    "CONTAINS_INGREDIENT": (
        r"\bcontains?\b|\bingredients?\b|\bcomposed of\b|\bconsist(?:s|ing)? of\b"
        r"|\bprepared (?:from|with)\b"
    ),
}
_CUE_PATTERNS = {
    predicate: re.compile(pattern, re.IGNORECASE)
    for predicate, pattern in _CUES.items()
}
_NEGATION = re.compile(
    r"\bnot\b|\bno\b|\bnever\b|\bwithout\b|\bnor\b|नहीं|(?<!\S)न(?!\S)",
    re.IGNORECASE,
)
_QUALIFIER = re.compile(
    r"\b(?:during|in) the (?:period|time|era|days) of\b|\bcentur(?:y|ies)\b"
    r"|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|half|\d+(?:\.\d+)?)"
    r"\s+parts?\s+of\b"
    r"|\bequal\s+(?:parts|quantities|proportions?)\b"
    r"|\bin\s+(?:the\s+)?(?:ratio|proportion)\b",
    re.IGNORECASE,
)
_DOSAGE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|g|gm|grams?|ml|tolas?|mashas?|rattis?|drops?)\b"
    r"|\bdos(?:e|age)\b|\bm[aā]tr[aā]\b|मात्रा",
    re.IGNORECASE,
)


class CandidateExtractor(Protocol):
    name: str
    version: str

    def extract(
        self,
        chunk: TextChunk,
        evidence_category: EvidenceCategory | None = None,
    ) -> tuple[ChunkMentions, list[CandidateClaim]]: ...


def make_claim_id(
    chunk_id: str,
    sentence_start: int,
    sentence_end: int,
    subject_id: str,
    predicate: str,
    object_id: str,
) -> str:
    payload = json.dumps(
        [EXTRACTOR_NAME, CLAIM_ID_SCHEME_VERSION, chunk_id, sentence_start,
         sentence_end, subject_id, predicate, object_id],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "cand-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


class LexiconCueExtractor:
    name = EXTRACTOR_NAME
    version = EXTRACTOR_VERSION

    @staticmethod
    def _choose_cue(sentence, start, subject, obj, cues, near):
        """Pick the cue that structurally relates subject and object.

        Returns (cue, True) for a supported relation. Returns (cue, False)
        when the pair is only listed near a cue, so the candidate is kept
        but flagged. Returns (None, False) when no cue is near enough.
        """
        def span(mention):
            return (mention.start - start, mention.end - start)

        flagged = None
        for cue in cues:
            if not near(subject, *cue.span()):
                continue
            result = assess(sentence, span(subject), span(obj), cue.span())
            object_near = near(obj, *cue.span())
            if result.supported and (
                object_near or result.basis == CUE_GOVERNS_ENUMERATION
            ):
                return cue, True
            if object_near and flagged is None:
                flagged = cue
        return flagged, False

    def __init__(self, matcher: LexiconMatcher) -> None:
        self._matcher = matcher

    @property
    def lexicon_version(self) -> str:
        return self._matcher.lexicon.lexicon_version

    def extract(
        self,
        chunk: TextChunk,
        evidence_category: EvidenceCategory | None = None,
    ) -> tuple[ChunkMentions, list[CandidateClaim]]:
        text = chunk.text
        mentions = self._matcher.find(text)
        chunk_mentions = ChunkMentions(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            mentions=mentions,
        )
        if len({m.concept.concept_id for m in mentions}) < 2:
            return chunk_mentions, []

        candidates: list[CandidateClaim] = []
        for start, end in sentence_spans(text):
            in_sentence = [m for m in mentions if start <= m.start and m.end <= end]
            if len({m.concept.concept_id for m in in_sentence}) < 2:
                continue
            candidates.extend(
                self._sentence_candidates(
                    chunk, text, start, end, in_sentence, evidence_category
                )
            )
        return chunk_mentions, candidates

    def _sentence_candidates(
        self,
        chunk: TextChunk,
        text: str,
        start: int,
        end: int,
        mentions: list[ConceptMention],
        evidence_category: EvidenceCategory | None,
    ) -> Iterable[CandidateClaim]:
        sentence = text[start:end]
        # First mention of each concept in the sentence.
        first: dict[str, ConceptMention] = {}
        for mention in mentions:
            first.setdefault(mention.concept.concept_id, mention)

        base_notes = []
        if _NEGATION.search(sentence):
            base_notes.append(NEGATION_CUE)
        if _DOSAGE.search(sentence):
            base_notes.append(DOSAGE_STATEMENT)
        if _QUALIFIER.search(sentence):
            base_notes.append(QUALIFIED_STATEMENT)
        if chunk.quality_flags:
            base_notes.append(SOURCE_QUALITY_FLAGGED)
        if evidence_category is None:
            base_notes.append(EVIDENCE_CATEGORY_UNKNOWN)
        if sentence.count(",") + sentence.count(";") >= LIST_SEPARATORS:
            base_notes.append(LIST_CONTEXT)

        passage = SupportingPassage(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            sentence=sentence,
            sentence_start=start,
            sentence_end=end,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            section_heading=chunk.section_heading,
            verse_numbers=chunk.verse_numbers,
            citation_refs=chunk.citation_refs,
            primary_script=chunk.primary_script,
            declared_source_language=chunk.declared_source_language,
            declared_translation_language=chunk.declared_translation_language,
            chunk_quality_flags=chunk.quality_flags,
        )

        def near(mention: ConceptMention, cue_start: int, cue_end: int) -> bool:
            # Distance in sentence coordinates between mention and cue.
            m_start, m_end = mention.start - start, mention.end - start
            gap = max(cue_start - m_end, m_start - cue_end, 0)
            return gap <= CUE_WINDOW_CHARS

        produced = 0
        for predicate, (subject_types, object_types) in CANDIDATE_PREDICATES.items():
            cues = list(_CUE_PATTERNS[predicate].finditer(sentence))
            if not cues:
                continue
            for subject in first.values():
                if subject.concept.concept_type not in subject_types:
                    continue
                for obj in first.values():
                    if (
                        obj.concept.concept_type not in object_types
                        or obj.concept.concept_id == subject.concept.concept_id
                    ):
                        continue
                    cue, supported = self._choose_cue(
                        sentence, start, subject, obj, cues, near
                    )
                    if cue is None:
                        continue
                    if produced >= MAX_CANDIDATES_PER_SENTENCE:
                        return
                    notes = list(base_notes)
                    if not supported:
                        notes.append(STRUCTURE_UNSUPPORTED)
                    if subject.ambiguous or obj.ambiguous:
                        notes.append(AMBIGUOUS_TERM)
                    if subject.compound or obj.compound:
                        notes.append(COMPOUND_MATCH)
                    produced += 1
                    yield CandidateClaim(
                        claim_id=make_claim_id(
                            chunk.chunk_id, start, end,
                            subject.concept.concept_id, predicate,
                            obj.concept.concept_id,
                        ),
                        subject=subject.concept,
                        predicate=predicate,
                        object=obj.concept,
                        cue=cue.group(0),
                        passage=passage,
                        evidence_category=evidence_category,
                        extraction_method=EXTRACTOR_NAME,
                        extractor_version=EXTRACTOR_VERSION,
                        lexicon_version=self.lexicon_version,
                        uncertainty=notes,
                    )
