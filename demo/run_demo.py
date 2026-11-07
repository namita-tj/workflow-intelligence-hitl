"""
The whole HITL pipeline on synthetic data in one command, no Ollama and no
private data needed:

    python demo/run_demo.py

1. writes a synthetic KPI export (demo/make_demo_data.py),
2. runs the rule-based detector, DBSCAN and the informational K-means step,
3. explains each finding (template explanation by default; --backend ollama
   uses the local model like main.py),
4. has two scripted reviewers review every finding independently (blind),
5. writes everything to an append-only ledger and prints the ledger summary,
   the disagreements between the two reviewers and their Fleiss' kappa.

The scripted reviewers only exist so the demo runs unattended. To review the
findings yourself instead:

    python demo/make_demo_data.py
    python main.py --kpi-file demo/demo_kpi_export.xlsx --backend none
"""

import argparse
import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from demo.make_demo_data import PLANTED, write_demo_export  # noqa: E402
from hitl.agreement import agreement_report, interpret_kappa  # noqa: E402
from hitl.ledger import load_ledger, process_finding  # noqa: E402
from hitl.pattern_aggregation import get_co_occurring_teammates, group_by_shared_metric  # noqa: E402


def reviewer_a(finding: dict) -> tuple[str, str]:
    """Confirms every finding as worth discussing, except the recording artefact."""
    if finding["teammate_id"] == "D-17":
        return "reject", "All hours logged under Others; a recording issue, not a behaviour pattern."
    return "confirm", "Deviation is real and worth discussing with the capability manager."


def reviewer_b(finding: dict) -> tuple[str, str]:
    """More sceptical: rejects single-metric breaches without a matching unusual profile."""
    if finding["teammate_id"] == "D-17":
        return "reject", "Logging artefact: every hour sits in the Others category."
    if finding["finding_type"] == "rule_breach" and finding["teammate_id"] == "D-08":
        return "reject", "Meeting time alone; the time profile is otherwise typical for the team."
    if finding["finding_type"] == "anomaly" and finding["teammate_id"] in ("D-12", "D-13"):
        return "confirm", "Idle-heavy profile, shared with a second teammate: likely low project load."
    return "confirm", "Clear deviation from the team, plausible to follow up."


def scripted_input(decide, finding: dict):
    """An input() replacement that answers the review prompts for one finding."""
    decision, annotation = decide(finding)
    answers = iter([decision, annotation])
    return lambda prompt="": next(answers)


DEMO_DIR = ROOT / "demo"


def run(backend: str = "none", ledger_path: str | Path = DEMO_DIR / "demo_ledger.jsonl",
        export_path: str | Path = DEMO_DIR / "demo_kpi_export.xlsx", quiet: bool = True) -> dict:
    export = write_demo_export(export_path)
    ledger = Path(ledger_path)
    if ledger.exists():
        ledger.unlink()  # the demo starts from an empty ledger each time

    df = main.load_kpi_data(str(export), verbose=False)
    raw = main.load_raw_task_data(str(export))
    findings = main.run_rule_based_detection(df) + main.run_anomaly_detection(raw)
    kmeans = main.run_kmeans_candidate_detection(raw)
    groups = group_by_shared_metric(findings)

    print(f"Synthetic export: {export} ({len(df)} active teammates after cleaning)")
    print(f"Findings: {len(findings)}  "
          f"(rule breaches {sum(f['finding_type'] == 'rule_breach' for f in findings)}, "
          f"DBSCAN outliers {sum(f['finding_type'] == 'anomaly' for f in findings)})")
    print(f"K-means smallest cluster (informational only): {kmeans['candidates']}")
    if groups:
        print(f"Shared-metric groups: {groups}")

    for reviewer, decide in (("Reviewer A", reviewer_a), ("Reviewer B", reviewer_b)):
        for finding in findings:
            co = (get_co_occurring_teammates(finding["teammate_id"], finding.get("metric"), groups)
                  if finding["finding_type"] == "rule_breach" else [])
            out = io.StringIO() if quiet else sys.stdout
            with contextlib.redirect_stdout(out):
                process_finding(finding, backend=backend, reviewer=reviewer,
                                input_fn=scripted_input(decide, finding), ledger_path=str(ledger),
                                co_occurring_teammates=co, blind=True)

    entries = load_ledger(str(ledger))
    report = agreement_report(entries)
    print(f"\nLedger: {ledger} ({len(entries)} entries, append-only)")
    for e in entries:
        what = e["finding_summary"].get("metric") or "time-allocation outlier"
        print(f"  {e['reviewer']:<10} {e['teammate_id']}  {e['finding_type']:<11} {what:<24} -> {e['decision']}")
    print(f"\nFindings reviewed by both reviewers: {report['findings_with_multiple_reviewers']}, "
          f"unanimous: {report['unanimous']}")
    for d in report["disagreements"]:
        decisions = ", ".join(f"{r['reviewer']} {r['decision']}" for r in d["reviews"])
        print(f"  disagreement on {d['teammate_id']} {d['finding_type']} {d['metric'] or ''}: {decisions}")
    k = report["fleiss_kappa"]
    print(f"Fleiss' kappa: {'undefined' if k is None else f'{k:.2f}'} ({interpret_kappa(k)})")
    print("\nPlanted patterns, for comparison:")
    for tid, what in PLANTED.items():
        print(f"  {tid}: {what}")
    return {"findings": findings, "entries": entries, "report": report, "kmeans": kmeans}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", default="none", choices=["none", "ollama"])
    parser.add_argument("--verbose", action="store_true", help="show every review screen")
    args = parser.parse_args()
    run(backend=args.backend, quiet=not args.verbose)
