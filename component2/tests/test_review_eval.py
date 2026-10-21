"""Tests for human-reviewed retrieval evaluation (synthetic pools only)."""

import json

import pytest

from app.knowledge_ingestion.cli import main
from app.retrieval.review_eval import (
    ReviewFileError,
    evaluate_reviewed,
    load_pool,
    load_reviews,
)
from app.retrieval.source_chunks import write_relevance_pool


A, B = "model/a", "model/b"

# (case, chunk, rank under A, rank under B, in existing automatic labels)
POOL = [
    ("c1", "x1", 1, None, True),
    ("c1", "x2", 2, 1, True),
    ("c1", "x3", 3, None, False),
    ("c1", "x4", None, 2, False),
    ("c1", "x5", None, 3, False),
    ("c2", "y1", 1, 1, True),
    ("c2", "y2", 2, 2, False),
    ("c2", "y3", 3, 3, False),
    ("c3", "z1", 1, 1, False),
    ("c3", "z2", 2, 2, True),
    ("c3", "z3", 3, 3, False),
]
QUERIES = {"c1": "query one", "c2": "query two", "c3": "पाण्डु रोग"}

# Judgements giving, under the strict policy:
#   c1: A rank 2, B rank 1    c2: nothing relevant    c3: A rank 2, B rank 2
JUDGED = {
    ("c1", "x1"): "not_relevant", ("c1", "x2"): "relevant",
    ("c1", "x3"): "not_relevant", ("c1", "x4"): "not_relevant",
    ("c1", "x5"): "not_relevant",
    ("c2", "y1"): "not_relevant", ("c2", "y2"): "not_relevant",
    ("c2", "y3"): "not_relevant",
    ("c3", "z1"): "partially_relevant", ("c3", "z2"): "relevant",
    ("c3", "z3"): "not_relevant",
}


def pool_rows(judged=None, reviewer="reviewer-under-test", notes=None):
    rows = []
    for case_id, chunk_id, rank_a, rank_b, auto in POOL:
        value = (judged or {}).get((case_id, chunk_id), "")
        rows.append({
            "case_id": case_id,
            "query": QUERIES[case_id],
            "chunk_id": chunk_id,
            "source_id": "src-test",
            "in_existing_labels": auto,
            "text": "synthetic passage",
            f"rank:{A}": rank_a,
            f"similarity:{A}": 0.5 if rank_a else None,
            f"rank:{B}": rank_b,
            f"similarity:{B}": 0.5 if rank_b else None,
            "judgement": value,
            "reviewer": reviewer if value else "",
            "review_notes": (notes or {}).get((case_id, chunk_id), ""),
        })
    return rows


def files(tmp_path, *reviews):
    pool = write_relevance_pool(pool_rows(), tmp_path / "pool.csv")
    paths = []
    for index, rows in enumerate(reviews):
        paths.append(write_relevance_pool(rows, tmp_path / f"review_{index}.csv"))
    return pool, paths


def evaluate(tmp_path, *reviews, policy="strict", k=3):
    pool_path, paths = files(tmp_path, *reviews)
    models, pool = load_pool(pool_path)
    result = load_reviews(pool, paths)
    assert result.errors == []
    return evaluate_reviewed(models, pool, result, policy=policy, k=k)


def review_errors(tmp_path, rows):
    pool_path, paths = files(tmp_path, rows)
    _, pool = load_pool(pool_path)
    return load_reviews(pool, paths).errors


# --- metrics -----------------------------------------------------------------

def test_strict_metrics_from_reviewed_labels_only(tmp_path):
    report = evaluate(tmp_path, pool_rows(JUDGED))

    assert report["cases_scored"] == ["c1", "c3"]
    assert report["cases_excluded"] == {"c2": "no_relevant_in_pool"}
    assert report["metrics"][A] == {
        "hit_rate@1": 0.0, "hit_rate@3": 1.0, "mrr@3": 0.5,
        "ranks": {"c1": 2, "c3": 2},
    }
    assert report["metrics"][B] == {
        "hit_rate@1": 0.5, "hit_rate@3": 1.0, "mrr@3": 0.75,
        "ranks": {"c1": 1, "c3": 2},
    }
    assert report["reviewed_rows"] == len(POOL)


