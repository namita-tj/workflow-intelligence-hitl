"""
Two-part prompt design for the explanation layer — an alternative to the
original single-block prompt, kept in a separate module so both can be
tested against the same live findings without modifying existing code.

Part 1: Statistical description (same factual content as the original).
Part 2: Knowledge-hypothesis questions — open questions for the human
        expert, rather than a directive or recommendation. Intended to
        more directly operationalize Polanyi's tacit-knowledge framework:
        rather than telling the reviewer what to conclude, it asks the
        specific kind of question that might help surface tacit knowledge
        the expert already holds but has not previously needed to state.
"""

from typing import Optional


def build_two_part_prompt(normalized_finding: dict) -> str:
    """Build a two-part explanation prompt from a normalized finding.

    Args:
        normalized_finding: A dict as produced by
            hitl.explanation_layer.normalize_finding(). Must contain
            'finding_type' ('rule_breach' or 'anomaly') and 'teammate_id'.
            For 'rule_breach': also requires 'metric', 'value', 'benchmark'.
            For 'anomaly': also requires 'cluster_label', 'is_noise'.

    Returns:
        A two-part prompt string ready for LLM submission.

    Raises:
        ValueError: if finding_type is missing, unrecognized, or if
            required fields for that finding_type are absent.
    """
    if not isinstance(normalized_finding, dict):
        raise ValueError(f"Expected dict, got {type(normalized_finding)}")

    finding_type = normalized_finding.get("finding_type")
    teammate_id = normalized_finding.get("teammate_id")

    if teammate_id is None:
        raise ValueError("normalized_finding is missing required field 'teammate_id'")

    if finding_type == "rule_breach":
        metric = normalized_finding.get("metric")
        value = normalized_finding.get("value")
        benchmark = normalized_finding.get("benchmark")

        if metric is None or value is None or benchmark is None:
            raise ValueError(
                f"rule_breach finding for {teammate_id} is missing one of "
                f"'metric', 'value', 'benchmark' (got metric={metric}, "
                f"value={value}, benchmark={benchmark})"
            )

        ratio_str = _format_ratio(value, benchmark)

        statistical_part = f"""Part 1 — Statistical description:
State only the following facts, with no interpretation:
- Teammate: {teammate_id}
- Metric: {metric}
- Observed: {value}
- Benchmark: {benchmark}
- Deviation: {ratio_str} from benchmark"""

    elif finding_type == "anomaly":
        cluster_label = normalized_finding.get("cluster_label")
        is_noise = normalized_finding.get("is_noise")

        if is_noise is None:
            raise ValueError(
                f"anomaly finding for {teammate_id} is missing required field 'is_noise'"
            )

        noise_str = "yes (outlier)" if is_noise else f"no (cluster {cluster_label})"

        statistical_part = f"""Part 1 — Statistical description:
State only the following facts, with no interpretation:
- Teammate: {teammate_id}
- Flagged as noise/outlier: {noise_str}"""

    else:
        raise ValueError(
            f"Unknown finding_type: {finding_type!r} for teammate {teammate_id}. "
            f"Expected 'rule_breach' or 'anomaly'."
        )

    knowledge_hypothesis_part = """
Part 2 — Knowledge-hypothesis questions:
Do not answer these yourself. Pose 1-2 open questions for the human expert
reviewing this finding, in the following style:
- What domain-specific knowledge might explain this pattern?
- Is this pattern consistent with what you observe in this person's work?
- Is there a specific approach or habit this person uses that others do not?

Guidelines:
1. Part 1 must contain no interpretation, no conclusion, no recommendation.
2. Part 2 must consist only of genuine open questions — not a disguised
   recommendation phrased as a question (e.g. "Have you considered
   investigating further?" is NOT acceptable).
3. Do not answer the questions yourself.
4. Total response: 3-4 sentences maximum."""

    return statistical_part + "\n" + knowledge_hypothesis_part


def _format_ratio(value: float, benchmark: float) -> str:
    """Format the deviation ratio between an observed value and its benchmark.
    Returns 'undefined' if benchmark is zero, to avoid division errors."""
    try:
        value = float(value)
        benchmark = float(benchmark)
    except (TypeError, ValueError):
        return "unknown ratio"

    if benchmark == 0:
        return "undefined"

    ratio = abs(value / benchmark)
    return f"{ratio:.2f}x"