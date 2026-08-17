"""Tests for the explanation layer — constrained LLM generation with fallback."""

import pytest
from unittest.mock import patch, MagicMock

from hitl.explanation_layer import (
    fallback_explanation,
    normalize_finding,
    build_prompt,
    call_llm,
    validate_response,
    explain_finding,
)


# ============================================================================
# 1. Fallback template tests — no LLM, pure logic
# ============================================================================

def test_fallback_rule_breach():
    """Fallback template for rule breach findings."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    result = fallback_explanation(finding)
    assert "T-023" in result
    assert "Idle Rate" in result
    assert "0.359" in result
    assert "0.050" in result or "0.05" in result


def test_fallback_anomaly():
    """Fallback template for anomaly findings."""
    finding = {
        "teammate_id": "T-023",
        "finding_type": "anomaly",
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    result = fallback_explanation(finding)
    assert "T-023" in result
    assert "anomalous" in result.lower() or "outlier" in result.lower()


# ============================================================================
# 2. Shape normalizer tests
# ============================================================================

def test_normalize_rule_breach():
    """Normalize a rule-based detector finding."""
    raw = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }
    normalized = normalize_finding(raw)
    assert normalized["finding_type"] == "rule_breach"
    assert normalized["metric"] == "Idle Rate"
    assert normalized["value"] == 0.359375
    assert normalized["benchmark"] == 0.05


def test_normalize_anomaly():
    """Normalize an anomaly detector finding."""
    raw = {
        "teammate_id": "T-023",
        "cluster_label": -1,
        "is_noise": True,
    }
    normalized = normalize_finding(raw)
    assert normalized["finding_type"] == "anomaly"
    assert normalized["cluster_label"] == -1
    assert normalized["is_noise"] is True


def test_normalize_unrecognized_schema():
    """Raise on unrecognized finding schema."""
    raw = {"teammate_id": "T-023", "unknown_field": "value"}
    with pytest.raises(ValueError, match="Unrecognized finding schema"):
        normalize_finding(raw)


# ============================================================================
# 3. Prompt builder tests
# ============================================================================

def test_prompt_builder_rule_breach():
    """Prompt builder constrains against firm conclusions for rule breach."""
    normalized = {
        "finding_type": "rule_breach",
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    prompt = build_prompt(normalized)
    assert "T-023" in prompt
    assert "Idle Rate" in prompt
    assert "0.359" in prompt
    # Constraint: forbid firm conclusions
    assert "Do NOT" in prompt or "should NOT" in prompt.upper()


def test_prompt_builder_anomaly():
    """Prompt builder constrains against firm conclusions for anomaly."""
    normalized = {
        "finding_type": "anomaly",
        "teammate_id": "T-023",
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    prompt = build_prompt(normalized)
    assert "T-023" in prompt
    assert "outlier" in prompt.lower()
    # Constraint: forbid firm conclusions
    assert "Do NOT" in prompt or "should NOT" in prompt.upper()


# ============================================================================
# 4. Validator tests — mocked LLM responses
# ============================================================================

def test_validate_response_rule_breach_pass():
    """Validator passes when LLM mentions the real metric."""
    normalized = {
        "finding_type": "rule_breach",
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    llm_response = "T-023's Idle Rate is significantly elevated at 35.9%..."
    assert validate_response(llm_response, normalized) is True


def test_validate_response_rule_breach_fail():
    """Validator fails when LLM doesn't mention the metric."""
    normalized = {
        "finding_type": "rule_breach",
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "cluster_label": None,
        "is_noise": None,
    }
    llm_response = "T-023 seems to have some performance issues in general."
    assert validate_response(llm_response, normalized) is False


