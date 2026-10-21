"""Optional LLM rephrasing of the deterministic, evidence-grounded explanation.

The LLM only rewrites existing explanation statements (from
app.reasoning.explanation) into plainer language. It never adds
statements. Every rephrased statement is checked and, if any check fails,
the deterministic text is kept instead:

- every claim/evidence/concept ID in the source text must still appear,
  and no other ID may appear;
- no number may appear that is not in the source text (no invented doses);
- no unsafe phrasing (diagnosis, prescription, dosage, efficacy promise)
  that the source text does not already contain;
- claim_ids and evidence_ids are always copied from the source statement,
  never taken from the model;
- statements that rest on provisional records always start with the exact
  label "Unverified — practitioner review pending", applied in code.

Without a client (or when the call fails) the deterministic statements are
returned unchanged, still labelled.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.llm.client import LLMClient, LLMRequestError
from app.llm.grounding import (
    NUMBER_PATTERN,
    PROVISIONAL_LABEL,
    extract_ids,
    parse_json_object,
    unsafe_phrases,
    with_provisional_label,
)
from app.models.c2_output import Component2Output, ExplanationStatement

BATCH_SIZE = 15

SYSTEM_PROMPT = f"""You rewrite explanation statements from an Ayurvedic knowledge-graph \
decision-support system into plain English for a practitioner. Rules:
- Rewrite each statement on its own. Do not add facts, herbs, sources, numbers, doses, \
benefits or advice that are not in that statement. Do not merge or drop statements.
- Copy every identifier in square brackets or of the form ABC-XYZ exactly as written.
- Never state or imply a diagnosis, prescription, dose, or that anything is safe or effective.
- Statements marked provisional rely on unverified drafts; keep that clear (the label \
"{PROVISIONAL_LABEL}" is added automatically).
Answer with one JSON object: {{"statements": [{{"index": number, "text": string}}]}}."""


class GroundedStatement(BaseModel):
    index: int
    kind: str
    text: str
    source_text: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    provisional: bool = False
    rephrased: bool = False
    rejection_reason: str | None = None


class GroundedExplanation(BaseModel):
    status: Literal["rephrased", "partially_rephrased", "deterministic_only", "llm_unavailable"]
    provider: str | None = None
    served_model: str | None = None
    statements: list[GroundedStatement]
    notice: str = (
        "Plain-language rephrasing of the deterministic explanation. It adds no "
        "knowledge; claim and evidence IDs are copied from the source statements."
    )


def provisional_ids(output: Component2Output) -> set[str]:
    """Claim and evidence IDs that are provisional research records."""
    ids: set[str] = set()
    for candidate in output.candidates:
        for path in candidate.paths:
            for claim in path.claims:
                if claim.knowledge_status == "provisional":
                    ids.add(claim.claim_id)
                for ref in claim.supporting_evidence + claim.contradicting_evidence + claim.qualifying_evidence:
                    if ref.knowledge_status == "provisional":
                        ids.add(ref.evidence_id)
    ids.update(
        item.evidence_id for item in output.retrieved_evidence
        if item.knowledge_status == "provisional"
    )
    return ids


def source_statements(output: Component2Output) -> list[ExplanationStatement]:
    """Request-level and per-candidate statements, without duplicates."""
    seen, statements = set(), []
    for statement in output.explanation + [s for c in output.candidates for s in c.rationale]:
        key = (statement.kind, statement.text)
        if key not in seen:
            seen.add(key)
            statements.append(statement)
    return statements


def check_rephrasing(source: str, candidate: str, allowed_ids: set[str]) -> str | None:
    """Reason the rephrasing is rejected, or None if it passes."""
    text = candidate.strip()
    if not text:
        return "empty"
    if len(text) > max(3 * len(source), 600):
        return "too_long"
    found = extract_ids(text)
    missing = extract_ids(source) - found
    if missing:
        return "missing_ids:" + ",".join(sorted(missing))
    added = found - extract_ids(source) - allowed_ids
    if added:
        return "added_ids:" + ",".join(sorted(added))
    # Digits inside IDs are not numbers in the sense of facts.
    bare_text, bare_source = text, source
    for identifier in found:
        bare_text = bare_text.replace(identifier, " ")
    for identifier in extract_ids(source):
        bare_source = bare_source.replace(identifier, " ")
    added_numbers = (
        set(NUMBER_PATTERN.findall(bare_text)) - set(NUMBER_PATTERN.findall(bare_source))
    )
    if added_numbers:
        return "added_numbers:" + ",".join(sorted(added_numbers))
    added_unsafe = set(unsafe_phrases(text)) - set(unsafe_phrases(source))
    if added_unsafe:
        return "unsafe_phrasing:" + ",".join(sorted(added_unsafe))
    return None


def explain_output(output: Component2Output, client: LLMClient | None = None) -> GroundedExplanation:
    provisional = provisional_ids(output)
    statements = []
    for index, statement in enumerate(source_statements(output)):
        is_provisional = bool(provisional & set(statement.claim_ids + statement.evidence_ids))
        statements.append(GroundedStatement(
            index=index,
            kind=statement.kind,
            source_text=statement.text,
            text=with_provisional_label(statement.text) if is_provisional else statement.text,
            claim_ids=list(statement.claim_ids),
            evidence_ids=list(statement.evidence_ids),
            provisional=is_provisional,
        ))
    if client is None or not statements:
        return GroundedExplanation(status="deterministic_only", statements=statements)

    # Small batches keep each answer well inside max_tokens; one answer for
    # ~100 statements would be cut off and every rewrite lost.
    rewrites: dict[int, str] = {}
    response = None
    batches = [statements[i:i + BATCH_SIZE] for i in range(0, len(statements), BATCH_SIZE)]
    failed_batches = 0
    for batch in batches:
        prompt = "Statements to rewrite:\n" + json.dumps(
            [{"index": s.index, "text": s.source_text, "provisional": s.provisional} for s in batch],
            ensure_ascii=False, indent=1,
        )
        try:
            response = client.complete(SYSTEM_PROMPT, prompt)
        except LLMRequestError:
            failed_batches += 1
            continue
        wanted = {s.index for s in batch}
        parsed = parse_json_object(response.text) or {}
        for item in parsed.get("statements") or []:
            if (isinstance(item, dict) and item.get("index") in wanted
                    and isinstance(item.get("text"), str)):
                rewrites.setdefault(item["index"], item["text"])
    if failed_batches == len(batches):
        return GroundedExplanation(
            status="llm_unavailable", provider=client.settings.provider, statements=statements
        )

    for statement in statements:
        rewrite = rewrites.get(statement.index)
        if rewrite is None:
            statement.rejection_reason = "not_returned"
            continue
        allowed = set(statement.claim_ids + statement.evidence_ids)
        reason = check_rephrasing(statement.source_text, rewrite, allowed)
        if reason:
            statement.rejection_reason = reason
            continue
        statement.text = with_provisional_label(rewrite) if statement.provisional else rewrite.strip()
        statement.rephrased = True

    rephrased = sum(s.rephrased for s in statements)
    status = (
        "rephrased" if rephrased == len(statements)
        else "partially_rephrased" if rephrased
        else "deterministic_only"
    )
    return GroundedExplanation(
        status=status,
        provider=client.settings.provider,
        served_model=response.served_model if response else None,
        statements=statements,
    )
