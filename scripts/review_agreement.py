"""
How far do reviews in the ledger agree?

Lists every finding that has been both confirmed and rejected, and computes
Fleiss' kappa over the findings reviewed by two or more reviewers (each
reviewer's latest decision counts). For a meaningful kappa, reviewers should
review independently: run main.py with --blind-review for each of them.

Usage: python scripts/review_agreement.py [--ledger ledger.jsonl]
"""

import argparse
import sys
from pathlib import Path

# Make the repository root importable when run as `python scripts/<name>.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hitl.agreement import agreement_report, interpret_kappa  # noqa: E402
from hitl.ledger import load_ledger  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger", default="ledger.jsonl")
    args = parser.parse_args(argv)

    entries = load_ledger(args.ledger)
    if not entries:
        print(f"No reviews found in {args.ledger}.")
        return 1
    report = agreement_report(entries)
    print(f"{len(entries)} review(s) in {args.ledger}")
    print(f"Findings reviewed by 2+ reviewers: {report['findings_with_multiple_reviewers']} "
          f"(reviewers: {', '.join(report['reviewers']) or '-'}), unanimous: {report['unanimous']}")
    kappa = report["fleiss_kappa"]
    print(f"Fleiss' kappa: {'undefined' if kappa is None else f'{kappa:.3f}'} ({interpret_kappa(kappa)})")
    if report["disagreements"]:
        print("\nFindings with conflicting decisions:")
        for d in report["disagreements"]:
            print(f"- {d['teammate_id']} {d['finding_type']} {d['metric'] or ''}")
            for r in d["reviews"]:
                print(f"    {r['timestamp']}  {r['reviewer']}: {r['decision']} - {r['annotation']}")
    else:
        print("No conflicting decisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
