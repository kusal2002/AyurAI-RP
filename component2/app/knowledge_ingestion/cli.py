"""Command-line interface for local source-document ingestion.

Nothing here writes to Neo4j or sends text to any external service.
Printed output contains metadata and counts, never passage text.

Usage:
    python -m app.knowledge_ingestion inspect corpus/raw/book.pdf
    python -m app.knowledge_ingestion extract corpus/raw/book.pdf --out corpus/extracted
    python -m app.knowledge_ingestion manifest corpus/raw --out corpus/extracted/manifest.json [--extract-dir corpus/extracted]
    python -m app.knowledge_ingestion manifest-update corpus/extracted/manifest.json --root corpus/raw --path-prefix classical_open/ [--extract-dir corpus/extracted]
    python -m app.knowledge_ingestion status corpus/extracted/manifest.json
    python -m app.knowledge_ingestion duplicates corpus/raw
    python -m app.knowledge_ingestion chunk corpus/extracted
    python -m app.knowledge_ingestion validate corpus/extracted
    python -m app.knowledge_ingestion embed corpus/extracted --store corpus/extracted/embeddings
    python -m app.knowledge_ingestion search "pandu roga lakshana" --store corpus/extracted/embeddings
    python -m app.knowledge_ingestion search-eval cases.jsonl --store corpus/extracted/embeddings [--details]
    python -m app.knowledge_ingestion search-pool cases.jsonl --store corpus/extracted/embeddings --out corpus/extracted/eval/pool.csv [--model ID ...]
    python -m app.knowledge_ingestion review-eval corpus/extracted/eval/pool.csv corpus/extracted/eval/pool_reviewed_A.csv [more reviews] [--policy strict|lenient] [--out report.json]

Candidate knowledge (rule-based, no language model, nothing sent anywhere):
    python -m app.knowledge_ingestion candidates-extract corpus/extracted --out corpus/extracted/candidates
    python -m app.knowledge_ingestion candidates corpus/extracted/candidates --status candidate
    python -m app.knowledge_ingestion review corpus/extracted/candidates CLAIM_ID --status approved --reviewer NAME --role practitioner --note "..."
    python -m app.knowledge_ingestion conflicts corpus/extracted/candidates

Reviewer-modelled claims (treatment path; a person authors them from an exact quote):
    python -m app.knowledge_ingestion model-claim corpus/extracted/candidates --extracted corpus/extracted --chunk-id ID --quote "..." --subject Roga:R-PANDU:Pandu --predicate SUGGESTS_PRINCIPLE --object TherapeuticPrinciple:TP-X:Label --statement "..." --reviewer NAME --role practitioner --note "..."
    python -m app.knowledge_ingestion modelled corpus/extracted/candidates
    python -m app.knowledge_ingestion withdraw-modelled corpus/extracted/candidates MODELLED_ID --reviewer NAME --role practitioner --note "..."

Graph promotion (dry run unless --apply; see docs/stage_e_neo4j_design.md):
    python -m app.knowledge_ingestion source-schema [--apply]
    python -m app.knowledge_ingestion promote corpus/extracted/candidates --extracted corpus/extracted [--apply]
    python -m app.knowledge_ingestion retract corpus/extracted/candidates [--apply]

Source registry and acquisition (dry run unless --apply; see docs/dataset-discovery.md):
    python -m app.knowledge_ingestion sources corpus/source_registry.csv [--decision include]
    python -m app.knowledge_ingestion sources-validate corpus/source_registry.csv
    python -m app.knowledge_ingestion acquire corpus/source_registry.csv --raw corpus/raw [--id N-001 ...] [--apply]
    python -m app.knowledge_ingestion ingest-report corpus/extracted/manifest.json [--extracted corpus/extracted] [--candidates corpus/extracted/candidates]

Embedding commands run offline by default: a model that is not already in
the local cache is not downloaded unless --allow-download is given.
"""

import argparse
import json
import os
from pathlib import Path

from app.knowledge_ingestion.manifest import (
    SourceMetadataError,
    load_source_metadata,
    read_manifest,
    write_manifest,
)
from app.config import load_ingestion_settings, load_source_retrieval_settings
from app.knowledge_ingestion.chunking import validate_chunks
from app.knowledge_ingestion.models import ExtractionStatus
from app.knowledge_ingestion.service import (
    build_manifest,
    chunk_extraction_output,
    chunks_path,
    extraction_summary,
    iter_extraction_summaries,
    load_chunks,
    load_extraction_output,
    SourceOutsideRootError,
    corpus_relative_path,
    process_source,
    scan_hashes,
    write_chunks,
    write_extraction,
)


def _load_metadata_arg(path: Path | None):
    return load_source_metadata(path) if path is not None else None


def _print_record(record) -> None:
    print(f"source_id:   {record.source_id} ({record.source_id_origin})")
    print(f"file:        {record.relative_path}")
    print(f"format:      {record.source_format.value}")
    print(f"sha256:      {record.content_sha256}")
    print(f"status:      {record.extraction_status.value}")
    print(f"extractor:   {record.extractor} {record.extractor_version or ''}")
    print(f"passages:    {record.passage_count}")
    if record.page_count is not None:
        print(f"pages:       {record.page_count}")
    if record.pages_needing_ocr:
        print(f"needs OCR:   pages {_page_ranges(record.pages_needing_ocr)}")
    for warning in record.warnings:
        print(f"WARNING: {warning}")
    for error in record.errors:
        print(f"ERROR: {error}")


def _page_ranges(pages: list[int]) -> str:
    ranges = []
    start = previous = None
    for page in pages:
        if start is None:
            start = previous = page
        elif page == previous + 1:
            previous = page
        else:
            ranges.append((start, previous))
            start = previous = page
    if start is not None:
        ranges.append((start, previous))
    return ", ".join(
        str(a) if a == b else f"{a}-{b}" for a, b in ranges
    )


def _cmd_inspect(args) -> int:
    extraction = process_source(
        args.path, metadata=_load_metadata_arg(args.metadata)
    )
    if args.json:
        print(json.dumps(extraction_summary(extraction), ensure_ascii=False,
                         indent=2))
    else:
        _print_record(extraction.record)
    return 0


