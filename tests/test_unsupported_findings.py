"""Thesis Section 4.2.5: an unsupported finding type used to be misclassified silently.
It must now be rejected with a clear error, before anything reaches the reviewer."""

import pytest

from hitl.explanation_layer import UnsupportedFindingError, explain_finding, normalize_finding
from hitl.ledger import process_finding

# The case from the thesis: a deviation from the teammate's own baseline (T-010, QC hours 3.75x)
PERSONAL_BASELINE = {"teammate_id": "T-010", "metric": "QC hours", "value": 3.75, "baseline": 1.0,
                     "comparison": "own history"}


def test_personal_baseline_finding_is_rejected_not_misclassified():
    with pytest.raises(UnsupportedFindingError, match="does not support"):
        normalize_finding(PERSONAL_BASELINE)


def test_unknown_declared_finding_type_is_rejected():
    with pytest.raises(UnsupportedFindingError, match="Unsupported finding_type 'personal_baseline'"):
        normalize_finding({"finding_type": "personal_baseline", "teammate_id": "T-010", "metric": "QC hours"})


def test_rule_breach_without_benchmark_is_rejected():
    with pytest.raises(UnsupportedFindingError, match=r"missing required field\(s\) \['benchmark'\]"):
        normalize_finding({"teammate_id": "T-023", "metric": "Idle Rate", "value": 0.36})


def test_declared_rule_breach_with_extra_fields_is_rejected():
    with pytest.raises(UnsupportedFindingError, match="baseline"):
        normalize_finding({"finding_type": "rule_breach", "teammate_id": "T-010", "metric": "QC hours",
                           "value": 3.75, "benchmark": 1.0, "baseline": 1.0})


def test_error_is_still_a_value_error_for_existing_callers():
    assert issubclass(UnsupportedFindingError, ValueError)


def test_supported_findings_still_pass_including_detector_output():
    rule = normalize_finding({"teammate_id": "T-023", "metric": "Idle Rate", "value": 0.36,
                              "benchmark": 0.05, "breached": True})
    assert rule["finding_type"] == "rule_breach"
    anomaly = normalize_finding({"finding_type": "anomaly", "teammate_id": "T-018", "cluster_label": -1,
                                 "is_noise": True})
    assert anomaly["finding_type"] == "anomaly"


def test_nothing_reaches_the_reviewer_or_the_ledger(tmp_path):
    ledger = tmp_path / "ledger.jsonl"

    def never_asked(prompt=""):
        raise AssertionError("the reviewer must not be asked about an unsupported finding")

    with pytest.raises(UnsupportedFindingError):
        process_finding(PERSONAL_BASELINE, backend="none", reviewer="R", input_fn=never_asked,
                        ledger_path=str(ledger))
    assert not ledger.exists()
    with pytest.raises(UnsupportedFindingError):
        explain_finding(PERSONAL_BASELINE, backend="none")
