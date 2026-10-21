"""Retrieval metrics from human relevance judgements on a pooled export.

Workflow (see docs/knowledge_ingestion.md, "Human-reviewed evaluation"):

1. `search-pool` writes the original pool CSV. It is never edited.
2. Each reviewer fills `judgement`, `reviewer` and `review_notes` in their
   own copy of the pool.
3. `review-eval` validates the copies against the original pool and
   computes metrics from the judgements only.

Judgement values (blank means "not reviewed"):

    relevant            the passage answers the query
    partially_relevant  the passage is on topic but answers only part of it
    not_relevant        the passage does not help answer the query
    uncertain           the reviewer could not decide (a note is required)

Policies decide which values count as relevant:

    strict   relevant
    lenient  relevant, partially_relevant

`uncertain`, blank and conflicting judgements are "undetermined": they are
never counted as relevant or as not relevant.

Ranks come from the original pool, so they reflect the stores at pooling
time. Rank determinability: for each model, ranks 1..k are read in order.
The first relevant rank is the case's rank. A miss is recorded only when
every rank up to k is decisively not relevant. If an undetermined passage
comes before any relevant one, the case is undetermined for that model.
Only cases that are determinate for every compared model, and that have at
least one passage judged relevant, are scored, so all models are compared
on exactly the same queries. Excluded cases are listed with the reason.

The automatic labels (`in_existing_labels`, the smoke-case JSONL) are never
used for scoring; they are only cross-tabulated against the judgements.
Nothing here writes to the inputs.
"""

import csv
import json
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


JUDGEMENTS = ("relevant", "partially_relevant", "not_relevant", "uncertain")
POLICIES = {
    "strict": frozenset({"relevant"}),
    "lenient": frozenset({"relevant", "partially_relevant"}),
}
DECISIVE = frozenset({"relevant", "partially_relevant", "not_relevant"})
IDENTITY_COLUMNS = ("case_id", "query", "chunk_id", "source_id")
JUDGEMENT_COLUMNS = ("judgement", "reviewer", "review_notes")
RANK_PREFIX = "rank:"


class ReviewFileError(ValueError):
    """A pool or review file cannot be read or lacks required columns."""


@dataclass
class PoolRow:
    case_id: str
    query: str
    chunk_id: str
    source_id: str
    in_existing_labels: bool | None
    ranks: dict[str, int | None]


@dataclass
class Judgement:
    value: str
    reviewer: str
    notes: str
    source: str  # "<file>:<line>"


@dataclass
class ReviewResult:
    errors: list[str] = field(default_factory=list)
    judgements: dict[tuple[str, str], list[Judgement]] = field(
        default_factory=lambda: defaultdict(list)
    )


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            return list(reader.fieldnames or []), rows
    except UnicodeDecodeError:
        raise ReviewFileError(
            f"{path.name} is not UTF-8; save it as 'CSV UTF-8' and retry."
        ) from None
    except OSError as exc:
        raise ReviewFileError(f"{path.name} could not be read ({type(exc).__name__}).") from None


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value or "").strip()