def test_lenient_policy_counts_partially_relevant(tmp_path):
    report = evaluate(tmp_path, pool_rows(JUDGED), policy="lenient")
    assert report["metrics"][A]["ranks"] == {"c1": 2, "c3": 1}
    assert report["metrics"][A]["mrr@3"] == 0.75
    assert report["metrics"][B]["hit_rate@1"] == 1.0
    assert report["relevant_values"] == ["partially_relevant", "relevant"]


def test_missing_judgement_before_a_hit_makes_the_case_undetermined(tmp_path):
    judged = dict(JUDGED)
    del judged[("c1", "x1")]  # A's rank 1 is unreviewed
    report = evaluate(tmp_path, pool_rows(judged))

    assert report["cases_scored"] == ["c3"]  # same set for both models
    assert report["cases_excluded"]["c1"] == (
        f"undetermined for {A}: rank 1 is unreviewed"
    )
    assert set(report["metrics"][B]["ranks"]) == {"c3"}


def test_missing_judgement_after_the_first_hit_does_not_matter(tmp_path):
    judged = dict(JUDGED)
    del judged[("c1", "x3")]  # A's rank 3 comes after its hit at rank 2
    report = evaluate(tmp_path, pool_rows(judged))
    assert "c1" in report["cases_scored"]


def test_a_decisive_miss_is_scored_not_excluded(tmp_path):
    judged = dict(JUDGED)
    judged[("c1", "x2")] = "not_relevant"  # A and B now miss x2 ...
    judged[("c1", "x4")] = "relevant"      # ... but B finds x4 at rank 2
    report = evaluate(tmp_path, pool_rows(judged))
    assert report["metrics"][A]["ranks"]["c1"] is None
    assert report["metrics"][B]["ranks"]["c1"] == 2


def test_uncertain_is_undetermined_and_unreviewed_cases_are_insufficient(tmp_path):
    judged = {("c1", "x1"): "uncertain"}
    notes = {("c1", "x1"): "Ambiguous OCR."}
    report = evaluate(tmp_path, pool_rows(judged, notes=notes))
    assert report["cases_scored"] == []
    assert all(
        reason.startswith("insufficient_review")
        for reason in report["cases_excluded"].values()
    )
    assert report["cases_excluded"]["c1"].endswith("(1 uncertain, 4 unreviewed)")
    assert report["metrics"][A]["hit_rate@1"] is None


def test_k_larger_than_pool_depth_is_rejected(tmp_path):
    pool_path, paths = files(tmp_path, pool_rows(JUDGED))
    models, pool = load_pool(pool_path)
    with pytest.raises(ValueError, match="pool depth"):
        evaluate_reviewed(models, pool, load_reviews(pool, paths), k=10)


def test_automatic_labels_are_only_cross_tabulated(tmp_path):
    report = evaluate(tmp_path, pool_rows(JUDGED))
    table = report["auto_label_vs_human"]
    assert table["auto_labelled / not_relevant"] == 2  # x1 and y1
    assert table["auto_labelled / relevant"] == 2      # x2 and z2
    assert sum(table.values()) == len(POOL)


# --- validation --------------------------------------------------------------

@pytest.mark.parametrize("change, message", [
    ({"judgement": "Relevant!"}, "invalid judgement"),
    ({"reviewer": ""}, "judgement without a reviewer"),
    ({"judgement": "uncertain", "review_notes": ""}, "'uncertain' needs a review note"),
    ({"judgement": "", "reviewer": "someone"}, "reviewer given without a judgement"),
    ({"query": "edited query"}, "differs from the original pool"),
    ({"chunk_id": "not-in-pool"}, "is not in the original pool"),
])
def test_invalid_rows_are_reported(tmp_path, change, message):
    rows = pool_rows(JUDGED)
    rows[0].update(change)
    errors = review_errors(tmp_path, rows)
    assert any(message in error for error in errors), errors


