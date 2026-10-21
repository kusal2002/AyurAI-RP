"""Curated concept lexicon and script-aware term matching.

A lexicon lists, for each concept, spelling and script variants of the
same term. It never maps a word to a different word in another language:
cross-language equivalence is a claim for reviewers, not for a lexicon.

Matching works on chunk text (NFC-normalized) and is case-insensitive.
A match must start at a word boundary. A match that runs on into further
letters or combining marks (Sanskrit compounds and inflections such as
'pāṇḍuroga' or 'पित्तं') is accepted only for concepts marked
allow_compound, and is then reported as a compound match.
"""

import json
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.schema import NODE_IDENTIFIERS
from app.knowledge_candidates.models import ConceptMention, ConceptRef
from app.knowledge_ingestion.normalization import normalize_text


CONCEPT_TYPES = frozenset(NODE_IDENTIFIERS) - {"Evidence", "Claim"}
DEFAULT_LEXICON_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge" / "seed_lexicon_v1.json"
)


class LexiconConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(min_length=1)
    concept_type: str
    label: str = Field(min_length=1)
    terms: list[str] = Field(min_length=1)
    ambiguous: bool = False
    allow_compound: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def _check_type(self) -> "LexiconConcept":
        if self.concept_type not in CONCEPT_TYPES:
            raise ValueError(
                f"{self.concept_id}: unknown concept type "
                f"{self.concept_type!r}; expected one of {sorted(CONCEPT_TYPES)}."
            )
        return self


class Lexicon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lexicon_version: str = Field(min_length=1)
    review_status: str
    description: str | None = None
    concepts: list[LexiconConcept]

    @model_validator(mode="after")
    def _check_unique(self) -> "Lexicon":
        ids = [concept.concept_id for concept in self.concepts]
        if len(ids) != len(set(ids)):
            raise ValueError("Lexicon concept_id values must be unique.")
        owner: dict[str, str] = {}
        for concept in self.concepts:
            for term in concept.terms:
                key = _term_key(term)
                if not key:
                    raise ValueError(f"{concept.concept_id}: empty term.")
                if owner.get(key, concept.concept_id) != concept.concept_id:
                    raise ValueError(
                        f"Term {term!r} is listed for both {owner[key]} and "
                        f"{concept.concept_id}; a term must name one concept."
                    )
                owner[key] = concept.concept_id
        return self


def _term_key(term: str) -> str:
    return normalize_text(term).text.casefold()


def load_lexicon(path: str | Path) -> Lexicon:
    return Lexicon.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def _is_word_char(char: str) -> bool:
    return char.isalnum() or unicodedata.category(char).startswith("M")


class LexiconMatcher:
    def __init__(self, lexicon: Lexicon) -> None:
        self.lexicon = lexicon
        self._by_key: dict[str, LexiconConcept] = {}
        for concept in lexicon.concepts:
            for term in concept.terms:
                self._by_key[_term_key(term)] = concept
        terms = sorted(self._by_key, key=len, reverse=True)
        # Spaces in multi-word terms match any run of whitespace.
        alternatives = [
            r"\s+".join(re.escape(part) for part in term.split())
            for term in terms
        ]
        self._pattern = re.compile(
            "|".join(alternatives), re.IGNORECASE
        ) if alternatives else None

    def find(self, text: str) -> list[ConceptMention]:
        if self._pattern is None:
            return []
        mentions: list[ConceptMention] = []
        for match in self._pattern.finditer(text):
            start, end = match.span()
            if start > 0 and _is_word_char(text[start - 1]):
                continue
            key = " ".join(match.group(0).split()).casefold()
            concept = self._by_key.get(key)
            if concept is None:
                continue
            compound = end < len(text) and _is_word_char(text[end])
            if compound and not concept.allow_compound:
                continue
            mentions.append(
                ConceptMention(
                    concept=ConceptRef(
                        concept_id=concept.concept_id,
                        concept_type=concept.concept_type,
                        label=concept.label,
                    ),
                    surface=match.group(0),
                    start=start,
                    end=end,
                    ambiguous=concept.ambiguous,
                    compound=compound,
                )
            )
        return mentions
