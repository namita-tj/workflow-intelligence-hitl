"""Ledger and pipeline orchestration — the final HITL component.

Orchestrates the complete pipeline (normalize → explain → review → persist)
and maintains an append-only ledger of reviewed findings. This is the
Externalization artifact — where tacit manager judgment becomes explicit,
recorded organizational memory.

Fixes the bug found in manual testing 2026-08-17: normalize exactly once,
thread the same object through both explain_finding() and review_finding().
"""

import json
from datetime import datetime, timezone
from typing import Optional

from hitl.explanation_layer import normalize_finding, explain_finding
from hitl.review import review_finding


def process_finding(
    raw_finding: dict,
    backend: str = "ollama",
    backend_kwargs: Optional[dict] = None,
    reviewer: Optional[str] = None,
    input_fn=None,
    ledger_path: str = "ledger.jsonl",
    prompt_style: str = "original",
) -> dict:
    """
    Complete HITL pipeline: normalize once, explain, review, persist to ledger.

    This is the fix for the bug found in manual testing where explain_finding()
    and review_finding() received differently-shaped input because nothing
    normalized once and threaded the result through both.

    Parameters
    ----------
    raw_finding : dict
        Raw detector output (rule_breach or anomaly schema).
    backend : str
        LLM backend for explanation ("ollama" or "google_ai").
    backend_kwargs : Optional[dict]
        Additional arguments for the LLM backend.
    reviewer : Optional[str]
        Reviewer name. If None, prompted during review.
    input_fn : Optional[Callable]
        Input function for review interaction. Defaults to builtin input().
    ledger_path : str
        Path to the JSON Lines ledger file.
    prompt_style : str
        "original" (default, fully covered by this thesis's RQ2 test suite)
        or "two_part" (experimental alternative — see explain_finding()).

    Returns
    -------
    dict
        The final reviewed record, now persisted in the ledger.
        Same structure as review_finding() output.
    """
    backend_kwargs = backend_kwargs or {}
    if input_fn is None:
        input_fn = input

    # 1. Normalize once — this normalized object flows through both steps
    normalized_finding = normalize_finding(raw_finding)

    # 2. Explain — uses the normalized finding
    explanation = explain_finding(
        normalized_finding,
        backend=backend,
        backend_kwargs=backend_kwargs,
        prompt_style=prompt_style,
    )

    # 3. Look up prior reviews of this exact finding, if any — shown to the
    #    reviewer as context (Section on recurring findings), never used to
    #    skip or auto-resolve the review itself.
    prior_reviews = find_prior_reviews(
        teammate_id=normalized_finding.get("teammate_id"),
        finding_type=normalized_finding.get("finding_type"),
        metric=normalized_finding.get("metric"),
        ledger_path=ledger_path,
    )

    # 4. Review — also uses the normalized finding (not raw, not re-derived)
    review_result = review_finding(
        normalized_finding,
        explanation=explanation,
        input_fn=input_fn,
        reviewer=reviewer,
        prior_reviews=prior_reviews,
    )

    # 5. Persist — append to ledger
    append_to_ledger(review_result, path=ledger_path)

    return review_result


def find_prior_reviews(
    teammate_id: str,
    finding_type: str,
    metric: Optional[str] = None,
    ledger_path: str = "ledger.jsonl",
) -> list[dict]:
    """
    Look up any prior ledger entries matching this teammate and finding.

    For rule_breach findings, matches on teammate_id + finding_type + metric
    (since the same teammate can have multiple different metric breaches).
    For anomaly findings, matches on teammate_id + finding_type alone.

    This does NOT skip or auto-resolve the review — it only surfaces prior
    history as context for the human reviewer, who still makes a fresh
    decision every time. This is a deliberate design choice: automatically
    reapplying a past decision would remove the human judgement step this
    thesis's design otherwise treats as essential (Section 3.8.4), and risks
    missing a genuine change in circumstance since the prior review.

    Parameters
    ----------
    teammate_id : str
    finding_type : str
        'rule_breach' or 'anomaly'.
    metric : Optional[str]
        Required to match specifically for rule_breach findings; ignored
        for anomaly findings.
    ledger_path : str
        Path to the JSON Lines ledger file.

    Returns
    -------
    list[dict]
        All matching prior entries, in the order they appear in the ledger
        (oldest first). Empty list if none found or if the ledger does
        not yet exist.
    """
    try:
        entries = load_ledger(ledger_path)
    except FileNotFoundError:
        return []

    matches = []
    for entry in entries:
        if entry.get("teammate_id") != teammate_id:
            continue
        if entry.get("finding_type") != finding_type:
            continue
        if finding_type == "rule_breach":
            entry_metric = entry.get("finding_summary", {}).get("metric")
            if entry_metric != metric:
                continue
        matches.append(entry)

    return matches


def append_to_ledger(record: dict, path: str = "ledger.jsonl") -> None:
    """
    Append one reviewed record as a JSON Line to the ledger.

    This is append-only by design and enforcement:
    - Always opens in "a" (append) mode, never "w" (write/overwrite)
    - Maintains a true historical record, not a mutable snapshot

    Parameters
    ----------
    record : dict
        One complete reviewed finding record (output of review_finding()).
    path : str
        Path to the JSON Lines ledger file.

    Notes
    -----
    Duplicate entries are allowed — each review is its own timestamped event.
    If the same finding is reviewed twice over time, both records persist.
    """
    # Ensure we're always appending, never overwriting
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_ledger(path: str = "ledger.jsonl") -> list[dict]:
    """
    Load the entire ledger history from a JSON Lines file.

    Parameters
    ----------
    path : str
        Path to the JSON Lines ledger file.

    Returns
    -------
    list[dict]
        List of all reviewed records, in order of appearance.

    Notes
    -----
    If the file does not exist, returns an empty list (not an error).
    """
    try:
        with open(path, "r") as f:
            records = [json.loads(line) for line in f if line.strip()]
        return records
    except FileNotFoundError:
        return []


__all__ = ["process_finding", "append_to_ledger", "load_ledger"]