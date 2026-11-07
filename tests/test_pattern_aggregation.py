"""pattern_aggregation.py had no tests (README limitation)."""

from hitl.pattern_aggregation import get_co_occurring_teammates, group_by_shared_metric

FINDINGS = [
    {"finding_type": "rule_breach", "teammate_id": "T-022", "metric": "Idle Rate"},
    {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate"},
    {"finding_type": "rule_breach", "teammate_id": "T-018", "metric": "Rework Rate"},
    {"finding_type": "anomaly", "teammate_id": "T-008", "cluster_label": -1, "is_noise": True},
    {"finding_type": "anomaly", "teammate_id": "T-018", "cluster_label": -1, "is_noise": True},
    {"finding_type": "rule_breach", "teammate_id": None, "metric": "Idle Rate"},
]


def test_groups_only_shared_rule_breaches():
    assert group_by_shared_metric(FINDINGS) == {"Idle Rate": ["T-022", "T-023"]}


def test_anomalies_are_never_grouped_by_their_shared_noise_label():
    anomalies = [f for f in FINDINGS if f["finding_type"] == "anomaly"]
    assert group_by_shared_metric(anomalies) == {}


def test_co_occurring_teammates_excludes_the_teammate_itself():
    grouped = group_by_shared_metric(FINDINGS)
    assert get_co_occurring_teammates("T-023", "Idle Rate", grouped) == ["T-022"]
    assert get_co_occurring_teammates("T-018", "Rework Rate", grouped) == []
    assert get_co_occurring_teammates("T-023", None, grouped) == []
