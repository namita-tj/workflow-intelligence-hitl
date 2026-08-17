"""Tests for the review interface — human decision capture with mocked input."""

import pytest
from datetime import datetime

from hitl.review import (
    review_finding,
    _display_finding,
    _prompt_for_decision,
    _prompt_for_annotation,
)


# ============================================================================
# Helper: mocked input function generator
# ============================================================================

def make_mock_input(responses: list) -> callable:
    """
    Create a mocked input function that returns scripted responses in order.

    Parameters
    ----------
    responses : list
        List of strings to return on successive calls.

    Returns
    -------
    callable
        Function that returns one response per call, raises StopIteration if exhausted.
    """
    responses_iter = iter(responses)
    return lambda _: next(responses_iter)


# ============================================================================
# 1. Prompt helper tests
# ============================================================================

def test_prompt_for_decision_confirm():
    """Prompt accepts 'confirm' (case-insensitive)."""
    mock_input = make_mock_input(["confirm"])
    result = _prompt_for_decision(mock_input)
    assert result == "confirm"


def test_prompt_for_decision_reject():
    """Prompt accepts 'reject' (case-insensitive)."""
    mock_input = make_mock_input(["REJECT"])
    result = _prompt_for_decision(mock_input)
    assert result == "reject"


def test_prompt_for_decision_invalid_then_valid():
    """Prompt rejects invalid input, then accepts valid input on retry."""
    mock_input = make_mock_input(["invalid", "maybe", "confirm"])
    result = _prompt_for_decision(mock_input)
    assert result == "confirm"


def test_prompt_for_annotation_minimum_length():
    """Annotation must be at least 10 characters."""
    # Too short, then valid
    mock_input = make_mock_input(["short", "This is a valid annotation with enough text"])
    result = _prompt_for_annotation(mock_input, "confirm")
    assert len(result) >= 10
    assert "valid" in result.lower()


def test_prompt_for_annotation_empty_rejected():
    """Annotation cannot be empty or whitespace-only."""
    # Empty, then whitespace, then valid
    mock_input = make_mock_input(["", "   ", "This is definitely long enough"])
    result = _prompt_for_annotation(mock_input, "reject")
    assert len(result) >= 10


# ============================================================================
# 2. Main review_finding function tests
# ============================================================================

