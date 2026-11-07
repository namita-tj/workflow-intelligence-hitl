"""quality_metrics.py had no tests (README limitation); these pin down its behaviour."""

import json

from hitl.quality_metrics import (
    has_potential_hallucination,
    has_recommendation_language,
    load_quality_metrics,
    log_quality_metrics,
    summarize_quality_metrics,
)

BREACH = {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate", "value": 0.36, "benchmark": 0.05}
ANOMALY = {"finding_type": "anomaly", "teammate_id": "T-018", "cluster_label": -1, "is_noise": True}


def test_recommendation_language_patterns():
    assert has_recommendation_language("The manager should look into this.")
    assert has_recommendation_language("It is important that this is discussed.")
    assert has_recommendation_language("We recommend a follow-up.")
    assert not has_recommendation_language("Idle Rate is 0.36 against a benchmark of 0.05.")
    assert not has_recommendation_language("Shoulder season may explain lower demand.")  # word boundary


def test_hallucination_heuristic_needs_another_metric_and_breach_language():
    assert has_potential_hallucination("Idle Rate and Rework Rate are both above threshold.", BREACH)
    assert not has_potential_hallucination("Idle Rate is above threshold; Rework Rate looks normal.", ANOMALY)
    assert not has_potential_hallucination("Idle Rate is high. Rework Rate is mentioned in passing.", BREACH)
    assert not has_potential_hallucination("Idle Rate is above threshold.", BREACH)


def test_log_and_summarize(tmp_path):
    path = str(tmp_path / "q.jsonl")
    log_quality_metrics("Idle Rate is above threshold. The manager should check.", BREACH, metrics_path=path)
    log_quality_metrics("Idle Rate is 0.36.", BREACH, metrics_path=path)
    log_quality_metrics(None, ANOMALY, metrics_path=path)
    records = load_quality_metrics(path)
    assert len(records) == 3 and records[2]["llm_available"] is False
    summary = summarize_quality_metrics(records)
    assert summary == {"n_total": 3, "n_available": 2, "recommendation_language_rate": 0.5,
                       "potential_hallucination_rate": 0.0}
    assert all(json.loads(line) for line in open(path))


def test_missing_log_and_empty_summary(tmp_path):
    assert load_quality_metrics(str(tmp_path / "none.jsonl")) == []
    assert summarize_quality_metrics([]) == {"n_total": 0, "n_available": 0}


def test_logging_never_breaks_the_pipeline(tmp_path):
    record = log_quality_metrics("text", BREACH, metrics_path=str(tmp_path / "missing_dir" / "q.jsonl"))
    assert record["llm_available"] is True
