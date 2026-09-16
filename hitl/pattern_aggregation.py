"""
Pattern aggregation: groups rule_breach findings that share the same
breached metric, so a reviewer sees "N other teammates also breached
this metric this run" rather than reviewing each in complete isolation.

This directly generalizes the T-022/T-023 pattern (both showed elevated
Idle Rate) into a reusable mechanism, rather than relying on that specific
pairing being hardcoded or noticed by chance.

Design note: DBSCAN's cluster_label is NOT used as the grouping signal
for anomaly findings. Every noise point shares cluster_label = -1 by
definition, so grouping on that would lump every anomaly into one
meaningless group. Shared metric breach (for rule_breach findings) is
the concrete, meaningful signal used instead. Anomaly-type findings are
not grouped by this mechanism — they remain presented individually,
which is itself an honest limitation, not an oversight (see Future Work).
"""


def group_by_shared_metric(findings: list[dict]) -> dict:
    """
    Group rule_breach findings by their breached metric.

    Parameters
    ----------
    findings : list[dict]
        Raw findings as produced by run_rule_based_detection() /
        run_anomaly_detection() in main.py — each must have at minimum
        'finding_type' and, for rule_breach, 'metric' and 'teammate_id'.

    Returns
    -------
    dict
        {metric_name: [teammate_id, ...]}, only for metrics breached by
        2 or more teammates. Metrics breached by only one teammate are
        omitted, since a group of one is not a co-occurrence.
    """
    by_metric: dict = {}
    for f in findings:
        if f.get("finding_type") != "rule_breach":
            continue
        metric = f.get("metric")
        teammate_id = f.get("teammate_id")
        if metric is None or teammate_id is None:
            continue
        by_metric.setdefault(metric, []).append(teammate_id)

    return {metric: ids for metric, ids in by_metric.items() if len(ids) >= 2}


def get_co_occurring_teammates(
    teammate_id: str,
    metric: str,
    grouped: dict,
) -> list[str]:
    """
    Given a specific finding's teammate and metric, return the OTHER
    teammate IDs who share the same metric breach (excluding this
    teammate themselves).

    Parameters
    ----------
    teammate_id : str
        The current finding's teammate.
    metric : str
        The current finding's breached metric.
    grouped : dict
        Output of group_by_shared_metric().

    Returns
    -------
    list[str]
        Other teammate IDs sharing this metric breach. Empty list if none.
    """
    ids = grouped.get(metric, [])
    return [i for i in ids if i != teammate_id]