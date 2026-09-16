"""
main.py — End-to-end RQ2 HITL pipeline orchestrator.

Runs the full detect -> explain -> review -> store flow described in
Section 3.8, using real MinoriLabs Phase 1 KPI data.

This was the one genuinely missing piece: rule_based_detector and
anomaly_detector each produce raw findings, but nothing previously
chained "run the detectors on real data" together with
ledger.process_finding() (which already correctly implements
explain -> review -> store, per the normalization-bug fix documented
in Section 3.9). This script is that missing first step, plus the
top-level loop tying everything together.

Requires:
    - Ollama running locally with the 'mistral' model pulled
      (run diagnose_ollama.py first if unsure)
    - The Phase 1 KPI Table Excel file (path set below)
    - Interactive terminal access for the review step (a human must
      confirm/reject each finding and provide an annotation)

Usage:
    python main.py                      # original prompt, interactive review
    python main.py --prompt-style two_part
    python main.py --limit 3            # only process the first 3 findings
    python main.py --reviewer "Namita"  # skip the reviewer-name prompt
"""

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from hitl.rule_based_detector import find_metric_breaches, THRESHOLDS
from hitl.anomaly_detector import detect_anomalies
from hitl.ledger import process_finding
from hitl.pattern_aggregation import group_by_shared_metric, get_co_occurring_teammates

KPI_FILE_PATH = "data/raw/MinoriLabs - Phase 1 KPI Table - May 2026.xlsx"
KPI_SHEET_NAME = "Phase 1 - KPI Summary"
FEATURE_COLUMNS = [
    "ETA Achievement", "Rework Rate", "Req. Understanding Ratio",
    "Meeting Overhead Ratio", "Idle Rate", "Effective Utilisation",
    "Avg Time Per Task",
]


def load_kpi_data(path: str) -> pd.DataFrame:
    """Load and lightly clean the KPI table, matching Section 3.2's
    documented cleaning steps (exclude zero-activity teammates)."""
    df = pd.read_excel(path, sheet_name=KPI_SHEET_NAME)
    if "Total Billable Hrs" in df.columns:
        df = df[df["Total Billable Hrs"] > 0]
    return df


def run_rule_based_detection(df: pd.DataFrame) -> list:
    """Run the rule-based detector across every teammate row.
    Returns only the findings that actually breach a threshold."""
    findings = []
    for _, row in df.iterrows():
        breaches = find_metric_breaches(row, THRESHOLDS)
        for b in breaches:
            if b.get("breached"):
                findings.append({
                    "finding_type": "rule_breach",
                    "teammate_id": row.get("Teammate ID"),
                    "metric": b.get("metric"),
                    "value": b.get("value"),
                    "benchmark": b.get("threshold", b.get("benchmark")),
                })
    return findings


def run_anomaly_detection(df: pd.DataFrame, eps: float = 4.0, min_samples: int = 3) -> list:
    """Run DBSCAN anomaly detection on the standardized behavioural
    feature matrix, using the same parameters validated in Section 3.8.2.
    Only teammates flagged as noise are returned as findings."""
    feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    if not feature_cols:
        print("WARNING: none of the expected feature columns found; skipping anomaly detection.",
              file=sys.stderr)
        return []

    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
    X_scaled = StandardScaler().fit_transform(X)
    teammate_ids = df["Teammate ID"].tolist()

    results = detect_anomalies(X_scaled, teammate_ids, eps=eps, min_samples=min_samples)
    return [
        {
            "finding_type": "anomaly",
            "teammate_id": r["teammate_id"],
            "cluster_label": r["cluster_label"],
            "is_noise": r["is_noise"],
        }
        for r in results if r.get("is_noise")
    ]


def main():
    parser = argparse.ArgumentParser(description="Run the full RQ2 HITL pipeline end-to-end.")
    parser.add_argument("--kpi-file", default=KPI_FILE_PATH, help="Path to the KPI Excel file.")
    parser.add_argument("--prompt-style", default="original", choices=["original", "two_part"],
                         help="Which explanation prompt design to use.")
    parser.add_argument("--reviewer", default=None, help="Reviewer name (skips interactive prompt).")
    parser.add_argument("--ledger-path", default="ledger.jsonl", help="Output ledger file path.")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only process the first N findings (useful for a quick test run).")
    parser.add_argument("--skip-anomaly", action="store_true", help="Skip DBSCAN anomaly detection.")
    parser.add_argument("--skip-rule-based", action="store_true", help="Skip rule-based detection.")
    parser.add_argument("--metrics-path", default="quality_metrics.jsonl",
                         help="Path to log LLM response quality metrics (recommendation language, potential hallucination).")
    args = parser.parse_args()

    print(f"Loading KPI data from: {args.kpi_file}")
    try:
        df = load_kpi_data(args.kpi_file)
    except FileNotFoundError:
        print(f"ERROR: file not found at '{args.kpi_file}'. "
              f"Pass the correct path with --kpi-file.", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(df)} active teammates.\n")

    all_findings = []
    if not args.skip_rule_based:
        rule_findings = run_rule_based_detection(df)
        print(f"Rule-based detector: {len(rule_findings)} threshold breach(es) found.")
        all_findings.extend(rule_findings)

    if not args.skip_anomaly:
        anomaly_findings = run_anomaly_detection(df)
        print(f"Anomaly detector: {len(anomaly_findings)} teammate(s) flagged as noise.")
        all_findings.extend(anomaly_findings)

    if args.limit:
        all_findings = all_findings[:args.limit]

    print(f"\nTotal findings to process: {len(all_findings)}")
    print(f"Prompt style: {args.prompt_style}")
    print(f"Ledger output: {args.ledger_path}\n")

    if not all_findings:
        print("No findings to process. Exiting.")
        return

    # Compute shared-metric groupings once, using the full batch — this is
    # why co-occurrence can't be computed inside process_finding() itself,
    # which only ever sees one finding at a time.
    grouped_by_metric = group_by_shared_metric(all_findings)
    if grouped_by_metric:
        print("Shared-metric groups found this run:")
        for metric, ids in grouped_by_metric.items():
            print(f"  {metric}: {ids}")
        print()

    results = []
    for i, finding in enumerate(all_findings, 1):
        print(f"\n{'='*60}")
        print(f"Finding {i}/{len(all_findings)}: {finding['teammate_id']} ({finding['finding_type']})")
        print("=" * 60)

        co_occurring = get_co_occurring_teammates(
            finding.get("teammate_id"), finding.get("metric"), grouped_by_metric
        ) if finding.get("finding_type") == "rule_breach" else []

        try:
            result = process_finding(
                finding,
                backend="ollama",
                reviewer=args.reviewer,
                ledger_path=args.ledger_path,
                prompt_style=args.prompt_style,
                metrics_path=args.metrics_path,
                co_occurring_teammates=co_occurring,
            )
            results.append(result)
            print(f"-> Decision: {result['decision']}")
        except Exception as e:
            print(f"ERROR processing this finding: {type(e).__name__}: {e}", file=sys.stderr)
            print("Continuing to next finding...")

    print(f"\n{'='*60}")
    print(f"COMPLETE: {len(results)}/{len(all_findings)} findings processed and logged to {args.ledger_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()