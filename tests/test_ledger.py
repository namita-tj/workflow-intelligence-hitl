"""Tests for the ledger — pipeline orchestration and persistence.

Critical test: the regression test for the normalization bug.
Asserts that explain_finding and review_finding receive the SAME
normalized dict, not differently-shaped input.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hitl.ledger import (
    process_finding,
    append_to_ledger,
    load_ledger,
)


# ============================================================================
# 1. Basic ledger persistence tests
# ============================================================================

def test_append_to_ledger_creates_file(tmp_path):
    """append_to_ledger creates the ledger file if it doesn't exist."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    record = {
        "teammate_id": "T-023",
        "decision": "confirm",
        "annotation": "Test annotation here",
    }

    append_to_ledger(record, path=str(ledger_path))

    assert ledger_path.exists()


def test_append_to_ledger_writes_json_line(tmp_path):
    """append_to_ledger writes valid JSON on a single line."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    record = {
        "teammate_id": "T-023",
        "decision": "confirm",
        "annotation": "Test annotation",
    }

    append_to_ledger(record, path=str(ledger_path))

    # Read back and parse
    with open(ledger_path, "r") as f:
        line = f.readline()
    parsed = json.loads(line)
    assert parsed == record


def test_append_and_load_roundtrip(tmp_path):
    """Append and load roundtrip: record → ledger → load → same record."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    record = {
        "teammate_id": "T-023",
        "finding_type": "rule_breach",
        "decision": "confirm",
        "annotation": "Test annotation here",
        "reviewer": "Test Reviewer",
        "timestamp": "2026-08-17T12:00:00+00:00",
    }

    append_to_ledger(record, path=str(ledger_path))
    loaded = load_ledger(path=str(ledger_path))

    assert len(loaded) == 1
    assert loaded[0] == record


def test_append_is_additive_not_overwriting(tmp_path):
    """Two appends produce two records, not one. Truly append-only."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    record1 = {
        "teammate_id": "T-001",
        "decision": "confirm",
        "annotation": "First annotation",
    }
    record2 = {
        "teammate_id": "T-023",
        "decision": "reject",
        "annotation": "Second annotation",
    }

    append_to_ledger(record1, path=str(ledger_path))
    append_to_ledger(record2, path=str(ledger_path))

    loaded = load_ledger(path=str(ledger_path))
    assert len(loaded) == 2
    assert loaded[0] == record1
    assert loaded[1] == record2


def test_append_multiple_records_preserves_order(tmp_path):
    """Multiple appends preserve order."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    records = [
        {"teammate_id": f"T-{i:03d}", "decision": "confirm"}
        for i in range(1, 6)
    ]

    for record in records:
        append_to_ledger(record, path=str(ledger_path))

    loaded = load_ledger(path=str(ledger_path))
    assert len(loaded) == 5
    assert loaded == records


def test_load_ledger_nonexistent_file_returns_empty_list(tmp_path):
    """load_ledger returns empty list if file doesn't exist (no error)."""
    ledger_path = tmp_path / "nonexistent.jsonl"
    result = load_ledger(path=str(ledger_path))
    assert result == []


