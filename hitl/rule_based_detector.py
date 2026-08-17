"""
Rule-based benchmark-breach detector.

Compares a teammate's KPI ratios against documented benchmarks
(source: MustDoCantFail_KPIs_Enhanced.xlsx) and returns which were breached.

Deterministic — no training, no learned parameters.
"""
import pandas as pd

# {metric: (direction, benchmark)} — direction is 'above' or 'below'
THRESHOLDS = {
    "ETA Achievement": ("below", 1.0),
    "Rework Rate": ("above", 0.10),
    "Meeting Overhead Ratio": ("above", 0.15),
    "Idle Rate": ("above", 0.05),
    "Effective Utilisation": ("below", 0.70),
    # Avg Time Per Task: excluded — no official benchmark exists anywhere
    # in MustDoCantFail_KPIs_Enhanced.xlsx. Not silently dropped: this is
    # a deliberate exclusion, stated here as the design decision.
    # Req. Understanding Ratio: excluded from this detector. Its official
    # definition ("baseline first, flag outliers >20%") is anomaly-detection
    # logic, not a fixed rule — handled in anomaly_detector.py instead.
}


def find_metric_breaches(row: pd.Series, thresholds: dict = THRESHOLDS) -> list[dict]:
    """
    Check one teammate's KPI ratios against documented benchmarks.

    Parameters
    ----------
    row : pd.Series
        One teammate's row (must include 'Teammate ID' and the metric columns).
    thresholds : dict
        {metric_name: (direction, benchmark)}, direction is 'above' or 'below'.

    Returns
    -------
    list[dict]
        One record per metric checked: teammate_id, metric, value,
        benchmark, breached (bool).

    Design decisions:
        - Avg Time Per Task: excluded, no official benchmark exists.
        - Req. Understanding Ratio: excluded, routed to anomaly_detector.py
          since its official rule is baseline-relative, not a fixed threshold.
    """
    teammate_id = row.get("Teammate ID")
    records = []

    for metric, (direction, benchmark) in thresholds.items():
        value = row.get(metric)
        if value is None or pd.isna(value):
            continue

        if direction == "above":
            breached = value > benchmark
        elif direction == "below":
            breached = value < benchmark
        else:
            raise ValueError(f"Unknown direction '{direction}' for metric '{metric}'")

        records.append({
            "teammate_id": teammate_id,
            "metric": metric,
            "value": value,
            "benchmark": benchmark,
            "breached": breached,
        })

    return records