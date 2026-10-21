"""CLI for the provisional research-knowledge pathway.

    python -m app.knowledge_provisional plan DATASET --extracted corpus/extracted [--out report.json] [--check-graph]
    python -m app.knowledge_provisional apply DATASET --extracted corpus/extracted --confirm-live-write [--out report.json]
    python -m app.knowledge_provisional verify DATASET --extracted corpus/extracted [--out report.json]

`plan` never writes. `--check-graph` adds read-only counts and lists which
planned concepts already exist. `apply` is the only command that writes and
requires --confirm-live-write; it records a before/after snapshot and runs
verification afterwards.
"""

import argparse
import json
from pathlib import Path

from app.knowledge_provisional.plan import plan_dataset, plan_to_dict


def _dump(data, out: Path | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.knowledge_provisional")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("dataset", type=Path)
        cmd.add_argument("--extracted", type=Path, required=True)
        cmd.add_argument("--out", type=Path)
        if name == "plan":
            cmd.add_argument("--check-graph", action="store_true",
                             help="Add read-only graph counts and existing-concept checks.")
        if name == "apply":
            cmd.add_argument("--confirm-live-write", action="store_true",
                             help="Required: writes to the configured Neo4j database.")
    args = parser.parse_args(argv)

    plan = plan_dataset(args.dataset, args.extracted)
    report = plan_to_dict(plan)
    summary = report["summary"]
    print(f"Dataset {summary['dataset_id']} v{summary['dataset_version']}: "
          f"{summary['claims']} claims, {summary['evidence']} evidence, {summary['concepts']} concepts, "
          f"{summary['sources']} sources, {summary['source_chunks']} chunks; "
          f"rejected {summary['rejected']}, duplicates {summary['duplicates']}")
    for item in report["rejected"]:
        print(f"  REJECTED {item['item']}: {item['reason']}")

    if args.command == "plan":
        if args.check_graph:
            from app.db.neo4j import close_neo4j_driver, get_neo4j_driver
            from app.knowledge_provisional.writer import existing_concepts, snapshot

            driver = get_neo4j_driver()
            try:
                report["graph_before"] = snapshot(driver)
                existing = existing_concepts(driver, plan)
            finally:
                close_neo4j_driver()
            report["concepts_already_in_graph"] = existing
            report["concepts_to_create"] = [c for c in plan.concepts if c not in existing]
            print(f"Graph now: {report['graph_before']['nodes']}")
            print(f"Concepts already present: {len(existing)}; to create: {len(report['concepts_to_create'])}")
        print("DRY RUN: nothing was written.")
        _dump(report, args.out)
        return 1 if plan.rejected else 0

    from app.db.neo4j import close_neo4j_driver, get_neo4j_driver
    from app.knowledge_provisional.writer import snapshot, verify_plan, write_plan

    driver = get_neo4j_driver()
    try:
        if args.command == "apply":
            if not args.confirm_live_write:
                print("Refusing to write: add --confirm-live-write after reviewing the dry run.")
                return 2
            if plan.rejected:
                print("Refusing to write: the plan has rejected items. Fix them first.")
                return 1
            report["graph_before"] = snapshot(driver)
            write = write_plan(plan, driver)
            report["write"] = write.__dict__
            report["graph_after"] = snapshot(driver)
            print(f"Applied batch {write.batch_id}: {write.counters}")
        report["verification"] = verify_plan(plan, driver)
    finally:
        close_neo4j_driver()
    verification = report["verification"]
    print(f"Verification: {verification['status']} "
          f"(claims {verification['claims_found']}/{verification['claims_expected']}, "
          f"evidence {verification['evidence_found']}/{verification['evidence_expected']})")
    for problem in verification["problems"][:20]:
        print(f"  PROBLEM {problem}")
    _dump(report, args.out)
    return 0 if verification["status"] == "verified" else 1
