import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from hitl.anomaly_detector import detect_anomalies


def _load_real_matrix():
    """Loads the same standardized teammate behavioral matrix used
    throughout this thesis — Raw Data sheet, % time per task category."""
    df = pd.read_excel(
        "data/MinoriLabs - Phase 1 KPI Table - May 2026.xlsx",
        sheet_name="Raw Data",
    )
    pivot = df.pivot_table(
        index="Teammate ID", columns="Task Category",
        values="Month Total (hrs)", aggfunc="sum", fill_value=0,
    )
    pivot = pivot.loc[pivot.sum(axis=1) > 0]
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0)
    X = StandardScaler().fit_transform(pivot_pct.values)
    return X, pivot_pct.index.tolist()


def test_known_noise_set():
    X, teammate_ids = _load_real_matrix()
    result = detect_anomalies(X, teammate_ids, eps=4.0, min_samples=3)
    noise = {r["teammate_id"] for r in result if r["is_noise"]}
    assert noise == {"T-003", "T-004", "T-008", "T-018", "T-022", "T-023"}

def test_dbscan_parameter_sensitivity_changes_result():
    """DBSCAN is parameter-sensitive on the real teammate matrix: a wider
    epsilon changes which teammates get flagged as noise, or eliminates
    the noise set entirely. Documents instability as a tested fact, not
    an anecdote — same caveat this thesis already applies to K-means."""
    X, teammate_ids = _load_real_matrix()

    default_result = detect_anomalies(X, teammate_ids, eps=4.0, min_samples=3)
    wider_result = detect_anomalies(X, teammate_ids, eps=6.0, min_samples=3)

    default_noise = {r["teammate_id"] for r in default_result if r["is_noise"]}
    wider_noise = {r["teammate_id"] for r in wider_result if r["is_noise"]}
    assert default_noise != wider_noise