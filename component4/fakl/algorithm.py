"""FAKL — Federated Ayurvedic Knowledge Learning (prototype algorithm, proposal SO3).

Goal: update the confidence of knowledge-graph claims (e.g. "pallor indicates
Pitta imbalance") from practitioner feedback at several clinics, WITHOUT any
clinic sharing its feedback records.

How it works
1. Each claim's current confidence acts like PRIOR_STRENGTH earlier votes:
   confidence 0.7 with strength 10 counts as 7 "agree" and 3 "disagree".
2. Local step (at each clinic): count its practitioners' agree / disagree votes
   per claim. Only these two counts per claim leave the clinic.
3. Privacy (at each clinic, before sharing):
   - optional differential privacy: add Laplace noise to each count, and
   - suppression: do not share a claim the clinic has too few votes on.
4. Federated step (server): add up the clinics' counts per claim and update
       new confidence = (prior agrees + all agrees) / (prior votes + all votes)
   Adding counts = weighting each clinic by how much feedback it gave (FedAvg-style).

Because only counts are combined, federation WITHOUT privacy gives exactly the
same result as pooling all feedback centrally; the privacy steps then trade a
little accuracy for protection, which run_fakl.py measures.
"""

import numpy as np

PRIOR_STRENGTH = 10   # how many votes the existing confidence is worth


def count_votes(feedback):
    """Per-claim (agree, disagree) counts from feedback records.

    Each record: {"claim_id": ..., "review_outcome": "agree" | "disagree" | ...}.
    "uncertain" and "needs_more_evidence" (Component 2's other outcomes) are
    neutral: they neither raise nor lower a claim's confidence.
    """
    counts = {}
    for record in feedback:
        agree, disagree = counts.get(record["claim_id"], (0, 0))
        if record["review_outcome"] == "agree":
            agree += 1
        elif record["review_outcome"] == "disagree":
            disagree += 1
        counts[record["claim_id"]] = (agree, disagree)
    return counts


def local_update(feedback, min_votes=0, epsilon=None, rng=None):
    """Runs AT A CLINIC. Returns the only thing that leaves it:
    {claim_id: (agree_count, disagree_count)}, possibly noisy, small counts suppressed.

    epsilon: if given, Laplace noise with scale 1/epsilon is added to each count.
             Assuming each practitioner gives at most one vote per claim, one vote
             changes one count by 1, so this is epsilon-differentially private per claim.
    min_votes: claims with fewer (noisy) votes than this are not shared at all.
               The decision uses the NOISY total, so it does not leak the true count.
    """
    share = {}
    for claim_id, (agree, disagree) in count_votes(feedback).items():
        if epsilon is not None:
            agree = max(0.0, agree + rng.laplace(0.0, 1.0 / epsilon))
            disagree = max(0.0, disagree + rng.laplace(0.0, 1.0 / epsilon))
        if agree + disagree < min_votes:
            continue   # suppressed: too little evidence to share safely
        share[claim_id] = (float(agree), float(disagree))
    return share


def updated_confidence(prior, agree, disagree, strength=PRIOR_STRENGTH):
    """Prior confidence acts as `strength` votes; add the new votes; return the new share of agrees."""
    return (prior * strength + agree) / (strength + agree + disagree)


def federated_update(claims, clinic_shares, strength=PRIOR_STRENGTH):
    """Runs AT THE SERVER. claims: {claim_id: prior confidence};
    clinic_shares: list of local_update() outputs. Returns {claim_id: new confidence}."""
    totals = {claim_id: [0.0, 0.0] for claim_id in claims}
    for share in clinic_shares:
        for claim_id, (agree, disagree) in share.items():
            if claim_id in totals:            # ignore claims the graph does not have
                totals[claim_id][0] += agree
                totals[claim_id][1] += disagree
    return {claim_id: updated_confidence(claims[claim_id], a, d, strength)
            for claim_id, (a, d) in totals.items()}


def centralised_update(claims, all_feedback, strength=PRIOR_STRENGTH):
    """Baseline that FAKL avoids: pool every clinic's raw feedback in one place."""
    counts = count_votes(all_feedback)
    return {claim_id: updated_confidence(prior, *counts.get(claim_id, (0, 0)), strength)
            for claim_id, prior in claims.items()}


def mean_abs_difference(a, b):
    """Average absolute gap between two {claim_id: confidence} results."""
    return float(np.mean([abs(a[c] - b[c]) for c in a]))
