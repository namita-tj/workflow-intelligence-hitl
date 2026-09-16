"""
Quality metrics tracking for the explanation layer's LLM outputs.

Extends the one-time 30-call soft-recommendation evaluation (Section 4.6)
into an ongoing, per-call quality log, so recommendation-language rate and
potential hallucinations can be tracked systematically over time, rather
than only measured in a single evaluation script.

Two metrics are tracked per response:

1. Recommendation-language rate — reuses the same detection patterns
   already validated in two_part_prompt_evaluation.py.

2. Potential hallucination — for rule_breach findings, a HEURISTIC check
   for whether the response names a metric OTHER than the one actually
   provided, as if it too had breached a threshold. This is a real,
   documented limitation, not a definitive hallucination detector: it
   catches one specific, checkable pattern (naming the wrong metric as
   breached) and will not catch other hallucination forms (e.g. inventing
   a plausible-sounding but false causal explanation using the CORRECT
   metric name). Treat this as a lower-bound estimate, not a complete
   measure, consistent with the same honesty standard applied to
   validate_response()'s own documented limitations.
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

RECOMMENDATION_PATTERNS = [
    r"\bshould\b", r"\brecommend", r"\bneeds? to\b", r"\bimportant (that|for)\b",
    r"\bmust\b", r"\bought to\b", r"\bit is (essential|critical|necessary)\b",
]

# Known metric names this system's rule-based detector actually checks
# (Section 3.8.1 THRESHOLDS). Used only for the hallucination heuristic below.
KNOWN_METRICS = [
    "ETA Achievement", "Rework Rate", "Meeting Overhead Ratio",
    "Idle Rate", "Effective Utilisation",
]


def has_recommendation_language(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in RECOMMENDATION_PATTERNS)


def has_potential_hallucination(text: str, normalized_finding: dict) -> bool:
    """
    Heuristic check: for a rule_breach finding, does the response mention a
    DIFFERENT known metric than the one actually provided, worded as if it
    were also breached? A bare mention of another metric's name in passing
    (e.g. contrasting it) is not flagged — only mention alongside breach-
    indicating language ("breach", "exceeded", "above", "below threshold").

    Returns False for anomaly findings — this heuristic is only defined
    for rule_breach, since anomaly findings have no single "correct metric"
    to hallucinate away from.
    """
    if normalized_finding.get("finding_type") != "rule_breach":
        return False

    actual_metric = normalized_finding.get("metric")
    text_lower = text.lower()
    breach_indicator = re.search(r"\b(breach|exceed|above|below|threshold)\b", text_lower)
    if not breach_indicator:
        return False

    for metric in KNOWN_METRICS:
        if metric == actual_metric:
            continue
        if metric.lower() in text_lower:
            return True
    return False


def log_quality_metrics(
    llm_response: Optional[str],
    normalized_finding: dict,
    metrics_path: str = "quality_metrics.jsonl",
) -> dict:
    """
    Compute and append one quality-metrics record for a single LLM response.

    Parameters
    ----------
    llm_response : Optional[str]
        The raw LLM response, or None if the LLM was unavailable / fallback
        was triggered (recorded as such, not skipped).
    normalized_finding : dict
        Output of normalize_finding().
    metrics_path : str
        Path to the JSON Lines metrics log.

    Returns
    -------
    dict
        The record that was logged.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "teammate_id": normalized_finding.get("teammate_id"),
        "finding_type": normalized_finding.get("finding_type"),
        "llm_available": llm_response is not None,
        "has_recommendation_language": None,
        "has_potential_hallucination": None,
    }

    if llm_response is not None:
        record["has_recommendation_language"] = has_recommendation_language(llm_response)
        record["has_potential_hallucination"] = has_potential_hallucination(
            llm_response, normalized_finding
        )

    try:
        with open(metrics_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # metrics logging must never break the actual pipeline

    return record


def load_quality_metrics(metrics_path: str = "quality_metrics.jsonl") -> list[dict]:
    """Load the full quality-metrics history. Empty list if none logged yet."""
    try:
        with open(metrics_path, "r") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def summarize_quality_metrics(records: list[dict]) -> dict:
    """Compute aggregate rates from a list of quality-metrics records,
    matching the same reporting format as the original 30-call evaluation."""
    available = [r for r in records if r["llm_available"]]
    n = len(available)
    if n == 0:
        return {"n_total": len(records), "n_available": 0}

    n_rec = sum(1 for r in available if r["has_recommendation_language"])
    n_hall = sum(1 for r in available if r["has_potential_hallucination"])

    return {
        "n_total": len(records),
        "n_available": n,
        "recommendation_language_rate": round(n_rec / n, 3),
        "potential_hallucination_rate": round(n_hall / n, 3),
    }