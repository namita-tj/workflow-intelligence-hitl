"""The synthetic demo data: the pipeline runs on it end to end, and the two data-dependent
checks that are skipped without the private file (test_anomaly_detector.py) run here on
synthetic data instead."""

import sys
from pathlib import Path

import pytest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from demo import run_demo  # noqa: E402
from demo.make_demo_data import EXPECTED_NOISE, build_demo_export, write_demo_export  # noqa: E402
from hitl.anomaly_detector import detect_anomalies  # noqa: E402


@pytest.fixture(scope="module")
def export(tmp_path_factory):
    return str(write_demo_export(tmp_path_factory.mktemp("demo") / "demo.xlsx"))


def _matrix(path):
    raw = main.load_raw_task_data(path)
    pivot = raw.pivot_table(index="Teammate ID", columns="Task Category", values="Month Total (hrs)",
                            aggfunc="sum", fill_value=0)
    pivot = pivot.loc[pivot.sum(axis=1) > 0]
    pct = pivot.div(pivot.sum(axis=1), axis=0)
    return StandardScaler().fit_transform(pct.values), pct.index.tolist()


def test_generator_is_reproducible_and_fictional():
    a, _ = build_demo_export(42)
    b, _ = build_demo_export(42)
    assert a.equals(b)
    assert all(t.startswith("D-") for t in a["Teammate ID"])


def test_cleaning_matches_the_documented_steps(export):
    df = main.load_kpi_data(export, verbose=False)
    assert len(df) == 18  # D-20 (no hours) and D-17 (no billable hours) excluded, as T-001/T-004 in the thesis
    assert "CSAT" not in df.columns  # fully empty output KPI dropped
    assert df["Req. Understanding Ratio"].isna().sum() == 1  # "-" placeholder became missing


def test_rule_based_detector_finds_the_planted_breaches(export):
    found = {(f["teammate_id"], f["metric"]) for f in main.run_rule_based_detection(main.load_kpi_data(export, verbose=False))}
    assert found == {("D-05", "Rework Rate"), ("D-08", "Meeting Overhead Ratio"), ("D-12", "Idle Rate"),
                     ("D-13", "Idle Rate")}


def test_known_noise_set_on_synthetic_data(export):
    """Synthetic counterpart of test_anomaly_detector.test_known_noise_set."""
    X, ids = _matrix(export)
    noise = {r["teammate_id"] for r in detect_anomalies(X, ids, eps=4.0, min_samples=3) if r["is_noise"]}
    assert noise == EXPECTED_NOISE


def test_dbscan_parameter_sensitivity_on_synthetic_data(export):
    """Synthetic counterpart of test_anomaly_detector.test_dbscan_parameter_sensitivity_changes_result."""
    X, ids = _matrix(export)
    default = {r["teammate_id"] for r in detect_anomalies(X, ids, eps=4.0, min_samples=3) if r["is_noise"]}
    wider = {r["teammate_id"] for r in detect_anomalies(X, ids, eps=6.0, min_samples=3) if r["is_noise"]}
    assert default != wider


def test_kmeans_smallest_cluster_is_the_recording_artefact(export):
    assert main.run_kmeans_candidate_detection(main.load_raw_task_data(export))["candidates"] == ["D-17"]


def test_demo_runs_end_to_end(tmp_path):
    out = run_demo.run(ledger_path=str(tmp_path / "ledger.jsonl"), export_path=str(tmp_path / "demo.xlsx"))
    assert len(out["findings"]) == 8 and len(out["entries"]) == 16
    report = out["report"]
    assert report["findings_with_multiple_reviewers"] == 8 and report["unanimous"] == 7
    assert [d["teammate_id"] for d in report["disagreements"]] == ["D-08"]
    assert report["fleiss_kappa"] == pytest.approx(0.590, abs=0.001)


def test_main_cli_on_demo_data(export, tmp_path, monkeypatch, capsys):
    answers = iter(["confirm", "Planted rework pattern, confirmed for the demo."] * 2)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    ledger = tmp_path / "ledger.jsonl"
    main.main(["--kpi-file", export, "--backend", "none", "--reviewer", "Tester", "--limit", "2",
               "--ledger-path", str(ledger), "--skip-kmeans"])
    assert "COMPLETE: 2/2 findings processed" in capsys.readouterr().out
    assert len(ledger.read_text().splitlines()) == 2
