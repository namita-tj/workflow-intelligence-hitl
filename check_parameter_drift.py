"""
check_parameter_drift.py - flags when a new month's clustering diagnostics
differ meaningfully from the last validated run, without automatically
choosing new parameters.

This does NOT re-select k, eps, or minPts automatically. Consistent with
this thesis's core argument (Section 5.1), a genuinely new choice of
clustering parameters is a human judgement call, informed by diagnostics,
not something this script should decide unsupervised. This script's job
is narrower and more honest: compute the same diagnostics used to
originally justify k=3 and eps=4.0/minPts=3, and clearly flag if this
month's numbers suggest those choices should be reviewed.

Usage: python scripts/check_parameter_drift.py --kpi-file <path>
"""

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score

from main import load_raw_task_data

VALIDATED_K = 3
VALIDATED_EPS = 4.0
VALIDATED_MIN_SAMPLES = 3
VALIDATED_SILHOUETTE_AT_K3 = 0.364

DRIFT_THRESHOLD = 0.10


def build_feature_matrix(raw_df):
    pivot = raw_df.pivot_table(
        index="Teammate ID", columns="Task Category",
        values="Month Total (hrs)", aggfunc="sum", fill_value=0,
    )
    pivot = pivot.loc[pivot.sum(axis=1) > 0]
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0)
    return StandardScaler().fit_transform(pivot_pct.values)


def check_k_selection_drift(X):
    results = {}
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        results[k] = silhouette_score(X, km.labels_)

    current_k3_silhouette = results[3]
    drift = abs(current_k3_silhouette - VALIDATED_SILHOUETTE_AT_K3)

    return {
        "silhouette_by_k": results,
        "k3_silhouette": current_k3_silhouette,
        "validated_k3_silhouette": VALIDATED_SILHOUETTE_AT_K3,
        "drift": drift,
        "flagged": drift > DRIFT_THRESHOLD,
        "best_k_this_run": max(results, key=results.get),
    }


def check_dbscan_noise_rate(X):
    db = DBSCAN(eps=VALIDATED_EPS, min_samples=VALIDATED_MIN_SAMPLES).fit(X)
    n_noise = sum(1 for label in db.labels_ if label == -1)
    noise_rate = n_noise / len(db.labels_)
    return {
        "n_noise": n_noise,
        "n_total": len(db.labels_),
        "noise_rate": round(noise_rate, 3),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check whether this month's clustering diagnostics have drifted "
                     "from the originally validated k=3/eps=4.0 choices."
    )
    parser.add_argument("--kpi-file", required=True, help="Path to this month's KPI Excel file.")
    args = parser.parse_args()

    try:
        raw_df = load_raw_task_data(args.kpi_file)
    except FileNotFoundError:
        print(f"ERROR: file not found at '{args.kpi_file}'.", file=sys.stderr)
        sys.exit(1)

    X = build_feature_matrix(raw_df)

    print(f"\n{'='*60}")
    print("PARAMETER DRIFT CHECK")
    print("=" * 60)
    print(f"Teammates this run: {X.shape[0]}\n")

    k_result = check_k_selection_drift(X)
    print("Silhouette scores by k (this run):")
    for k, score in k_result["silhouette_by_k"].items():
        marker = " <- validated choice" if k == VALIDATED_K else ""
        print(f"  k={k}: {score:.3f}{marker}")

    print(f"\nk=3 silhouette: {k_result['k3_silhouette']:.3f} "
          f"(originally validated: {k_result['validated_k3_silhouette']:.3f}, "
          f"drift: {k_result['drift']:.3f})")

    if k_result["flagged"]:
        print(f"\n  *** FLAGGED: k=3's silhouette score has drifted by more than "
              f"{DRIFT_THRESHOLD} from the originally validated run. ***")
        print(f"  This month's best-scoring k is k={k_result['best_k_this_run']}.")
        print("  RECOMMENDATION: a human should review this month's diagnostics "
              "before trusting k=3 clustering results without re-validation.")
    else:
        print("\n  No significant drift detected. k=3 remains consistent with "
              "the originally validated choice.")

    db_result = check_dbscan_noise_rate(X)
    print(f"\nDBSCAN noise rate at validated eps={VALIDATED_EPS}, "
          f"minPts={VALIDATED_MIN_SAMPLES}: "
          f"{db_result['n_noise']}/{db_result['n_total']} "
          f"({db_result['noise_rate']*100:.1f}%)")

    print(f"\n{'='*60}")
    print("This script flags potential drift; it does NOT select new "
          "parameters. Any change to k, eps, or minPts remains a human "
          "decision, informed by these diagnostics (Section 5.1).")
    print("=" * 60)


if __name__ == "__main__":
    main()