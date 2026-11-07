"""
Synthetic KPI export with the same shape as the private MinoriLabs file, so
anyone can run the whole pipeline (detect -> explain -> review -> ledger)
without access to real data.

Everything here is invented: 20 fictional teammates (D-01 to D-20, "D" for
demo), random but reproducible numbers, and a few patterns planted on purpose
so the detectors have something to find:

    D-05  spends a large share of hours on rework, and breaches Rework Rate
    D-12  mostly idle, breaches Idle Rate
    D-13  the same idle-heavy profile as D-12: a pair, like T-022/T-023 in the thesis
    D-17  every hour logged under "Others", a recording artefact like T-004
    D-08  breaches Meeting Overhead Ratio only (a rule breach without an unusual profile)
    D-20  no logged hours at all: excluded, like T-001

The two sheets use the real sheet and column names ("Phase 1 - KPI Summary"
with Teammate ID, Total Billable Hrs and the 7 input ratios; "Raw Data" with
Teammate ID, Capability, Task Category and Month Total (hrs)), including the
quirks the cleaning step handles: fully empty output-KPI columns and "-"
placeholders.

Usage:
    python demo/make_demo_data.py                       # writes demo/demo_kpi_export.xlsx
    python demo/make_demo_data.py --out somewhere.xlsx --seed 7
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TASK_CATEGORIES = [
    "Production", "Rework", "QC", "Meetings", "Learning",
    "Idle", "Client Communication", "Planning", "Documentation", "Others",
]
# A typical teammate's share of hours per category (sums to 1)
TYPICAL_SHARES = np.array([0.46, 0.04, 0.10, 0.08, 0.05, 0.02, 0.10, 0.07, 0.06, 0.02])
CAPABILITIES = ["Webtech", "Graphics", "Search Advertising", "Content", "Data"]

PLANTED = {
    "D-05": "rework-heavy profile and a Rework Rate breach",
    "D-12": "idle-heavy profile and an Idle Rate breach",
    "D-13": "idle-heavy profile and an Idle Rate breach (pairs with D-12)",
    "D-17": "all hours logged under 'Others'",
    "D-08": "Meeting Overhead Ratio breach only",
    "D-20": "no logged hours (excluded)",
}
# The teammates DBSCAN (eps=4.0, min_samples=3) flags with the default seed. With some
# other seeds the D-12/D-13 pair is not flagged: the same parameter sensitivity the thesis
# reports for DBSCAN at this sample size (Section 4.1.2), visible on purpose.
EXPECTED_NOISE = {"D-05", "D-12", "D-13", "D-17"}


def _shares(rng: np.random.Generator, teammate: str) -> np.ndarray:
    s = TYPICAL_SHARES * rng.uniform(0.85, 1.15, len(TYPICAL_SHARES))
    if teammate == "D-05":
        s[1] = 0.38  # Rework
    elif teammate in ("D-12", "D-13"):
        s[5] = 0.40  # Idle
        s[0] *= 0.6
    elif teammate == "D-17":
        s = np.zeros(len(TYPICAL_SHARES))
        s[-1] = 1.0  # Others only
    return s / s.sum()


def build_demo_export(seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (kpi_summary, raw_data) as DataFrames."""
    rng = np.random.default_rng(seed)
    teammates = [f"D-{i:02d}" for i in range(1, 21)]
    kpi_rows, raw_rows = [], []
    for i, tid in enumerate(teammates):
        hours = 0.0 if tid == "D-20" else float(rng.uniform(120, 165))
        capability = CAPABILITIES[i % len(CAPABILITIES)]
        if hours > 0:
            for category, share in zip(TASK_CATEGORIES, _shares(rng, tid), strict=True):
                if share > 0:
                    raw_rows.append({"Teammate ID": tid, "Capability": capability,
                                     "Task Category": category, "Month Total (hrs)": round(hours * share, 2)})
        row = {
            "Teammate ID": tid,
            "Capability": capability,
            # D-17 logs hours, but none of them as billable (like T-004 in the thesis)
            "Total Billable Hrs": 0.0 if tid == "D-17" else round(hours * rng.uniform(0.7, 0.9), 1),
            "ETA Achievement": round(rng.uniform(1.0, 1.15), 3),
            "Rework Rate": round(rng.uniform(0.02, 0.08), 3),
            "Req. Understanding Ratio": round(rng.uniform(0.05, 0.12), 3),
            "Meeting Overhead Ratio": round(rng.uniform(0.05, 0.12), 3),
            "Idle Rate": round(rng.uniform(0.0, 0.04), 3),
            "Effective Utilisation": round(rng.uniform(0.75, 0.92), 3),
            "Avg Time Per Task (hrs)": round(rng.uniform(2.0, 5.0), 2),
            # output KPIs not yet entered this month: fully empty, dropped by the cleaning step
            "CSAT": np.nan, "Number of Escalations": np.nan, "Number of Defects": np.nan, "KPI Achievement": np.nan,
        }
        if tid == "D-05":
            row["Rework Rate"] = 0.31
        if tid in ("D-12", "D-13"):
            row["Idle Rate"] = 0.28 if tid == "D-12" else 0.24
            row["Effective Utilisation"] = round(rng.uniform(0.72, 0.8), 3)
        if tid == "D-08":
            row["Meeting Overhead Ratio"] = 0.22
        if tid == "D-03":
            row["Req. Understanding Ratio"] = "-"  # undefined ratio, as in the real export
        if tid == "D-20":
            for k in ("ETA Achievement", "Rework Rate", "Req. Understanding Ratio", "Meeting Overhead Ratio",
                      "Idle Rate", "Effective Utilisation", "Avg Time Per Task (hrs)"):
                row[k] = "-"
        kpi_rows.append(row)
    return pd.DataFrame(kpi_rows), pd.DataFrame(raw_rows)


DEFAULT_PATH = Path(__file__).resolve().parent / "demo_kpi_export.xlsx"


def write_demo_export(path: str | Path = DEFAULT_PATH, seed: int = 42) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kpi, raw = build_demo_export(seed)
    with pd.ExcelWriter(path) as writer:
        kpi.to_excel(writer, sheet_name="Phase 1 - KPI Summary", index=False)
        raw.to_excel(writer, sheet_name="Raw Data", index=False)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_PATH))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = write_demo_export(args.out, args.seed)
    print(f"Wrote {out} (20 fictional teammates). Planted patterns:")
    for tid, what in PLANTED.items():
        print(f"  {tid}: {what}")
