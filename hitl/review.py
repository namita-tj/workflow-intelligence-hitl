"""Human review interface for HITL findings.

Presents an explained finding to a reviewer, captures their decision
(confirm/reject) with required annotation, and records the review outcome.

Annotation is required on both confirm AND reject to prevent automation bias
and rubber-stamping. See Lai et al. for the motivation.
"""

from datetime import datetime, timezone
from typing import Callable, Optional


def review_finding(
    finding: dict,
    explanation: str,
    input_fn: Callable[[str], str] = input,
    reviewer: Optional[str] = None,
) -> dict:
    """
    Present one finding + its explanation to a human reviewer, capture
    their decision and annotation.

    Parameters
    ----------
    finding : dict
        The normalized finding being reviewed. Must include at minimum:
        'teammate_id', 'finding_type', and type-specific fields (metric/value/benchmark
        for rule_breach, cluster_label/is_noise for anomaly).
    explanation : str
        Plain-text explanation (output of explain_finding()).
    input_fn : Callable[[str], str]
        Function to get user input. Defaults to builtin input().
        Swappable for testing — allows injection of mocked responses.
    reviewer : Optional[str]
        Reviewer name. If None, prompted at runtime.

    Returns
    -------
    dict
        Structured review outcome:
        {
            'teammate_id': str,
            'finding_type': str,  # 'rule_breach' or 'anomaly'
            'finding_summary': dict,  # subset of the finding (metric, value, etc.)
            'explanation': str,
            'decision': 'confirm' | 'reject',
            'annotation': str,  # required, non-empty
            'reviewer': str,
            'timestamp': str,   # ISO 8601 format
        }

    Raises
    ------
    ValueError
        If decision or annotation validation fails (though normally handled
        by reprompting the user, not raised).
    """

    # Prompt for reviewer name if not provided
    if reviewer is None:
        reviewer = input_fn("Reviewer name (required): ").strip()
        while not reviewer:
            reviewer = input_fn("Reviewer name cannot be empty. Try again: ").strip()

    # Display the finding and explanation
    _display_finding(finding, explanation)

    # Collect decision and annotation
    decision = _prompt_for_decision(input_fn)
    annotation = _prompt_for_annotation(input_fn, decision)

    # Build finding summary (type-specific subset)
    if finding.get("finding_type") == "rule_breach":
        finding_summary = {
            "metric": finding.get("metric"),
            "value": finding.get("value"),
            "benchmark": finding.get("benchmark"),
        }
    elif finding.get("finding_type") == "anomaly":
        finding_summary = {
            "cluster_label": finding.get("cluster_label"),
            "is_noise": finding.get("is_noise"),
        }
    else:
        finding_summary = {}

    # ISO 8601 timestamp in UTC
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "teammate_id": finding.get("teammate_id"),
        "finding_type": finding.get("finding_type"),
        "finding_summary": finding_summary,
        "explanation": explanation,
        "decision": decision,
        "annotation": annotation,
        "reviewer": reviewer,
        "timestamp": timestamp,
    }


# ============================================================================
# Helper functions for display and input collection
# ============================================================================

def _display_finding(finding: dict, explanation: str) -> None:
    """Display the finding and explanation to the reviewer."""
    print("\n" + "=" * 70)
    print("FINDING REVIEW")
    print("=" * 70)
    print(f"\nTeammate: {finding.get('teammate_id')}")
    print(f"Finding Type: {finding.get('finding_type')}")

    if finding.get("finding_type") == "rule_breach":
        print(f"Metric: {finding.get('metric')}")
        print(f"Observed Value: {finding.get('value')}")
        print(f"Benchmark: {finding.get('benchmark')}")

    elif finding.get("finding_type") == "anomaly":
        is_noise = finding.get("is_noise")
        status = "Outlier (noise)" if is_noise else f"Cluster {finding.get('cluster_label')}"
        print(f"Status: {status}")

    print("\n" + "-" * 70)
    print("EXPLANATION:")
    print("-" * 70)
    print(explanation)
    print("=" * 70 + "\n")


def _prompt_for_decision(input_fn: Callable[[str], str]) -> str:
    """Prompt for and validate the reviewer's decision (confirm or reject)."""
    valid_decisions = {"confirm", "reject"}

    while True:
        decision = input_fn(
            "Decision (confirm/reject): "
        ).strip().lower()

        if decision not in valid_decisions:
            print(f"Invalid decision. Please enter 'confirm' or 'reject'.")
            continue

        return decision


def _prompt_for_annotation(input_fn: Callable[[str], str], decision: str) -> str:
    """
    Prompt for and validate annotation (required on both confirm and reject).

    Parameters
    ----------
    input_fn : Callable
        Input function.
    decision : str
        The reviewer's decision ('confirm' or 'reject').

    Returns
    -------
    str
        Non-empty annotation string.
    """
    if decision == "confirm":
        prompt_text = (
            "Annotation (why you confirm this finding — required, at least 10 chars): "
        )
    else:  # reject
        prompt_text = (
            "Annotation (why you reject this finding — required, at least 10 chars): "
        )

    while True:
        annotation = input_fn(prompt_text).strip()

        if len(annotation) < 10:
            print(
                "Annotation too short. Please provide at least 10 characters "
                "explaining your reasoning."
            )
            continue

        return annotation


__all__ = ["review_finding"]