def test_validate_response_anomaly_pass():
    """Validator passes when LLM mentions outlier/anomaly/cluster."""
    normalized = {
        "finding_type": "anomaly",
        "teammate_id": "T-023",
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    llm_response = "T-023 is flagged as an outlier in cluster analysis..."
    assert validate_response(llm_response, normalized) is True


def test_validate_response_anomaly_fail():
    """Validator fails when LLM doesn't mention outlier/anomaly/cluster/ID."""
    normalized = {
        "finding_type": "anomaly",
        "teammate_id": "T-023",
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    llm_response = "This teammate has been working hard on various tasks."
    assert validate_response(llm_response, normalized) is False


def test_validate_response_anomaly_fail_with_none_teammate_id():
    """Validator correctly rejects unrelated text even when teammate_id is None.
    
    This is the edge case where an empty string in the keyword list would match
    everything. Ensure that doesn't happen.
    """
    normalized = {
        "finding_type": "anomaly",
        "teammate_id": None,  # This was causing the bug
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": -1,
        "is_noise": True,
    }
    # Completely unrelated text
    llm_response = "This is about lunch and the weather today."
    # Should fail validation because it doesn't mention outlier/anomal/cluster
    assert validate_response(llm_response, normalized) is False

def test_validate_response_does_not_catch_soft_recommendations():
    """KNOWN LIMITATION — documents, does not fix.

    validate_response only checks for factual content (metric/value mentioned),
    not for constraint violations like soft recommendations. This is a real,
    observed gap: a live Ollama call against T-023 produced a factually correct
    explanation that still ended with a recommendation ("it is important for
    the manager to investigate further"), despite the prompt explicitly
    forbidding this. That response would incorrectly PASS validation, as
    demonstrated below. See explanation_layer.py's validate_response docstring
    for the full explanation and why this was left undetected by design.
    """
    normalized = {
        "finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate",
        "value": 0.359375, "benchmark": 0.05, "cluster_label": None, "is_noise": None,
    }
    response_with_soft_recommendation = (
        "T-023's Idle Rate is 0.36, well above the 0.05 benchmark. "
        "It is important for the manager to investigate further."
    )
    # This SHOULD arguably fail, but doesn't — the assertion below documents
    # current behavior, not desired behavior.
    assert validate_response(response_with_soft_recommendation, normalized) is True
    
# ============================================================================
# 5. LLM call wrapper tests — mocked API
# ============================================================================

def test_call_llm_ollama_mocked():
    """Mock call_llm with Ollama backend."""
    with patch("hitl.explanation_layer._call_ollama") as mock_ollama:
        mock_ollama.return_value = "Mocked response"
        result = call_llm("test prompt", backend="ollama", model="mistral")
        assert result == "Mocked response"
        mock_ollama.assert_called_once_with("test prompt", model="mistral")


def test_call_llm_google_ai_mocked():
    """Mock call_llm with Google AI backend."""
    with patch("hitl.explanation_layer._call_google_ai") as mock_google:
        mock_google.return_value = "Mocked response"
        result = call_llm("test prompt", backend="google_ai", api_key="fake_key")
        assert result == "Mocked response"
        mock_google.assert_called_once_with("test prompt", api_key="fake_key")


def test_call_llm_unknown_backend():
    """Raise on unknown backend."""
    with pytest.raises(ValueError, match="Unknown backend"):
        call_llm("test prompt", backend="unknown_backend")


# ============================================================================
# 6. Orchestrator tests — mocked validation and fallback
# ============================================================================

def test_explain_finding_with_valid_llm_response():
    """Orchestrator returns LLM response when validation passes."""
    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    llm_response = "T-023's Idle Rate at 35.9% is significantly above the 5% benchmark..."

    with patch("hitl.explanation_layer.call_llm") as mock_call:
        mock_call.return_value = llm_response
        result = explain_finding(raw_finding, backend="ollama")
        assert result == llm_response


def test_explain_finding_fallback_on_validation_failure():
    """Orchestrator falls back to template when LLM validation fails."""
    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    # LLM response doesn't mention "Idle Rate" — validation will fail
    bad_llm_response = "T-023 has some issues in general."

    with patch("hitl.explanation_layer.call_llm") as mock_call:
        mock_call.return_value = bad_llm_response
        result = explain_finding(raw_finding, backend="ollama")
        # Should fall back to template
        assert "T-023" in result
        assert "Idle Rate" in result


def test_explain_finding_fallback_on_llm_none():
    """Orchestrator falls back to template when LLM returns None."""
    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    with patch("hitl.explanation_layer.call_llm") as mock_call:
        mock_call.return_value = None  # LLM call failed
        result = explain_finding(raw_finding, backend="ollama")
        # Should fall back to template
        assert "T-023" in result
        assert "Idle Rate" in result


def test_explain_finding_anomaly_with_fallback():
    """Orchestrator handles anomaly findings with fallback."""
    raw_finding = {
        "teammate_id": "T-023",
        "cluster_label": -1,
        "is_noise": True,
    }

    with patch("hitl.explanation_layer.call_llm") as mock_call:
        mock_call.return_value = None
        result = explain_finding(raw_finding, backend="ollama")
        # Should fall back to template
        assert "T-023" in result
        assert "anomalous" in result.lower() or "outlier" in result.lower()


# ============================================================================
# Integration test — marked to skip by default
# ============================================================================

@pytest.mark.integration
def test_integration_explain_t023_real_backend():
    """Integration test: real T-023 finding against actual LLM backend.
    
    This test is SKIPPED by default and only runs if:
    1. You run: pytest -m integration
    2. You have an LLM backend available (Ollama or Google AI API key)
    
    Manually verify the output reads like the reference example:
    "T-023's idle time (35.9%) is more than 7x the 5% benchmark — among the
    highest in the team. This could indicate blocked work, insufficient task
    assignment, or reduced capacity. Worth checking in before assuming a
    performance issue."
    """
    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    # Try Ollama first, fall back to Google AI if available
    result = explain_finding(raw_finding, backend="ollama")

    # Minimal validation: result should be non-empty and mention the teammate/metric
    assert result
    assert "T-023" in result
    assert "Idle Rate" in result or "idle" in result.lower()

    # Print for manual inspection
    print("\n" + "=" * 70)
    print("MANUAL INSPECTION REQUIRED:")
    print("=" * 70)
    print(result)
    print("=" * 70)
    print("Does this explanation:")
    print("  1. State the fact clearly (Idle Rate, value, benchmark)?")
    print("  2. Offer 1-2 possible interpretations?")
    print("  3. Avoid firm conclusions or recommendations?")
    print("=" * 70)