def test_load_ledger_skips_empty_lines(tmp_path):
    """load_ledger skips blank lines gracefully."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    # Write manually with blank lines
    with open(ledger_path, "w") as f:
        f.write(json.dumps({"id": 1}) + "\n")
        f.write("\n")  # blank line
        f.write(json.dumps({"id": 2}) + "\n")
        f.write("   \n")  # whitespace line
        f.write(json.dumps({"id": 3}) + "\n")

    loaded = load_ledger(path=str(ledger_path))
    assert len(loaded) == 3
    assert loaded[0]["id"] == 1
    assert loaded[1]["id"] == 2
    assert loaded[2]["id"] == 3


# ============================================================================
# 2. THE CRITICAL REGRESSION TEST
# ============================================================================

def test_process_finding_threads_one_normalized_object(tmp_path, monkeypatch):
    """
    REGRESSION TEST for the bug found 2026-08-17:
    Asserts that explain_finding and review_finding receive the SAME
    normalized dict — not the raw detector output or differently-shaped versions.

    This is what would have caught the manual-testing bug immediately.
    """
    ledger_path = tmp_path / "test_ledger.jsonl"

    # Raw finding (rule breach schema)
    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    # Capture what each function is actually called with
    explain_calls = []
    review_calls = []

    def mock_explain_finding(finding, backend=None, backend_kwargs=None):
        explain_calls.append(finding)
        return "Mock explanation"

    def mock_review_finding(finding, explanation=None, input_fn=None, reviewer=None):
        review_calls.append(finding)
        return {
            "teammate_id": finding.get("teammate_id"),
            "finding_type": finding.get("finding_type"),
            "finding_summary": {},
            "explanation": explanation,
            "decision": "confirm",
            "annotation": "Test annotation that is long enough",
            "reviewer": "Test Reviewer",
            "timestamp": "2026-08-17T12:00:00+00:00",
        }

    # Monkeypatch both functions
    monkeypatch.setattr(
        "hitl.ledger.explain_finding",
        mock_explain_finding,
    )
    monkeypatch.setattr(
        "hitl.ledger.review_finding",
        mock_review_finding,
    )

    # Run the pipeline
    process_finding(
        raw_finding,
        reviewer="Test Reviewer",
        input_fn=lambda _: "confirm",
        ledger_path=str(ledger_path),
    )

    # The critical assertions:
    # 1. Both were called exactly once
    assert len(explain_calls) == 1
    assert len(review_calls) == 1

    # 2. Both received the SAME object (not different normalizations)
    assert explain_calls[0] is review_calls[0], (
        "explain_finding and review_finding received different objects! "
        "Bug: normalization not shared."
    )

    # 3. The object they received is normalized (has 'finding_type')
    normalized = explain_calls[0]
    assert "finding_type" in normalized
    assert normalized["finding_type"] == "rule_breach"

    # 4. It is NOT the raw finding (raw doesn't have 'finding_type')
    assert raw_finding != normalized


def test_process_finding_writes_to_ledger(tmp_path, monkeypatch):
    """After process_finding, ledger file contains the reviewed record."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    # Mock the interactive parts
    def mock_explain(finding, **kwargs):
        return "Mocked explanation for T-023"

    def mock_review(finding, explanation=None, input_fn=None, reviewer=None):
        return {
            "teammate_id": finding.get("teammate_id"),
            "finding_type": finding.get("finding_type"),
            "finding_summary": {"metric": "Idle Rate"},
            "explanation": explanation,
            "decision": "confirm",
            "annotation": "Confirmed during team review",
            "reviewer": reviewer or "Test Reviewer",
            "timestamp": "2026-08-17T12:30:00+00:00",
        }

    monkeypatch.setattr("hitl.ledger.explain_finding", mock_explain)
    monkeypatch.setattr("hitl.ledger.review_finding", mock_review)

    # Run pipeline
    result = process_finding(
        raw_finding,
        reviewer="Alice Chen",
        ledger_path=str(ledger_path),
    )

    # Verify ledger was written
    loaded = load_ledger(path=str(ledger_path))
    assert len(loaded) == 1
    assert loaded[0]["teammate_id"] == "T-023"
    assert loaded[0]["decision"] == "confirm"
    assert loaded[0]["reviewer"] == "Alice Chen"

    # Verify returned value matches ledger entry
    assert result == loaded[0]


# ============================================================================
# 3. Pipeline integration tests
# ============================================================================