def test_duplicate_and_missing_rows_are_reported(tmp_path):
    rows = pool_rows(JUDGED)
    duplicated = rows + [dict(rows[0])]
    assert any("duplicate row" in e for e in review_errors(tmp_path, duplicated))

    shortened = pool_rows(JUDGED)[:-2]
    assert any("2 pool row(s) are missing" in e for e in review_errors(tmp_path, shortened))


def test_same_reviewer_cannot_judge_a_row_twice_across_files(tmp_path):
    pool_path, paths = files(tmp_path, pool_rows(JUDGED), pool_rows(JUDGED))
    _, pool = load_pool(pool_path)
    errors = load_reviews(pool, paths).errors
    assert any("already judged" in e for e in errors)


def test_disagreeing_reviewers_are_a_conflict_not_resolved(tmp_path):
    first = dict(JUDGED)
    first[("c1", "x4")] = "relevant"  # both agree x4 (B rank 2) is relevant
    second = dict(first)
    second[("c1", "x2")] = "not_relevant"
    report = evaluate(
        tmp_path,
        pool_rows(first, reviewer="reviewer-one"),
        pool_rows(second, reviewer="reviewer-two"),
    )
    assert report["conflicting_rows"] == ["c1 x2"]
    assert report["cases_excluded"]["c1"].endswith("rank 2 is conflict")
    assert report["reviewers"] == ["reviewer-one", "reviewer-two"]
    # Agreeing reviewers still score c3.
    assert "c3" in report["cases_scored"]


def test_non_pool_file_is_rejected(tmp_path):
    other = tmp_path / "other.csv"
    other.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ReviewFileError, match="not a search-pool export"):
        load_pool(other)


# --- CLI ---------------------------------------------------------------------

def test_cli_review_eval_reports_and_never_modifies_inputs(tmp_path, capsys):
    pool_path, (review_path,) = files(tmp_path, pool_rows(JUDGED))
    cases = tmp_path / "cases.jsonl"
    cases.write_text("".join(
        json.dumps({"case_id": c, "query": q, "relevant_chunk_ids": ["x"]}) + "\n"
        for c, q in QUERIES.items()
    ), encoding="utf-8")
    before = {p: p.read_bytes() for p in (pool_path, review_path, cases)}
    out = tmp_path / "reports" / "strict.json"

    assert main(["review-eval", str(pool_path), str(review_path), "--k", "3",
                 "--cases", str(cases), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["cases_scored"] == ["c1", "c3"]
    assert report["case_query_mismatches"] == []
    assert {p: p.read_bytes() for p in before} == before

    assert main(["review-eval", str(pool_path), str(review_path), "--k", "3",
                 "--out", str(review_path)]) == 2
    assert main(["review-eval", str(pool_path), str(pool_path), "--k", "3"]) == 2
    assert main(["review-eval", str(pool_path), str(review_path)]) == 2  # k=10 > depth
    capsys.readouterr()


def test_cli_rejects_invalid_reviews_and_query_mismatch(tmp_path, capsys):
    bad = pool_rows(JUDGED)
    bad[0]["judgement"] = "maybe"
    pool_path, (review_path,) = files(tmp_path, bad)
    assert main(["review-eval", str(pool_path), str(review_path), "--k", "3"]) == 1
    assert "invalid judgement" in capsys.readouterr().out

    good_pool, (good_review,) = files(tmp_path, pool_rows(JUDGED))
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"case_id": "c1", "query": "something else",
                                 "relevant_chunk_ids": ["x"]}) + "\n", encoding="utf-8")
    assert main(["review-eval", str(good_pool), str(good_review), "--k", "3",
                 "--cases", str(cases)]) == 1
    assert "c1" in json.loads(capsys.readouterr().out)["case_query_mismatches"]