def test_review_finding_confirm_rule_breach():
    """Review a rule-breach finding with confirm decision."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    explanation = "T-023's idle time is significantly elevated."

    mock_input = make_mock_input([
        "Alice Chen",  # reviewer name
        "confirm",     # decision
        "Reduced task assignment that week, confirmed with T-023",  # annotation
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["teammate_id"] == "T-023"
    assert result["finding_type"] == "rule_breach"
    assert result["decision"] == "confirm"
    assert result["annotation"] == "Reduced task assignment that week, confirmed with T-023"
    assert result["reviewer"] == "Alice Chen"
    assert result["explanation"] == explanation
    assert result["finding_summary"]["metric"] == "Idle Rate"


def test_review_finding_reject_rule_breach():
    """Review a rule-breach finding with reject decision."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    explanation = "T-023's idle time is significantly elevated."

    mock_input = make_mock_input([
        "Bob Smith",     # reviewer name
        "reject",        # decision
        "Measurement error during that period, data already flagged",  # annotation
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["teammate_id"] == "T-023"
    assert result["decision"] == "reject"
    assert len(result["annotation"]) >= 10
    assert result["reviewer"] == "Bob Smith"


def test_review_finding_confirm_anomaly():
    """Review an anomaly finding with confirm decision."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "anomaly",
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    explanation = "T-023 is flagged as an outlier."

    mock_input = make_mock_input([
        "Carol Davis",   # reviewer name
        "confirm",       # decision
        "Behavioral profile differs significantly; warrants follow-up",  # annotation
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["teammate_id"] == "T-023"
    assert result["finding_type"] == "anomaly"
    assert result["decision"] == "confirm"
    assert result["finding_summary"]["is_noise"] is True
    assert result["finding_summary"]["cluster_label"] == -1


def test_review_finding_reject_anomaly():
    """Review an anomaly finding with reject decision."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "anomaly",
        "cluster_label": 1,
        "is_noise": False,
    }
    explanation = "T-023 is in cluster 1."

    mock_input = make_mock_input([
        "Diana Evans",   # reviewer name
        "reject",        # decision
        "Cluster assignment is expected given team composition at the time",  # annotation
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["decision"] == "reject"
    assert "expected" in result["annotation"].lower()


# ============================================================================
# 3. Timestamp validation
# ============================================================================

def test_review_finding_timestamp_iso8601():
    """Timestamp is in ISO 8601 format."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "Test annotation that is long enough",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    # Should be parseable as ISO 8601 using datetime.fromisoformat()
    timestamp_str = result["timestamp"]
    try:
        parsed = datetime.fromisoformat(timestamp_str)
        assert parsed is not None
    except ValueError as e:
        pytest.fail(f"Timestamp not valid ISO 8601: {timestamp_str}, error: {e}")


def test_review_finding_timestamp_has_timezone():
    """Timestamp includes timezone information (UTC)."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "Test annotation with sufficient length",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    # ISO 8601 with timezone should contain 'T' and a timezone indicator
    timestamp_str = result["timestamp"]
    assert "T" in timestamp_str  # Date-time separator
    assert "+" in timestamp_str or "Z" in timestamp_str or timestamp_str.endswith("+00:00")


# ============================================================================
# 4. Annotation enforcement
# ============================================================================

def test_review_finding_annotation_required_on_confirm():
    """Annotation is required and non-empty on confirm."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "This annotation is definitely long enough to pass validation",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["decision"] == "confirm"
    assert len(result["annotation"]) >= 10
    assert result["annotation"] != ""


def test_review_finding_annotation_required_on_reject():
    """Annotation is required and non-empty on reject."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "reject",
        "Rejecting due to data quality issues in the measurement period",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["decision"] == "reject"
    assert len(result["annotation"]) >= 10
    assert result["annotation"] != ""


def test_review_finding_empty_annotation_reprompted():
    """Empty annotation triggers reprompt, not failure."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    # Empty → short → valid
    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "",            # empty
        "oops",        # too short
        "This is a comprehensive annotation that passes all checks",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert len(result["annotation"]) >= 10
    assert "comprehensive" in result["annotation"].lower()


# ============================================================================
# 5. Reviewer identity handling
# ============================================================================

def test_review_finding_reviewer_provided():
    """When reviewer is provided, it's used directly."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "confirm",
        "Test annotation that is long enough here",
    ])

    result = review_finding(
        finding, explanation, input_fn=mock_input, reviewer="Preassigned Reviewer"
    )

    assert result["reviewer"] == "Preassigned Reviewer"


def test_review_finding_reviewer_prompted_if_none():
    """When reviewer is None, input is prompted."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Ellen Foster",  # reviewer name (prompted)
        "confirm",
        "Test annotation that satisfies length requirements",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input, reviewer=None)

    assert result["reviewer"] == "Ellen Foster"


def test_review_finding_empty_reviewer_reprompted():
    """Empty reviewer name triggers reprompt."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    # empty → whitespace → valid
    mock_input = make_mock_input([
        "",             # empty
        "   ",          # whitespace only
        "Frank Green",  # valid
        "confirm",
        "Test annotation that is valid and long enough",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input, reviewer=None)

    assert result["reviewer"] == "Frank Green"


# ============================================================================
# 6. Finding summary extraction
# ============================================================================

def test_review_finding_summary_rule_breach():
    """Finding summary correctly extracts rule breach fields."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "Test annotation here",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["finding_summary"]["metric"] == "Idle Rate"
    assert result["finding_summary"]["value"] == 0.359375
    assert result["finding_summary"]["benchmark"] == 0.05


def test_review_finding_summary_anomaly():
    """Finding summary correctly extracts anomaly fields."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "anomaly",
        "cluster_label": -1,
        "is_noise": True,
    }
    explanation = "Test explanation."

    mock_input = make_mock_input([
        "Test Reviewer",
        "confirm",
        "Test annotation here",
    ])

    result = review_finding(finding, explanation, input_fn=mock_input)

    assert result["finding_summary"]["cluster_label"] == -1
    assert result["finding_summary"]["is_noise"] is True