def _rank(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        raise ReviewFileError(f"Rank {value!r} is not a number.") from None


def load_pool(path: str | Path) -> tuple[list[str], dict[tuple[str, str], PoolRow]]:
    """Read the original pool. Returns (model IDs, rows by (case, chunk))."""
    path = Path(path)
    columns, raw = _read_csv(path)
    missing = [c for c in IDENTITY_COLUMNS if c not in columns]
    models = [c[len(RANK_PREFIX):] for c in columns if c.startswith(RANK_PREFIX)]
    if missing or not models:
        raise ReviewFileError(
            f"{path.name} is not a search-pool export "
            f"(missing: {missing or 'rank:<model> columns'})."
        )
    rows: dict[tuple[str, str], PoolRow] = {}
    for line, row in enumerate(raw, start=2):
        key = (row["case_id"].strip(), row["chunk_id"].strip())
        if key in rows:
            raise ReviewFileError(f"{path.name}:{line}: duplicate pool row {key}.")
        flag = (row.get("in_existing_labels") or "").strip().lower()
        rows[key] = PoolRow(
            case_id=key[0],
            query=_nfc(row["query"]),
            chunk_id=key[1],
            source_id=row["source_id"].strip(),
            in_existing_labels={"true": True, "false": False}.get(flag),
            ranks={m: _rank(row.get(RANK_PREFIX + m)) for m in models},
        )
    return models, rows


def load_reviews(
    pool: dict[tuple[str, str], PoolRow],
    paths: list[str | Path],
) -> ReviewResult:
    """Validate reviewer copies against the pool and collect judgements."""
    result = ReviewResult()
    seen_by_reviewer: dict[tuple[str, str, str], str] = {}
    for path in map(Path, paths):
        columns, raw = _read_csv(path)
        missing = [c for c in (*IDENTITY_COLUMNS, *JUDGEMENT_COLUMNS) if c not in columns]
        if missing:
            result.errors.append(f"{path.name}: missing columns {missing}.")
            continue
        keys_in_file: dict[tuple[str, str], int] = {}
        for line, row in enumerate(raw, start=2):
            where = f"{path.name}:{line}"
            key = (row["case_id"].strip(), row["chunk_id"].strip())
            if key in keys_in_file:
                result.errors.append(
                    f"{where}: duplicate row for {key} (first at line {keys_in_file[key]})."
                )
                continue
            keys_in_file[key] = line
            original = pool.get(key)
            if original is None:
                result.errors.append(f"{where}: {key} is not in the original pool.")
                continue
            if (_nfc(row["query"]) != original.query
                    or row["source_id"].strip() != original.source_id):
                result.errors.append(
                    f"{where}: query or source_id differs from the original pool."
                )
                continue
            value = (row["judgement"] or "").strip()
            reviewer = (row["reviewer"] or "").strip()
            notes = (row["review_notes"] or "").strip()
            if not value:
                if reviewer:
                    result.errors.append(f"{where}: reviewer given without a judgement.")
                continue
            if value not in JUDGEMENTS:
                result.errors.append(
                    f"{where}: invalid judgement {value!r}; use one of {', '.join(JUDGEMENTS)}."
                )
                continue
            if not reviewer:
                result.errors.append(f"{where}: judgement without a reviewer name.")
                continue
            if value == "uncertain" and not notes:
                result.errors.append(f"{where}: 'uncertain' needs a review note.")
                continue
            reviewer_key = (reviewer.casefold(), *key)
            if reviewer_key in seen_by_reviewer:
                result.errors.append(
                    f"{where}: {reviewer} already judged {key} at "
                    f"{seen_by_reviewer[reviewer_key]}."
                )
                continue
            seen_by_reviewer[reviewer_key] = where
            result.judgements[key].append(Judgement(value, reviewer, notes, where))
        absent = sorted(set(pool) - set(keys_in_file))
        if absent:
            result.errors.append(
                f"{path.name}: {len(absent)} pool row(s) are missing, e.g. {absent[0]}."
            )
    return result


def resolve(judgements: list[Judgement]) -> tuple[str | None, bool]:
    """Combined judgement for one passage: (value or None, is_conflict)."""
    values = {j.value for j in judgements}
    if not values:
        return None, False
    if len(values) > 1:
        return None, True
    return values.pop(), False


def evaluate_reviewed(
    models: list[str],
    pool: dict[tuple[str, str], PoolRow],
    reviews: ReviewResult,
    policy: str = "strict",
    k: int = 10,
    cases_file: dict[str, str] | None = None,
) -> dict:
    """Compute metrics from reviewed judgements only (see module docstring)."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy {policy!r}; use {sorted(POLICIES)}.")
    if not pool:
        raise ValueError("The pool is empty.")
    depth = {
        model: max((row.ranks[model] or 0) for row in pool.values()) for model in models
    }
    shallow = {m: d for m, d in depth.items() if d < k}
    if shallow:
        raise ValueError(f"k={k} exceeds the pool depth for {shallow}; use a smaller k.")
    relevant_values = POLICIES[policy]

    by_case: dict[str, list[PoolRow]] = defaultdict(list)
    for row in pool.values():
        by_case[row.case_id].append(row)

    def label(row: PoolRow) -> str:
        value, conflict = resolve(reviews.judgements.get((row.case_id, row.chunk_id), []))
        if conflict:
            return "conflict"
        if value is None:
            return "unreviewed"
        if value == "uncertain":
            return "uncertain"
        return "relevant" if value in relevant_values else "not_relevant"

    scored: list[str] = []
    excluded: dict[str, str] = {}
    ranks: dict[str, dict[str, int | None]] = {m: {} for m in models}
    for case_id in sorted(by_case):
        rows = by_case[case_id]
        labels = {row.chunk_id: label(row) for row in rows}
        if "relevant" not in labels.values():
            if all(value == "not_relevant" for value in labels.values()):
                excluded[case_id] = "no_relevant_in_pool"
            else:
                pending = Counter(
                    value for value in labels.values() if value != "not_relevant"
                )
                excluded[case_id] = (
                    "insufficient_review: no passage judged relevant yet ("
                    + ", ".join(f"{count} {kind}" for kind, count in sorted(pending.items()))
                    + ")"
                )
            continue
        case_ranks: dict[str, int | None] = {}
        reason = None
        for model in models:
            ordered = {row.ranks[model]: row for row in rows if row.ranks[model]}
            outcome = None
            for position in range(1, k + 1):
                row = ordered.get(position)
                status = labels[row.chunk_id] if row else "rank_missing_from_pool"
                if status == "relevant":
                    outcome = position
                    break
                if status != "not_relevant":
                    reason = f"undetermined for {model}: rank {position} is {status}"
                    break
            if reason:
                break
            case_ranks[model] = outcome
        if reason:
            excluded[case_id] = reason
            continue
        scored.append(case_id)
        for model in models:
            ranks[model][case_id] = case_ranks[model]

    def metrics(model: str) -> dict:
        values = [ranks[model][case] for case in scored]
        count = len(values) or 1
        return {
            "hit_rate@1": round(sum(1 for r in values if r == 1) / count, 4) if values else None,
            f"hit_rate@{k}": round(sum(1 for r in values if r) / count, 4) if values else None,
            f"mrr@{k}": round(sum(1 / r for r in values if r) / count, 4) if values else None,
            "ranks": {case: ranks[model][case] for case in scored},
        }

    agreement = Counter()
    for (case_id, chunk_id), row in pool.items():
        value, conflict = resolve(reviews.judgements.get((case_id, chunk_id), []))
        human = "conflict" if conflict else (value or "unreviewed")
        auto = {True: "auto_labelled", False: "not_auto_labelled", None: "auto_unknown"}[
            row.in_existing_labels
        ]
        agreement[f"{auto} / {human}"] += 1

    query_mismatches = []
    if cases_file is not None:
        for case_id, rows in by_case.items():
            expected = cases_file.get(case_id)
            if expected is None or _nfc(expected) != rows[0].query:
                query_mismatches.append(case_id)

    reviewed_rows = sum(1 for js in reviews.judgements.values() if js)
    conflicts = sorted(
        f"{case_id} {chunk_id}"
        for (case_id, chunk_id), js in reviews.judgements.items()
        if resolve(js)[1]
    )
    return {
        "policy": policy,
        "relevant_values": sorted(relevant_values),
        "k": k,
        "pool_depth": depth,
        "models": models,
        "reviewers": sorted({j.reviewer for js in reviews.judgements.values() for j in js}),
        "pool_rows": len(pool),
        "reviewed_rows": reviewed_rows,
        "conflicting_rows": conflicts,
        "cases_total": len(by_case),
        "cases_scored": scored,
        "cases_excluded": excluded,
        "metrics": {model: metrics(model) for model in models},
        "auto_label_vs_human": dict(sorted(agreement.items())),
        "case_query_mismatches": sorted(query_mismatches),
    }


def load_case_queries(path: str | Path) -> dict[str, str]:
    """case_id -> query from the original smoke-case JSONL (read only)."""
    queries = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                data = json.loads(line)
                queries[data["case_id"]] = data["query"]
    return queries
