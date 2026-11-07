"""two_part_prompt.py: structure of the prompt and its input checks."""

import pytest

from hitl.two_part_prompt import build_two_part_prompt

BREACH = {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate", "value": 0.36, "benchmark": 0.05}


def test_rule_breach_prompt_has_both_parts_and_the_facts():
    p = build_two_part_prompt(BREACH)
    assert "Part 1" in p and "Part 2" in p and "Idle Rate" in p and "T-023" in p
    assert "Do not answer these yourself" in p


def test_anomaly_prompt():
    p = build_two_part_prompt({"finding_type": "anomaly", "teammate_id": "T-018", "cluster_label": -1, "is_noise": True})
    assert "yes (outlier)" in p


@pytest.mark.parametrize("bad", [
    {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate", "value": 0.36},
    {"finding_type": "anomaly", "teammate_id": "T-018", "cluster_label": -1},
    {"finding_type": "personal_baseline", "teammate_id": "T-010"},
    {"finding_type": "rule_breach", "metric": "Idle Rate", "value": 1, "benchmark": 1},
    "not a dict",
])
def test_invalid_findings_raise(bad):
    with pytest.raises(ValueError):
        build_two_part_prompt(bad)


def test_zero_benchmark_gives_undefined_ratio():
    p = build_two_part_prompt({**BREACH, "benchmark": 0})
    assert "undefined" in p
