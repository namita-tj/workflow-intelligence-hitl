"""Thesis Section 4.2.4: correct explanations that paraphrase the metric used to be rejected."""

import pytest

from hitl.explanation_layer import METRIC_PARAPHRASES, metric_match, validate_response


def _breach(metric):
    return {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": metric, "value": 0.36,
            "benchmark": 0.05, "cluster_label": None, "is_noise": None}


def test_the_thesis_example_now_passes():
    response = "T-023 is spending a lot of time without active tasks assigned this month."
    assert validate_response(response, _breach("Idle Rate")) is True
    assert metric_match(response, "Idle Rate") == "paraphrase"


@pytest.mark.parametrize(("metric", "response"), [
    ("Rework Rate", "A large share of hours went into redoing deliverables after review."),
    ("Meeting Overhead Ratio", "Much of the month was spent in meetings with the client."),
    ("ETA Achievement", "Several tasks missed their deadlines this month."),
    ("Effective Utilisation", "Productive hours were lower than for most of the team."),
])
def test_paraphrases_of_each_metric(metric, response):
    assert validate_response(response, _breach(metric)) is True


def test_exact_names_still_pass_and_are_reported_as_exact():
    assert metric_match("T-023's Idle Rate is 35.9%.", "Idle Rate") == "exact"


@pytest.mark.parametrize(("metric", "response"), [
    ("Idle Rate", "T-023 spent most of the month in client meetings."),
    ("Rework Rate", "T-023 had a lot of idle time."),
    ("Meeting Overhead Ratio", "T-023 seems to have some performance issues in general."),
])
def test_explanations_of_a_different_metric_still_fail(metric, response):
    assert validate_response(response, _breach(metric)) is False


def test_no_paraphrase_is_shared_between_metrics():
    import re

    for metric, patterns in METRIC_PARAPHRASES.items():
        for other in METRIC_PARAPHRASES:
            if other != metric:
                assert not any(re.search(p, other.lower()) for p in patterns), (metric, other)


def test_empty_response_fails():
    assert validate_response("", _breach("Idle Rate")) is False
