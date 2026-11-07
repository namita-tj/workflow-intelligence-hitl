"""Disagreement detection and Fleiss' kappa over ledger entries."""

import pytest

from hitl.agreement import (
    agreement_report,
    conflicting_prior,
    find_disagreements,
    fleiss_kappa,
    interpret_kappa,
    latest_decisions,
)
from hitl.ledger import load_ledger, process_finding


def _entry(teammate, decision, reviewer, metric="Idle Rate", finding_type="rule_breach", ts="2026-01-01"):
    summary = {"metric": metric} if finding_type == "rule_breach" else {"cluster_label": -1, "is_noise": True}
    return {"teammate_id": teammate, "finding_type": finding_type, "finding_summary": summary,
            "decision": decision, "reviewer": reviewer, "timestamp": ts, "annotation": "reason given here"}


def test_fleiss_kappa_matches_the_published_example():
    # Fleiss (1971) worked example as reproduced on Wikipedia: 10 items, 14 raters, kappa = 0.210
    table = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
             [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    assert fleiss_kappa(table) == pytest.approx(0.210, abs=0.001)


def test_fleiss_kappa_edge_cases():
    assert fleiss_kappa([[2, 0], [0, 2], [2, 0]]) == pytest.approx(1.0)  # perfect agreement
    assert fleiss_kappa([[2, 0], [2, 0]]) is None  # everyone always confirms: chance agreement is 1
    assert fleiss_kappa([[1, 0]]) is None  # a single rating is not agreement
    assert fleiss_kappa([[1, 1], [1, 1]]) == pytest.approx(-1.0)  # always split


def test_latest_decision_per_reviewer_counts():
    entries = [_entry("T-1", "confirm", "A"), _entry("T-1", "reject", "A", ts="2026-02-01"),
               _entry("T-1", "reject", "B")]
    assert latest_decisions(entries) == {("T-1", "rule_breach", "Idle Rate"): {"A": "reject", "B": "reject"}}


def test_disagreements_are_found_per_finding():
    entries = [_entry("T-1", "confirm", "A"), _entry("T-1", "reject", "B"),
               _entry("T-1", "confirm", "B", metric="Rework Rate"),  # a different finding
               _entry("T-2", "confirm", "A", finding_type="anomaly"), _entry("T-2", "confirm", "B", finding_type="anomaly")]
    found = find_disagreements(entries)
    assert [(d["teammate_id"], d["metric"]) for d in found] == [("T-1", "Idle Rate")]


def test_agreement_report():
    entries = [_entry("T-1", "confirm", "A"), _entry("T-1", "reject", "B"),
               _entry("T-2", "confirm", "A"), _entry("T-2", "confirm", "B"),
               _entry("T-3", "reject", "A"), _entry("T-3", "reject", "B"),
               _entry("T-4", "confirm", "A")]  # only one reviewer: not counted
    r = agreement_report(entries)
    assert r["findings_with_multiple_reviewers"] == 3 and r["unanimous"] == 2
    assert r["reviewers"] == ["A", "B"] and len(r["disagreements"]) == 1
    assert r["fleiss_kappa"] == pytest.approx(0.333, abs=0.001)


def test_interpret_kappa():
    assert interpret_kappa(None) == "undefined"
    assert interpret_kappa(0.59) == "moderate" and interpret_kappa(0.9) == "almost perfect"
    assert interpret_kappa(-0.1) == "poor"


def _answers(*values):
    it = iter(values)
    return lambda prompt="": next(it)


FINDING = {"finding_type": "rule_breach", "teammate_id": "T-023", "metric": "Idle Rate",
           "value": 0.359, "benchmark": 0.05}


def test_process_finding_records_and_reports_disagreement(tmp_path, capsys):
    ledger = str(tmp_path / "ledger.jsonl")
    first = process_finding(FINDING, backend="none", reviewer="A", input_fn=_answers("confirm", "Idle time is real here."),
                            ledger_path=ledger)
    assert first["disagrees_with"] == []
    second = process_finding(FINDING, backend="none", reviewer="B", input_fn=_answers("reject", "Low project load only."),
                             ledger_path=ledger)
    assert [d["reviewer"] for d in second["disagrees_with"]] == ["A"]
    assert "disagrees with 1 earlier review" in capsys.readouterr().out
    assert len(load_ledger(ledger)) == 2  # both decisions kept, nothing overridden


def test_blind_review_hides_prior_decisions_but_still_flags_conflict(tmp_path, capsys):
    ledger = str(tmp_path / "ledger.jsonl")
    process_finding(FINDING, backend="none", reviewer="A", input_fn=_answers("confirm", "Idle time is real here."),
                    ledger_path=ledger)
    capsys.readouterr()
    result = process_finding(FINDING, backend="none", reviewer="B", input_fn=_answers("reject", "Low project load only."),
                             ledger_path=ledger, blind=True)
    out = capsys.readouterr().out
    assert "previously reviewed" not in out  # the earlier decision was not shown
    assert result["disagrees_with"]  # but the conflict is recorded


def test_conflicting_prior():
    prior = [{"decision": "confirm"}, {"decision": "reject"}, {"decision": None}]
    assert conflicting_prior("confirm", prior) == [{"decision": "reject"}]
    assert conflicting_prior("reject", None) == []