def test_process_finding_rule_breach(tmp_path, monkeypatch):
    """process_finding handles rule-breach findings end to end."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    raw_finding = {
        "teammate_id": "T-023",
        "metric": "Idle Rate",
        "value": 0.359375,
        "benchmark": 0.05,
        "breached": True,
    }

    # Mock interactive parts
    monkeypatch.setattr(
        "hitl.ledger.explain_finding",
        lambda finding, **kwargs: f"Explanation for {finding.get('metric')}",
    )
    monkeypatch.setattr(
        "hitl.ledger.review_finding",
        lambda finding, **kwargs: {
            "teammate_id": finding.get("teammate_id"),
            "finding_type": finding.get("finding_type"),
            "finding_summary": {"metric": finding.get("metric")},
            "explanation": kwargs.get("explanation"),
            "decision": "confirm",
            "annotation": "Test annotation",
            "reviewer": kwargs.get("reviewer", "Unknown"),
            "timestamp": "2026-08-17T12:00:00+00:00",
        },
    )

    result = process_finding(
        raw_finding,
        reviewer="Test Reviewer",
        ledger_path=str(ledger_path),
    )

    assert result["teammate_id"] == "T-023"
    assert result["finding_type"] == "rule_breach"
    assert "Idle Rate" in result["finding_summary"]["metric"]


def test_process_finding_anomaly(tmp_path, monkeypatch):
    """process_finding handles anomaly findings end to end."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    raw_finding = {
        "teammate_id": "T-023",
        "cluster_label": -1,
        "is_noise": True,
    }

    # Mock interactive parts
    monkeypatch.setattr(
        "hitl.ledger.explain_finding",
        lambda finding, **kwargs: "Outlier explanation",
    )
    monkeypatch.setattr(
        "hitl.ledger.review_finding",
        lambda finding, **kwargs: {
            "teammate_id": finding.get("teammate_id"),
            "finding_type": finding.get("finding_type"),
            "finding_summary": {
                "cluster_label": finding.get("cluster_label"),
                "is_noise": finding.get("is_noise"),
            },
            "explanation": kwargs.get("explanation"),
            "decision": "reject",
            "annotation": "Cluster assignment is expected",
            "reviewer": kwargs.get("reviewer", "Unknown"),
            "timestamp": "2026-08-17T12:00:00+00:00",
        },
    )

    result = process_finding(
        raw_finding,
        reviewer="Test Reviewer",
        ledger_path=str(ledger_path),
    )

    assert result["teammate_id"] == "T-023"
    assert result["finding_type"] == "anomaly"
    assert result["finding_summary"]["is_noise"] is True


def test_process_finding_full_roundtrip_multiple_findings(tmp_path, monkeypatch):
    """Multiple findings processed create multiple ledger entries."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    findings = [
        {
            "teammate_id": "T-001",
            "metric": "ETA Achievement",
            "value": 0.5,
            "benchmark": 0.2,
            "breached": True,
        },
        {
            "teammate_id": "T-023",
            "cluster_label": -1,
            "is_noise": True,
        },
        {
            "teammate_id": "T-005",
            "metric": "Rework Rate",
            "value": 0.15,
            "benchmark": 0.05,
            "breached": True,
        },
    ]

    # Mock interactive parts
    monkeypatch.setattr(
        "hitl.ledger.explain_finding",
        lambda finding, **kwargs: f"Explanation",
    )
    monkeypatch.setattr(
        "hitl.ledger.review_finding",
        lambda finding, **kwargs: {
            "teammate_id": finding.get("teammate_id"),
            "finding_type": finding.get("finding_type"),
            "finding_summary": {},
            "explanation": "Explanation",
            "decision": "confirm",
            "annotation": "Confirmed",
            "reviewer": "Test",
            "timestamp": "2026-08-17T12:00:00+00:00",
        },
    )

    # Process all findings
    for finding in findings:
        process_finding(
            finding,
            reviewer="Test Reviewer",
            ledger_path=str(ledger_path),
        )

    # Verify ledger has all three entries
    loaded = load_ledger(path=str(ledger_path))
    assert len(loaded) == 3
    assert loaded[0]["teammate_id"] == "T-001"
    assert loaded[1]["teammate_id"] == "T-023"
    assert loaded[2]["teammate_id"] == "T-005"


# ============================================================================
# 4. Ledger mode enforcement tests
# ============================================================================

def test_append_mode_never_overwrites(tmp_path):
    """append_to_ledger always appends, never truncates."""
    ledger_path = tmp_path / "test_ledger.jsonl"

    # Write initial record manually
    with open(ledger_path, "w") as f:
        f.write(json.dumps({"id": "original"}) + "\n")

    # Append a new record
    append_to_ledger({"id": "new"}, path=str(ledger_path))

    # Both should be present
    with open(ledger_path, "r") as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == "original"
    assert json.loads(lines[1])["id"] == "new"
