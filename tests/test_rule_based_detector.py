import pandas as pd

from hitl.rule_based_detector import THRESHOLDS, find_metric_breaches


T023_ROW = pd.Series({
    "Teammate ID": "T-023",
    "ETA Achievement": 0.1125,
    "Rework Rate": 0.0,
    "Req. Understanding Ratio": 0.0,
    "Meeting Overhead Ratio": 0.028125,
    "Idle Rate": 0.359375,
    "Effective Utilisation": 0.1125,
    "Avg Time Per Task": 20.0,
})

# A teammate who passes every checked metric
CLEAN_ROW = pd.Series({
    "Teammate ID": "T-CLEAN",
    "ETA Achievement": 1.0,
    "Rework Rate": 0.05,
    "Req. Understanding Ratio": 0.0,
    "Meeting Overhead Ratio": 0.10,
    "Idle Rate": 0.02,
    "Effective Utilisation": 0.85,
    "Avg Time Per Task": 5.0,
})


def test_t023_breaches():
    result = find_metric_breaches(T023_ROW, THRESHOLDS)
    breached = {r["metric"] for r in result if r["breached"]}
    assert breached == {"ETA Achievement", "Idle Rate", "Effective Utilisation"}


def test_no_false_breach_case():
    result = find_metric_breaches(CLEAN_ROW, THRESHOLDS)
    breached = {r["metric"] for r in result if r["breached"]}
    assert breached == set()


def test_teammate_id_populated():
    result = find_metric_breaches(T023_ROW, THRESHOLDS)
    assert all(r["teammate_id"] == "T-023" for r in result)