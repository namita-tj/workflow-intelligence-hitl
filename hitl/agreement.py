"""Agreement between reviews in the ledger.

Two questions the thesis left open (Section 6.2, "Consensus across Multiple Reviewers"):

1. Disagreement: has the same finding been confirmed by one review and rejected by another?
   Before, both entries were simply kept and nobody was told.
2. Agreement across several reviewers: when a group of reviewers each reviews the same
   findings independently, how far does their agreement exceed chance? Measured with
   Fleiss' kappa (Fleiss, 1971), which works for any number of reviewers.

A "finding" is identified the same way as for prior-review lookups in ledger.py:
teammate + finding type, plus the metric for rule breaches. When one reviewer reviewed the
same finding more than once, only their latest decision counts.
"""

from collections import Counter, defaultdict
from typing import Iterable, Optional

CATEGORIES = ("confirm", "reject")


def finding_key(entry: dict) -> tuple:
    """(teammate_id, finding_type, metric or None) for a ledger entry or a normalized finding."""
    metric = entry.get("metric")
    if metric is None:
        metric = (entry.get("finding_summary") or {}).get("metric")
    if entry.get("finding_type") != "rule_breach":
        metric = None
    return entry.get("teammate_id"), entry.get("finding_type"), metric


def latest_decisions(entries: Iterable[dict]) -> dict:
    """{finding_key: {reviewer: decision}}, keeping each reviewer's latest decision.
    Ledger entries are in the order they were written, so later entries win."""
    out: dict = defaultdict(dict)
    for e in entries:
        if e.get("decision") in CATEGORIES:
            out[finding_key(e)][e.get("reviewer") or "unknown"] = e["decision"]
    return dict(out)


def conflicting_prior(current_decision: str, prior_reviews: Optional[list]) -> list[dict]:
    """Prior reviews of the same finding whose decision differs from the current one."""
    return [p for p in (prior_reviews or []) if p.get("decision") in CATEGORIES and p["decision"] != current_decision]


def find_disagreements(entries: Iterable[dict]) -> list[dict]:
    """Findings that have been both confirmed and rejected (by anyone, at any time)."""
    by_key: dict = defaultdict(list)
    for e in entries:
        if e.get("decision") in CATEGORIES:
            by_key[finding_key(e)].append(e)
    out = []
    for key, reviews in by_key.items():
        decisions = {r["decision"] for r in reviews}
        if len(decisions) > 1:
            out.append({
                "teammate_id": key[0], "finding_type": key[1], "metric": key[2],
                "reviews": [{"reviewer": r.get("reviewer"), "decision": r["decision"],
                             "timestamp": r.get("timestamp"), "annotation": r.get("annotation")}
                            for r in reviews],
            })
    return out


def fleiss_kappa(counts: list[list[int]]) -> Optional[float]:
    """Fleiss' kappa for a table with one row per item and one column per category,
    each cell the number of raters who chose that category for that item.

    Items may have different numbers of raters (each needs at least 2). Returns None
    when kappa is undefined: no usable items, or every rating in one category
    (chance agreement is then 1).
    """
    rows = [r for r in counts if sum(r) >= 2]
    if not rows:
        return None
    total = sum(sum(r) for r in rows)
    k = len(rows[0])
    p_j = [sum(r[j] for r in rows) / total for j in range(k)]
    p_i = [(sum(c * c for c in r) - sum(r)) / (sum(r) * (sum(r) - 1)) for r in rows]
    p_bar = sum(p_i) / len(p_i)
    p_e = sum(p * p for p in p_j)
    if p_e == 1:
        return None
    return (p_bar - p_e) / (1 - p_e)


def agreement_report(entries: Iterable[dict], min_reviewers: int = 2) -> dict:
    """Fleiss' kappa and raw agreement over the findings reviewed by at least
    ``min_reviewers`` different reviewers, using each reviewer's latest decision."""
    entries = list(entries)
    decisions = latest_decisions(entries)
    items = {k: v for k, v in decisions.items() if len(v) >= max(2, min_reviewers)}
    table = [[Counter(v.values())[c] for c in CATEGORIES] for v in items.values()]
    unanimous = sum(1 for row in table if max(row) == sum(row))
    return {
        "findings_with_multiple_reviewers": len(items),
        "reviewers": sorted({r for v in items.values() for r in v}),
        "unanimous": unanimous,
        "fleiss_kappa": fleiss_kappa(table),
        "disagreements": find_disagreements(entries),
    }


def interpret_kappa(kappa: Optional[float]) -> str:
    """Landis & Koch (1977) labels, the usual rough guide."""
    if kappa is None:
        return "undefined"
    for bound, label in ((0.0, "poor"), (0.20, "slight"), (0.40, "fair"), (0.60, "moderate"),
                         (0.80, "substantial")):
        if kappa <= bound:
            return label
    return "almost perfect"


__all__ = [
    "finding_key", "latest_decisions", "conflicting_prior", "find_disagreements",
    "fleiss_kappa", "agreement_report", "interpret_kappa",
]