def _cmd_extract(args) -> int:
    # Without --root the record keeps the file name only (earlier behaviour).
    relative_path = (
        corpus_relative_path(args.path, args.root)
        if args.root is not None else None
    )
    extraction = process_source(
        args.path,
        relative_path=relative_path,
        metadata=_load_metadata_arg(args.metadata),
    )
    _print_record(extraction.record)
    if not extraction.result.passages:
        print("No passages extracted; nothing written.")
        return 1
    summary_path, passages_path = write_extraction(extraction, args.out)
    print(f"Wrote {summary_path} and {passages_path}")
    return 0


def _cmd_manifest(args) -> int:
    manifest = build_manifest(args.root, extract_dir=args.extract_dir)
    write_manifest(manifest, args.out)
    _print_manifest_status(manifest)
    print(f"Wrote {args.out}")
    return 0


def _cmd_manifest_update(args) -> int:
    import shutil
    from datetime import datetime, timezone

    from app.knowledge_ingestion.service import update_manifest

    manifest = read_manifest(args.manifest)
    updated, processed = update_manifest(
        manifest, args.root, args.path_prefix, extract_dir=args.extract_dir
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.manifest.with_name(f"{args.manifest.stem}.before-update-{stamp}.json")
    shutil.copy2(args.manifest, backup)
    write_manifest(updated, args.manifest)
    by_path = {r.relative_path: r for r in updated.sources}
    for relative in processed:
        record = by_path[relative]
        print(f"{record.extraction_status.value:<22} {record.source_id:<28} "
              f"passages={record.passage_count:<6} {relative}")
    for conflict in updated.source_id_conflicts:
        print(f"CONFLICT: source_id {conflict.source_id!r}: " + ", ".join(conflict.relative_paths))
    print(f"Processed {len(processed)} file(s); manifest now lists "
          f"{len(updated.sources)} source(s) (was {len(manifest.sources)}). "
          f"Previous manifest kept as {backup.name}.")
    return 0


def _print_manifest_status(manifest) -> None:
    counts: dict[str, int] = {}
    for record in manifest.sources:
        status = record.extraction_status.value
        counts[status] = counts.get(status, 0) + 1
        print(
            f"{status:<22} {record.source_id:<24} "
            f"passages={record.passage_count:<6} {record.relative_path}"
        )
    print(
        "Totals: "
        + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")
    )
    for group in manifest.duplicate_groups:
        print("DUPLICATE content: " + ", ".join(group.relative_paths))
    for conflict in manifest.source_id_conflicts:
        print(
            f"CONFLICT: source_id {conflict.source_id!r} is used for "
            "different content: " + ", ".join(conflict.relative_paths)
        )
    for skipped in manifest.skipped_files:
        print(f"SKIPPED: {skipped}")


def _cmd_status(args) -> int:
    manifest = read_manifest(args.manifest)
    _print_manifest_status(manifest)
    incomplete = [
        record for record in manifest.sources
        if record.extraction_status != ExtractionStatus.EXTRACTED
    ]
    return 1 if incomplete else 0


def _cmd_duplicates(args) -> int:
    if args.path.is_file():
        manifest = read_manifest(args.path)
        groups = [group.relative_paths for group in manifest.duplicate_groups]
        conflicts = manifest.source_id_conflicts
    else:
        by_hash, skipped = scan_hashes(args.path)
        groups = [paths for paths in by_hash.values() if len(paths) > 1]
        conflicts = []
        for item in skipped:
            print(f"SKIPPED: {item}")
    for paths in groups:
        print("DUPLICATE content: " + ", ".join(paths))
    for conflict in conflicts:
        print(
            f"CONFLICT: source_id {conflict.source_id!r}: "
            + ", ".join(conflict.relative_paths)
        )
    print(f"Duplicate groups: {len(groups)}")
    return 1 if groups or conflicts else 0


def _cmd_chunk(args) -> int:
    settings = load_ingestion_settings()
    summaries = iter_extraction_summaries(args.path)
    totals = {"sources": 0, "chunks": 0, "flagged": 0}
    for summary in summaries:
        record, _, chunks = chunk_extraction_output(summary, settings)
        out_dir = args.out if args.out is not None else summary.parent
        write_chunks(chunks, chunks_path(out_dir, record.source_id))
        flagged = sum(1 for chunk in chunks if chunk.quality_flags)
        scripts: dict[str, int] = {}
        for chunk in chunks:
            scripts[chunk.primary_script] = scripts.get(chunk.primary_script, 0) + 1
        totals["sources"] += 1
        totals["chunks"] += len(chunks)
        totals["flagged"] += flagged
        if args.verbose or len(summaries) == 1:
            script_text = ", ".join(f"{k}={v}" for k, v in sorted(scripts.items()))
            print(
                f"{record.source_id:<24} chunks={len(chunks):<6} "
                f"flagged={flagged:<5} scripts[{script_text}] "
                f"{record.relative_path}"
            )
    print(
        f"Chunked {totals['sources']} source(s): {totals['chunks']} chunks, "
        f"{totals['flagged']} with quality flags "
        f"(max {settings.chunk_max_chars} chars, "
        f"overlap {settings.chunk_overlap_chars})."
    )
    return 0


def _cmd_validate(args) -> int:
    settings = load_ingestion_settings()
    failing = 0
    checked = 0
    for summary in iter_extraction_summaries(args.path):
        record, passages = load_extraction_output(summary)
        path = chunks_path(summary.parent, record.source_id)
        if not path.is_file():
            if passages:
                failing += 1
                print(f"{record.source_id}: no chunks file; run 'chunk' first.")
            continue
        problems = validate_chunks(load_chunks(path), passages, settings)
        checked += 1
        if problems:
            failing += 1
            print(f"{record.source_id} ({record.relative_path}): "
                  f"{len(problems)} problem(s)")
            for problem in problems[:5]:
                print(f"  {problem}")
    print(f"Validated {checked} source(s); {failing} with problems.")
    return 1 if failing else 0


def _make_encoder(settings, allow_download: bool):
    """Create the configured encoder; offline unless downloads are allowed.

    The offline switches must be set before sentence-transformers is first
    imported, which happens lazily when the model is loaded.
    """
    if not allow_download:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from app.retrieval.embedding import SentenceTransformerEncoder

    return SentenceTransformerEncoder(settings)


def _source_selected(record, path_filters, excluded_sources=()) -> bool:
    """Any-match on path filters (none = all); excluded IDs always lose."""
    if isinstance(path_filters, str):
        path_filters = [path_filters]
    if record.source_id in set(excluded_sources or ()):
        return False
    return not path_filters or any(f in record.relative_path for f in path_filters)


def _chunks_for_embedding(path: Path, path_filter, excluded_sources=()):
    for summary in iter_extraction_summaries(path):
        record, _ = load_extraction_output(summary)
        if not _source_selected(record, path_filter, excluded_sources):
            continue
        chunk_file = chunks_path(summary.parent, record.source_id)
        if chunk_file.is_file():
            yield from load_chunks(chunk_file)


def _cmd_embed(args) -> int:
    from app.retrieval.source_chunks import build_embedding_store

    settings = load_source_retrieval_settings()
    encoder = _make_encoder(settings, args.allow_download)
    print(f"Model: {encoder.model_id} (batch size {settings.batch_size})")

    def progress(done: int, total: int) -> None:
        if done == total or done % (settings.batch_size * 50) == 0:
            print(f"  embedded {done}/{total}")

    stats = build_embedding_store(
        _chunks_for_embedding(args.path, args.path_filter, args.exclude_source),
        encoder,
        args.store,
        settings,
        rebuild=args.rebuild,
        progress=progress,
    )
    print(
        f"Store {stats['store_dir']}: {stats['chunks']} chunks, "
        f"dimension {stats['dimension']}, embedded {stats['embedded']}, "
        f"reused {stats['reused']}, removed {stats['removed']} "
        f"in {stats['seconds']} s."
    )
    return 0


def _cmd_search(args) -> int:
    from app.retrieval.source_chunks import SourceChunkIndex

    settings = load_source_retrieval_settings()
    index = SourceChunkIndex(
        args.store, _make_encoder(settings, args.allow_download), settings
    )
    hits = index.search(
        args.query,
        top_k=args.top_k,
        scripts=args.script,
        source_ids=args.source_id,
        max_per_source=args.max_per_source,
        include_below_threshold=args.include_below_threshold,
        exclude_flags=args.exclude_flag,
    )
    if not hits:
        print("No results above the similarity threshold.")
        return 0
    for rank, hit in enumerate(hits, start=1):
        chunk = hit.chunk
        pages = (
            f"p.{chunk.page_start}" if chunk.page_start == chunk.page_end
            else f"pp.{chunk.page_start}-{chunk.page_end}"
        ) if chunk.page_start else (
            f"lines {chunk.line_start}-{chunk.line_end}" if chunk.line_start else ""
        )
        low = " (below threshold)" if hit.below_threshold else ""
        print(f"{rank:>2}. {hit.similarity:.3f}{low} {chunk.chunk_id} {pages}")
        details = [f"script={chunk.primary_script}"]
        if chunk.section_heading:
            details.append(f"section={chunk.section_heading[:60]!r}")
        if chunk.verse_numbers:
            details.append("verses=" + ",".join(chunk.verse_numbers))
        if chunk.quality_flags:
            details.append("flags=" + ",".join(chunk.quality_flags))
        print("    " + " ".join(details) + f" [{hit.evidence_status}]")
        snippet = " ".join(chunk.text.split())[: args.snippet_chars]
        if snippet:
            print(f"    {snippet}")
    return 0


def _cmd_search_eval(args) -> int:
    from app.retrieval.source_chunks import (
        SourceChunkIndex,
        evaluate_retrieval,
        load_retrieval_cases,
    )

    settings = load_source_retrieval_settings()
    index = SourceChunkIndex(
        args.store, _make_encoder(settings, args.allow_download), settings
    )
    report = evaluate_retrieval(
        index,
        load_retrieval_cases(args.cases),
        top_k=args.top_k,
        exclude_flags=args.exclude_flag,
        details=args.details,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_search_pool(args) -> int:
    from app.retrieval.source_chunks import (
        SourceChunkIndex,
        build_relevance_pool,
        load_retrieval_cases,
        write_relevance_pool,
    )

    if args.out.resolve() == args.cases.resolve():
        print("ERROR: --out must not be the cases file; labels are never overwritten.")
        return 2
    indexes, labels = [], None
    if args.system:
        # Same configured model over several stores: compares corpora.
        settings = load_source_retrieval_settings()
        encoder = _make_encoder(settings, args.allow_download)
        labels = []
        for spec in args.system:
            label, _, root = spec.partition("=")
            if not label or not root:
                print(f"ERROR: --system must be LABEL=STORE_ROOT, got {spec!r}")
                return 2
            labels.append(label)
            indexes.append(SourceChunkIndex(Path(root), encoder, settings))
        model_ids = labels
    else:
        model_ids = args.model or [load_source_retrieval_settings().embedding_model]
        for model_id in model_ids:
            settings = load_source_retrieval_settings(model_id)
            indexes.append(SourceChunkIndex(
                args.store, _make_encoder(settings, args.allow_download), settings
            ))
    rows = build_relevance_pool(indexes, load_retrieval_cases(args.cases), args.top_k,
                                labels=labels)
    write_relevance_pool(rows, args.out)
    cases = len({row["case_id"] for row in rows})
    print(f"Wrote {len(rows)} (case, passage) rows for {cases} case(s) from "
          f"{len(model_ids)} system(s) to {args.out}.")
    print("The judgement columns are empty for human review. The file contains "
          "source-book text: keep it out of Git and do not share it.")
    return 0


def _cmd_review_eval(args) -> int:
    from app.retrieval.review_eval import (
        evaluate_reviewed,
        load_case_queries,
        load_pool,
        load_reviews,
    )

    inputs = [args.pool, *args.reviews] + ([args.cases] if args.cases else [])
    if args.out is not None and any(
        args.out.resolve() == path.resolve() for path in inputs
    ):
        print("ERROR: --out must not be one of the input files.")
        return 2
    if any(review.resolve() == args.pool.resolve() for review in args.reviews):
        print("ERROR: review the copies; the original pool is the reference.")
        return 2

    try:
        models, pool = load_pool(args.pool)
        reviews = load_reviews(pool, args.reviews)
        if reviews.errors:
            print(f"Review files are invalid ({len(reviews.errors)} problem(s)); "
                  "no metrics computed:")
            for error in reviews.errors[:50]:
                print(f"  {error}")
            return 1
        report = evaluate_reviewed(
            models, pool, reviews, policy=args.policy, k=args.k,
            cases_file=load_case_queries(args.cases) if args.cases else None,
        )
    except ValueError as exc:  # unreadable files, bad k, unknown policy
        print(f"ERROR: {exc}")
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 1 if report["case_query_mismatches"] else 0


def _cmd_candidates_extract(args) -> int:
    from app.knowledge_candidates.extractor import LexiconCueExtractor
    from app.knowledge_candidates.lexicon import (
        DEFAULT_LEXICON_PATH,
        LexiconMatcher,
        load_lexicon,
    )
    from app.knowledge_candidates.store import CandidateStore, run_extraction

    lexicon = load_lexicon(args.lexicon or DEFAULT_LEXICON_PATH)
    extractor = LexiconCueExtractor(LexiconMatcher(lexicon))
    print(
        f"Lexicon {lexicon.lexicon_version} ({lexicon.review_status}), "
        f"{len(lexicon.concepts)} concepts; extractor "
        f"{extractor.name} v{extractor.version}"
    )

    def sources():
        for summary in iter_extraction_summaries(args.path):
            record, _ = load_extraction_output(summary)
            if not _source_selected(record, args.path_filter, args.exclude_source):
                continue
            chunk_file = chunks_path(summary.parent, record.source_id)
            if chunk_file.is_file():
                yield (
                    record.source_id,
                    record.metadata.evidence_category,
                    load_chunks(chunk_file),
                )

    stats = run_extraction(sources(), extractor, CandidateStore(args.out))
    print(", ".join(f"{key}={value}" for key, value in stats.items()))
    print("Candidates are unreviewed and are not used by reasoning.")
    return 0


def _load_store(path: Path):
    from app.knowledge_candidates.store import CandidateStore

    store = CandidateStore(path)
    if not store.candidates_path.is_file():
        raise FileNotFoundError(f"No candidates in {path.name}; run candidates-extract.")
    return store


def _cmd_candidates(args) -> int:
    store = _load_store(args.path)
    candidates = list(store.load_candidates().values())
    selected = [
        c for c in candidates
        if (not args.status or c.review_status.value in args.status)
        and (not args.predicate or c.predicate in args.predicate)
        and (not args.concept or {c.subject.concept_id, c.object.concept_id}
             & set(args.concept))
        and (args.include_stale or not c.stale)
    ]
    counts: dict[str, int] = {}
    for candidate in selected:
        key = f"{candidate.review_status.value}/{candidate.predicate}"
        counts[key] = counts.get(key, 0) + 1
    for candidate in selected[: args.limit]:
        p = candidate.passage
        where = (
            f"p.{p.page_start}" if p.page_start else
            f"lines {p.line_start}-{p.line_end}" if p.line_start else ""
        )
        print(
            f"{candidate.claim_id} [{candidate.review_status.value}] "
            f"{candidate.subject.label} --{candidate.predicate}--> "
            f"{candidate.object.label}  cue={candidate.cue!r}"
        )
        print(f"    {p.source_id} {where} {p.chunk_id}")
        if candidate.uncertainty or candidate.conflict_ids:
            print(
                "    notes: " + ", ".join(candidate.uncertainty)
                + (f"; conflicts: {len(candidate.conflict_ids)}"
                   if candidate.conflict_ids else "")
            )
        if args.show_sentence:
            print("    \"" + " ".join(p.sentence.split())[:300] + "\"")
    print(f"{len(selected)} of {len(candidates)} candidate(s) match; "
          f"showing {min(len(selected), args.limit)}.")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")
    return 0


def _cmd_review(args) -> int:
    from app.knowledge_candidates.models import ReviewerRole, ReviewStatus
    from app.knowledge_candidates.review import ReviewError, review_candidate

    store = _load_store(args.path)
    candidates = store.load_candidates()
    candidate = candidates.get(args.claim_id)
    if candidate is None:
        print(f"ERROR: unknown candidate {args.claim_id}")
        return 2
    try:
        updated, event, conflicts = review_candidate(
            candidate,
            ReviewStatus(args.status),
            reviewer=args.reviewer,
            reviewer_role=ReviewerRole(args.role),
            note=args.note,
            additional_source_ids=args.source_id or [],
            superseded_by=args.superseded_by,
            acknowledge_conflicts=args.acknowledge_conflicts,
            conflicts=store.load_conflicts(),
            known_claim_ids=set(candidates),
        )
    except ReviewError as exc:
        print(f"REVIEW REFUSED: {exc}")
        return 1
    candidates[updated.claim_id] = updated
    store.append_review(event)
    store.save(candidates, conflicts)
    print(
        f"{updated.claim_id}: {event.from_status.value} -> "
        f"{event.to_status.value} by {event.reviewer} ({event.reviewer_role.value})"
    )
    return 0


def _cmd_conflicts(args) -> int:
    store = _load_store(args.path)
    conflicts = store.load_conflicts()
    for conflict in conflicts.values():
        if args.open_only and conflict.status.value != "open":
            continue
        print(
            f"{conflict.conflict_id} [{conflict.status.value}] "
            f"{conflict.kind.value}: {conflict.description}"
        )
        print("    claims: " + ", ".join(conflict.claim_ids[:8])
              + (" ..." if len(conflict.claim_ids) > 8 else ""))
    print(f"{len(conflicts)} conflict(s).")
    return 0


def _cmd_source_schema(args) -> int:
    from app.db.schema import initialize_source_schema

    statements = initialize_source_schema(dry_run=not args.apply)
    for statement in statements:
        print(statement)
    if args.apply:
        from app.db.neo4j import close_neo4j_driver

        close_neo4j_driver()
        print(f"Applied {len(statements)} additive statement(s).")
    else:
        print(f"DRY RUN: {len(statements)} statement(s) not applied. "
              "Re-run with --apply to create them.")
    return 0


def _load_promotion_inputs(candidates_dir: Path, extracted: Path):
    from app.knowledge_candidates.modelled import ModelledStore

    store = _load_store(candidates_dir)
    candidates = store.load_candidates()
    modelled = ModelledStore(candidates_dir).load()
    passages = [c.passage for c in candidates.values()] + [m.passage for m in modelled.values()]
    needed_sources = {p.source_id for p in passages}
    needed_chunks = {p.chunk_id for p in passages}
    sources, chunks = {}, {}
    for summary in iter_extraction_summaries(extracted):
        record, _ = load_extraction_output(summary)
        if record.source_id not in needed_sources:
            continue
        sources[record.source_id] = record
        chunk_file = chunks_path(summary.parent, record.source_id)
        if chunk_file.is_file():
            for chunk in load_chunks(chunk_file):
                if chunk.chunk_id in needed_chunks:
                    chunks[chunk.chunk_id] = chunk
    return candidates, store.load_conflicts(), sources, chunks, store.load_review_log()


def _manifest_conflicts(manifest_path: Path | None) -> set[str]:
    """source_ids the manifest reports as reused for different content."""
    if manifest_path is None or not manifest_path.is_file():
        return set()
    return {
        conflict.source_id
        for conflict in read_manifest(manifest_path).source_id_conflicts
    }


def _cmd_promote(args) -> int:
    from app.db.source_repository import plan_promotions, promote

    candidates, conflicts, sources, chunks, review_log = _load_promotion_inputs(
        args.path, args.extracted
    )
    manifest_path = args.manifest or (args.extracted / "manifest.json")
    conflicting = _manifest_conflicts(manifest_path)
    if not manifest_path.is_file():
        print(f"NOTE: no manifest at {manifest_path}; source_id conflicts "
              "are checked only inside the write transaction.")
    report = plan_promotions(
        candidates.values(), conflicts, sources, chunks,
        review_log=review_log, conflicting_source_ids=conflicting,
    )
    from app.db.source_repository import plan_modelled_promotions
    from app.knowledge_candidates.modelled import ModelledStore

    modelled_store = ModelledStore(args.path)
    modelled = modelled_store.load()
    modelled_report = plan_modelled_promotions(
        modelled.values(), sources, chunks,
        modelled_log=modelled_store.load_log(), conflicting_source_ids=conflicting,
    )
    report.plans.extend(modelled_report.plans)
    report.skipped.extend(modelled_report.skipped)
    if modelled:
        print(f"Reviewer-modelled claims: {len(modelled)}; to promote: "
              f"{len(modelled_report.plans)}")

    reasons: dict[str, int] = {}
    for _, reason in report.skipped:
        reasons[reason] = reasons.get(reason, 0) + 1
    print(f"Candidates: {len(candidates)}; to promote: {len(report.plans)}; "
          f"skipped: {len(report.skipped)}")
    for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
        print(f"  skipped {count:>5}: {reason}")
    for plan in report.plans:
        subject, predicate, obj = plan.triple
        print(
            f"  PROMOTE {plan.candidate_id} -> {plan.claim_id}: "
            f"{subject} -{predicate}-> {obj} "
            f"[{plan.claim_properties['verification_status']}] "
            f"{plan.evidence_label} {plan.evidence_properties['evidence_id']} "
            f"from {plan.source_id} {plan.chunk_id}"
            + (" (descriptive; not used by reasoning)" if plan.descriptive else "")
        )

    if not args.apply:
        print("DRY RUN: nothing was written to Neo4j. Review the plan above, "
              "then re-run with --apply.")
        return 0

    from app.db.neo4j import close_neo4j_driver

    try:
        promote(report, apply=True)
    finally:
        close_neo4j_driver()
    print(f"Applied batch {report.batch_id}: " + ", ".join(
        f"{k}={v}" for k, v in report.counters.items()))
    print("Refresh the API evidence index (POST "
          "/api/v1/c2/evidence-index/refresh) to make new evidence searchable.")
    return 0


def _cmd_retract(args) -> int:
    from app.db.source_repository import plan_retractions, retract

    from app.db.source_repository import plan_modelled_retractions
    from app.knowledge_candidates.modelled import ModelledStore

    store = _load_store(args.path)
    report = plan_retractions(store.load_candidates().values())
    report.plans.extend(plan_modelled_retractions(ModelledStore(args.path).load().values()).plans)
    print(f"Claims to retract: {len(report.plans)}")
    for plan in report.plans:
        print(f"  RETRACT {plan.claim_id} (by {plan.retracted_by}): {plan.reason}")
    if not args.apply:
        print("DRY RUN: nothing was changed in Neo4j. Retraction relabels "
              "claims (:Claim -> :RetractedClaim) and unsupported evidence "
              "(-> :RetractedEvidence); nothing is deleted.")
        return 0

    from app.db.neo4j import close_neo4j_driver

    try:
        retract(report, apply=True)
    finally:
        close_neo4j_driver()
    print(f"Applied batch {report.batch_id}: retracted "
          f"{len(report.retracted_claims)} claim(s), "
          f"{report.evidence_retracted} evidence node(s); "
          f"{len(report.not_in_graph)} not found in the graph.")
    print("Refresh the API evidence index (POST "
          "/api/v1/c2/evidence-index/refresh) so retracted evidence is dropped.")
    return 0


def _cmd_sources(args) -> int:
    from app.knowledge_ingestion.registry import load_registry

    entries = load_registry(args.registry)
    shown = [e for e in entries if not args.decision or e.decision in args.decision]
    for entry in shown:
        print(f"{entry.registry_id:7} {entry.decision:23} {entry.status:9} "
              f"{(entry.licence or '-')[:28]:28} {entry.title[:70]}")
    print(f"{len(shown)} of {len(entries)} registry entries")
    return 0


def _cmd_sources_validate(args) -> int:
    from app.knowledge_ingestion.registry import load_registry, validate_registry

    entries = load_registry(args.registry)
    problems = validate_registry(entries)
    for problem in problems:
        print(f"PROBLEM {problem}")
    print(f"{len(entries)} entries, {len(problems)} problem(s)")
    return 1 if problems else 0


def _cmd_acquire(args) -> int:
    from app.knowledge_ingestion.registry import (
        acquire, load_registry, validate_registry,
    )

    entries = load_registry(args.registry)
    problems = validate_registry(entries)
    if problems:
        for problem in problems:
            print(f"PROBLEM {problem}")
        print("Registry has problems; nothing acquired.")
        return 1
    report = acquire(entries, args.raw, apply=args.apply,
                     only=set(args.id) if args.id else None)
    for item in report.items:
        note = f" ({item.detail})" if item.detail else ""
        print(f"{item.registry_id:7} {item.state:19} {item.size_bytes:>22} "
              f"{item.target}{note}")
    if not args.apply:
        to_fetch = [i for i in report.items if i.state in {"missing", "partial"}]
        print(f"Dry run: {len(to_fetch)} file(s) would be downloaded. "
              "Re-run with --apply to download.")
        return 0
    for rid, checksum in report.recorded_checksums.items():
        print(f"RECORD {rid} sha256={checksum} (add to the registry)")
    for rid, error in report.errors.items():
        print(f"ERROR {rid}: {error}")
    print(f"Downloaded {len(report.downloaded)}, sidecars written "
          f"{len(report.sidecars_written)}, errors {len(report.errors)}.")
    if report.downloaded:
        print("Next: run 'manifest' to extract the new sources.")
    return 1 if report.errors else 0


def _cmd_ingest_report(args) -> int:
    from app.knowledge_ingestion.report import build_ingestion_report

    report = build_ingestion_report(
        args.manifest, extracted_dir=args.extracted,
        candidates_dir=args.candidates, settings=load_ingestion_settings(),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 1 if report["totals"]["validation_problem_sources"] else 0


def _find_chunk(extracted: Path, chunk_id: str):
    source_id = chunk_id.split("#chk-", 1)[0]
    path = chunks_path(extracted, source_id)
    if not path.is_file():
        raise FileNotFoundError(f"No chunks for source {source_id}; run 'chunk' first.")
    for chunk in load_chunks(path):
        if chunk.chunk_id == chunk_id:
            return chunk
    raise FileNotFoundError(f"Chunk {chunk_id} not found (re-chunked?).")


def _cmd_model_claim(args) -> int:
    from app.knowledge_candidates.models import ReviewerRole
    from app.knowledge_candidates.modelled import (
        ModelledClaimError, ModelledStore, model_claim,
    )

    chunk = _find_chunk(args.extracted, args.chunk_id)
    try:
        claim = model_claim(
            chunk, subject=args.subject, predicate=args.predicate,
            object=args.object, quote=args.quote, statement=args.statement,
            reviewer=args.reviewer, reviewer_role=ReviewerRole(args.role),
            note=args.note, models_candidate_id=args.models_candidate,
        )
        ModelledStore(args.path).add(claim)
    except ModelledClaimError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"{claim.modelled_id}: {claim.subject.concept_id} -{claim.predicate}-> "
          f"{claim.object.concept_id} from {chunk.chunk_id} "
          f"[{claim.passage.sentence_start}:{claim.passage.sentence_end}] "
          f"by {claim.created.reviewer} ({claim.created.reviewer_role.value})")
    print("Stored locally only. Promote with 'promote' (dry run first).")
    return 0


def _cmd_modelled(args) -> int:
    from app.knowledge_candidates.modelled import ModelledStore

    claims = ModelledStore(args.path).load()
    for claim in claims.values():
        refs = ", ".join(claim.passage.citation_refs[:3])
        print(f"{claim.modelled_id} [{claim.status.value}] {claim.subject.label} "
              f"--{claim.predicate}--> {claim.object.label}  "
              f"({claim.passage.source_id}{'; ' + refs if refs else ''}) "
              f"by {claim.created.reviewer}")
        if args.show_quote:
            print(f'    "{claim.passage.sentence}"')
            print(f"    statement: {claim.statement}")
    print(f"{len(claims)} modelled claim(s)")
    return 0


def _cmd_withdraw_modelled(args) -> int:
    from app.knowledge_candidates.models import ReviewerRole
    from app.knowledge_candidates.modelled import ModelledClaimError, ModelledStore

    try:
        claim = ModelledStore(args.path).withdraw(
            args.modelled_id, args.reviewer, ReviewerRole(args.role), args.note
        )
    except ModelledClaimError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"{claim.modelled_id}: withdrawn. Run 'retract' to stop using its graph claim.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.knowledge_ingestion",
        description=(
            "Inspect and extract local Ayurvedic source documents. "
            "Nothing is written to Neo4j."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser(
        "inspect", help="Extract in memory and print a summary (no text)."
    )
    inspect.add_argument("path", type=Path)
    inspect.add_argument(
        "--metadata", type=Path,
        help="Metadata JSON (default: '<file>.meta.json' if present).",
    )
    inspect.add_argument("--json", action="store_true",
                         help="Print the summary as JSON.")
    inspect.set_defaults(handler=_cmd_inspect)

    extract = commands.add_parser(
        "extract", help="Extract one file and write passages to --out."
    )
    extract.add_argument("path", type=Path)
    extract.add_argument("--out", type=Path, required=True,
                         help="Output directory (keep it out of Git).")
    extract.add_argument("--metadata", type=Path)
    extract.add_argument(
        "--root", type=Path,
        help="Corpus root (e.g. corpus/raw). Records the source path relative "
             "to it, as the manifest does, so --path-filter matches. Without "
             "it, only the file name is recorded.",
    )
    extract.set_defaults(handler=_cmd_extract)

    manifest = commands.add_parser(
        "manifest", help="Process a directory and write a source manifest."
    )
    manifest.add_argument("root", type=Path)
    manifest.add_argument("--out", type=Path, required=True,
                          help="Manifest JSON path.")
    manifest.add_argument(
        "--extract-dir", type=Path,
        help="Also write each source's passages to this directory.",
    )
    manifest.set_defaults(handler=_cmd_manifest)

    manifest_update = commands.add_parser(
        "manifest-update",
        help="Extract only files under the given path prefixes and merge them "
             "into an existing manifest (other records are kept as stored).",
    )
    manifest_update.add_argument("manifest", type=Path)
    manifest_update.add_argument("--root", type=Path, required=True)
    manifest_update.add_argument("--path-prefix", action="append", required=True,
                                 help="Relative path prefix under root (repeatable).")
    manifest_update.add_argument("--extract-dir", type=Path)
    manifest_update.set_defaults(handler=_cmd_manifest_update)

    status = commands.add_parser(
        "status", help="Show extraction status from a manifest file."
    )
    status.add_argument("manifest", type=Path)
    status.set_defaults(handler=_cmd_status)

    duplicates = commands.add_parser(
        "duplicates",
        help="Report identical files in a directory, or from a manifest.",
    )
    duplicates.add_argument("path", type=Path)
    duplicates.set_defaults(handler=_cmd_duplicates)

    chunk = commands.add_parser(
        "chunk",
        help="Normalize and chunk extracted passages (*.extraction.json).",
    )
    chunk.add_argument(
        "path", type=Path,
        help="An <source_id>.extraction.json file or a directory of them.",
    )
    chunk.add_argument(
        "--out", type=Path,
        help="Output directory (default: next to each extraction file).",
    )
    chunk.add_argument("--verbose", action="store_true",
                       help="Print one line per source.")
    chunk.set_defaults(handler=_cmd_chunk)

    validate = commands.add_parser(
        "validate",
        help="Check chunk files against their passages (traceability).",
    )
    validate.add_argument("path", type=Path)
    validate.set_defaults(handler=_cmd_validate)

    def add_store_args(command):
        command.add_argument(
            "--store", type=Path, required=True,
            help="Embedding store root (one subdirectory per model).",
        )
        command.add_argument(
            "--allow-download", action="store_true",
            help="Allow downloading the configured model if not cached.",
        )

    embed = commands.add_parser(
        "embed",
        help="Embed chunk files into a local vector store (incremental).",
    )
    embed.add_argument("path", type=Path,
                       help="Directory of *.extraction.json with chunks.")
    add_store_args(embed)
    embed.add_argument(
        "--path-filter", action="append",
        help="Only sources whose relative path contains this text "
             "(repeatable; a source matching any filter is included).",
    )
    embed.add_argument(
        "--exclude-source", action="append", default=[],
        help="Leave out this source_id (repeatable), e.g. a known duplicate.",
    )
    embed.add_argument("--rebuild", action="store_true",
                       help="Ignore and replace an existing store.")
    embed.set_defaults(handler=_cmd_embed)

    search = commands.add_parser(
        "search", help="Semantic search over embedded source chunks."
    )
    search.add_argument("query")
    add_store_args(search)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--script", action="append",
                        help="Filter by script code (Deva, Sinh, Latn).")
    search.add_argument("--source-id", action="append")
    search.add_argument("--max-per-source", type=int)
    search.add_argument("--include-below-threshold", action="store_true")
    search.add_argument("--snippet-chars", type=int, default=200)
    search.add_argument(
        "--exclude-flag", action="append",
        help="Skip chunks with this quality flag (repeatable), e.g. symbol_noise.",
    )
    search.set_defaults(handler=_cmd_search)

    search_eval = commands.add_parser(
        "search-eval",
        help="Hit rate and MRR over labelled retrieval cases (JSONL).",
    )
    search_eval.add_argument("cases", type=Path)
    add_store_args(search_eval)
    search_eval.add_argument("--top-k", type=int, default=10)
    search_eval.add_argument("--exclude-flag", action="append")
    search_eval.add_argument(
        "--details", action="store_true",
        help="Add per-case diagnostics: label method, labelled chunks by "
             "script and source, answerability in the query's script, and "
             "the scripts and quality flags of the hits.",
    )
    search_eval.set_defaults(handler=_cmd_search_eval)

    search_pool = commands.add_parser(
        "search-pool",
        help="Export pooled top-k results of one or more models as CSV for "
             "human relevance review (labels are never changed).",
    )
    search_pool.add_argument("cases", type=Path)
    add_store_args(search_pool)
    search_pool.add_argument("--out", type=Path, required=True,
                             help="CSV path (keep it in a git-ignored folder).")
    search_pool.add_argument(
        "--model", action="append",
        help="Model ID whose store to pool (repeatable). Default: the "
             "configured source model.",
    )
    search_pool.add_argument(
        "--system", action="append",
        help="LABEL=STORE_ROOT (repeatable): pool the configured model over "
             "several store roots, e.g. to compare corpora. Overrides --model.",
    )
    search_pool.add_argument("--top-k", type=int, default=10)
    search_pool.set_defaults(handler=_cmd_search_pool)

    review_eval = commands.add_parser(
        "review-eval",
        help="Validate human relevance judgements on pool copies and compute "
             "metrics from them only (inputs are never modified).",
    )
    review_eval.add_argument("pool", type=Path,
                             help="Original search-pool CSV (reference, unchanged).")
    review_eval.add_argument("reviews", type=Path, nargs="+",
                             help="Reviewer copies of the pool with judgements filled in.")
    review_eval.add_argument("--policy", choices=["strict", "lenient"], default="strict",
                             help="strict: only 'relevant' counts; lenient: also "
                                  "'partially_relevant'.")
    review_eval.add_argument("--k", type=int, default=10)
    review_eval.add_argument("--cases", type=Path,
                             help="Original smoke-case JSONL, to check queries match.")
    review_eval.add_argument("--out", type=Path,
                             help="Write the JSON report here (git-ignored folder).")
    review_eval.set_defaults(handler=_cmd_review_eval)

    cand_extract = commands.add_parser(
        "candidates-extract",
        help="Extract candidate claims from chunks (rule-based, offline).",
    )
    cand_extract.add_argument("path", type=Path,
                              help="Directory of *.extraction.json with chunks.")
    cand_extract.add_argument("--out", type=Path, required=True,
                              help="Candidate store directory.")
    cand_extract.add_argument("--lexicon", type=Path,
                              help="Lexicon JSON (default: knowledge/seed_lexicon_v1.json).")
    cand_extract.add_argument("--path-filter", action="append",
                              help="Relative path substring (repeatable, any match).")
    cand_extract.add_argument("--exclude-source", action="append", default=[],
                              help="Leave out this source_id (repeatable).")
    cand_extract.set_defaults(handler=_cmd_candidates_extract)

    cand_list = commands.add_parser(
        "candidates", help="List candidate claims (preview; nothing is written)."
    )
    cand_list.add_argument("path", type=Path)
    cand_list.add_argument("--status", action="append",
                           help="candidate, uncertain, needs_more_sources, approved, rejected, superseded")
    cand_list.add_argument("--predicate", action="append")
    cand_list.add_argument("--concept", action="append", help="Concept ID, e.g. R-PANDU.")
    cand_list.add_argument("--include-stale", action="store_true")
    cand_list.add_argument("--show-sentence", action="store_true")
    cand_list.add_argument("--limit", type=int, default=20)
    cand_list.set_defaults(handler=_cmd_candidates)

    review = commands.add_parser(
        "review", help="Record a review decision for one candidate."
    )
    review.add_argument("path", type=Path)
    review.add_argument("claim_id")
    review.add_argument(
        "--status", required=True,
        choices=["approved", "rejected", "uncertain", "needs_more_sources", "superseded"],
    )
    review.add_argument("--reviewer", required=True)
    review.add_argument("--role", required=True, choices=["practitioner", "researcher"])
    review.add_argument("--note")
    review.add_argument("--source-id", action="append",
                        help="Additional corroborating source ID (repeatable).")
    review.add_argument("--superseded-by")
    review.add_argument("--acknowledge-conflicts", action="store_true")
    review.set_defaults(handler=_cmd_review)

    conflicts = commands.add_parser("conflicts", help="List detected conflicts.")
    conflicts.add_argument("path", type=Path)
    conflicts.add_argument("--open-only", action="store_true")
    conflicts.set_defaults(handler=_cmd_conflicts)

    source_schema = commands.add_parser(
        "source-schema",
        help="Show (or with --apply create) the additive Stage E constraints.",
    )
    source_schema.add_argument("--apply", action="store_true",
                               help="Actually create them in Neo4j.")
    source_schema.set_defaults(handler=_cmd_source_schema)

    promote_cmd = commands.add_parser(
        "promote",
        help="Plan (or with --apply write) approved candidates into Neo4j.",
    )
    promote_cmd.add_argument("path", type=Path, help="Candidate store directory.")
    promote_cmd.add_argument("--extracted", type=Path, required=True,
                             help="Directory with *.extraction.json and chunks.")
    promote_cmd.add_argument(
        "--manifest", type=Path,
        help="Manifest for source_id conflict checks "
             "(default: <extracted>/manifest.json).",
    )
    promote_cmd.add_argument("--apply", action="store_true",
                             help="Write to Neo4j (default is a dry run).")
    promote_cmd.set_defaults(handler=_cmd_promote)

    retract_cmd = commands.add_parser(
        "retract",
        help="Plan (or with --apply perform) non-destructive retraction of "
             "promoted claims whose approval was withdrawn.",
    )
    retract_cmd.add_argument("path", type=Path, help="Candidate store directory.")
    retract_cmd.add_argument("--apply", action="store_true",
                             help="Relabel in Neo4j (default is a dry run).")
    retract_cmd.set_defaults(handler=_cmd_retract)

    model_cmd = commands.add_parser(
        "model-claim",
        help="Record a reviewer-modelled ontology claim from an exact quote "
             "(local only; nothing is written to Neo4j).",
    )
    model_cmd.add_argument("path", type=Path, help="Candidate store directory.")
    model_cmd.add_argument("--extracted", type=Path, required=True)
    model_cmd.add_argument("--chunk-id", required=True)
    model_cmd.add_argument("--quote", required=True,
                           help="Exact text from the chunk's normalized text (must occur once).")
    model_cmd.add_argument("--subject", required=True, help="Type:ID:Label")
    model_cmd.add_argument("--predicate", required=True)
    model_cmd.add_argument("--object", required=True, help="Type:ID:Label")
    model_cmd.add_argument("--statement", required=True,
                           help="Your wording of what the passage states.")
    model_cmd.add_argument("--reviewer", required=True)
    model_cmd.add_argument("--role", choices=["practitioner", "researcher"], required=True)
    model_cmd.add_argument("--note", required=True,
                           help="Why the passage supports this claim.")
    model_cmd.add_argument("--models-candidate",
                           help="Candidate ID this claim models (optional).")
    model_cmd.set_defaults(handler=_cmd_model_claim)

    modelled_cmd = commands.add_parser("modelled", help="List reviewer-modelled claims.")
    modelled_cmd.add_argument("path", type=Path)
    modelled_cmd.add_argument("--show-quote", action="store_true")
    modelled_cmd.set_defaults(handler=_cmd_modelled)

    withdraw_cmd = commands.add_parser(
        "withdraw-modelled", help="Withdraw a modelled claim (never deleted).")
    withdraw_cmd.add_argument("path", type=Path)
    withdraw_cmd.add_argument("modelled_id")
    withdraw_cmd.add_argument("--reviewer", required=True)
    withdraw_cmd.add_argument("--role", choices=["practitioner", "researcher"], required=True)
    withdraw_cmd.add_argument("--note", required=True)
    withdraw_cmd.set_defaults(handler=_cmd_withdraw_modelled)

    sources = commands.add_parser("sources", help="List source registry entries.")
    sources.add_argument("registry", type=Path)
    sources.add_argument("--decision", action="append",
                         help="Only show this decision (repeatable).")
    sources.set_defaults(handler=_cmd_sources)

    sources_validate = commands.add_parser(
        "sources-validate", help="Check the source registry for problems.")
    sources_validate.add_argument("registry", type=Path)
    sources_validate.set_defaults(handler=_cmd_sources_validate)

    acquire_cmd = commands.add_parser(
        "acquire",
        help="Plan (or with --apply perform) checksum-verified downloads of "
             "included registry sources.",
    )
    acquire_cmd.add_argument("registry", type=Path)
    acquire_cmd.add_argument("--raw", type=Path, required=True,
                             help="Corpus raw directory, e.g. corpus/raw.")
    acquire_cmd.add_argument("--id", action="append",
                             help="Only this registry_id (repeatable).")
    acquire_cmd.add_argument("--apply", action="store_true",
                             help="Download (default is a dry run).")
    acquire_cmd.set_defaults(handler=_cmd_acquire)

    ingest_report = commands.add_parser(
        "ingest-report",
        help="Summarize processed, skipped, rejected, duplicated and "
             "validated sources (counts only, no text).",
    )
    ingest_report.add_argument("manifest", type=Path)
    ingest_report.add_argument("--extracted", type=Path,
                               help="Directory with *.chunks.jsonl to validate.")
    ingest_report.add_argument("--candidates", type=Path,
                               help="Candidate store directory.")
    ingest_report.add_argument("--out", type=Path)
    ingest_report.set_defaults(handler=_cmd_ingest_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (
        FileNotFoundError, NotADirectoryError, SourceMetadataError,
        SourceOutsideRootError,
    ) as exc:
        print(f"ERROR: {exc}")
        return 2
    except ValueError as exc:
        # Raised by read_manifest() for files that are not valid manifests.
        print(f"ERROR: input is not a valid manifest ({type(exc).__name__}).")
        return 2
    except RuntimeError as exc:
        # Embedding model unavailable, or an embedding store problem. The
        # messages name the model or store, never chunk text.
        print(f"ERROR: {exc}")
        return 3
