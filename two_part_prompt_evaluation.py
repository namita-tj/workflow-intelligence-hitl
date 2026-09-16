"""
Two-Part Prompt Evaluation — Statistical Description + Knowledge-Hypothesis Questions

Runs the same 30-call evaluation as explanation_layer_evaluation.py, but using
the new two-part prompt (hitl/two_part_prompt.py) instead of the original
single-block prompt. Results are directly comparable to the original 46.7%
soft-recommendation baseline.

Additionally checks for "disguised recommendations" — cases where Part 2
contains a directive phrased as a question, which would NOT count as a
genuine open question under this design's own stated goal.

Saves full results (including raw response text) to
two_part_prompt_results.json, so individual responses can be reviewed or
quoted afterward, and so a mid-run failure does not lose completed results.

Usage: python two_part_prompt_evaluation.py
"""

import time
import re
import json
import statistics
import sys
from datetime import datetime, timezone

from hitl.explanation_layer import normalize_finding, call_llm
from hitl.two_part_prompt import build_two_part_prompt

RECOMMENDATION_PATTERNS = [
    r"\bshould\b", r"\brecommend", r"\bneeds? to\b", r"\bimportant (that|for)\b",
    r"\bmust\b", r"\bought to\b", r"\bit is (essential|critical|necessary)\b",
]

DISGUISED_QUESTION_PATTERNS = [
    r"have you considered", r"why not (try|consider)",
    r"you (should|might want to) consider", r"wouldn't it be (better|wise|advisable)",
]

TEST_FINDINGS = [
    {"finding_type": "rule_breach", "metric": "Idle Rate", "value": 0.359, "benchmark": 0.05, "teammate_id": "T-023"},
    {"finding_type": "rule_breach", "metric": "ETA Achievement", "value": 0.391, "benchmark": 1.0, "teammate_id": "T-018"},
    {"finding_type": "rule_breach", "metric": "Rework Rate", "value": 0.369, "benchmark": 0.10, "teammate_id": "T-018"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-018"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-022"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-023"},
]

N_RUNS_PER_FINDING = 5
OUTPUT_FILE = "two_part_prompt_results.json"


def contains_recommendation_language(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in RECOMMENDATION_PATTERNS)


def contains_disguised_question(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in DISGUISED_QUESTION_PATTERNS)


def contains_genuine_question(text: str) -> bool:
    return "?" in text


def save_results(results: list, partial: bool = False) -> None:
    """Persist results to disk after every call, so a crash mid-run never
    loses completed work."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial_run": partial,
        "n_runs_per_finding": N_RUNS_PER_FINDING,
        "results": results,
    }
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError as e:
        print(f"WARNING: could not write results file ({e}). Continuing anyway.", file=sys.stderr)


def run_single_call(finding: dict, run_idx: int) -> dict:
    """Run one finding through the two-part prompt and LLM. Never raises —
    any failure is recorded in the result dict instead, so one bad call
    cannot abort the whole evaluation."""
    entry = {
        "teammate_id": finding.get("teammate_id"),
        "finding_type": finding.get("finding_type"),
        "run_index": run_idx,
        "response": None,
        "latency_seconds": None,
        "error": None,
    }

    try:
        normalized = normalize_finding(finding)
        prompt = build_two_part_prompt(normalized)
    except Exception as e:
        entry["error"] = f"prompt construction failed: {e}"
        return entry

    start = time.time()
    try:
        llm_response = call_llm(prompt, backend="ollama")
    except Exception as e:
        entry["latency_seconds"] = round(time.time() - start, 2)
        entry["error"] = f"call_llm raised an exception: {e}"
        return entry

    entry["latency_seconds"] = round(time.time() - start, 2)

    if llm_response is None:
        entry["error"] = "call_llm returned None (LLM unavailable or fallback triggered)"
        return entry

    entry["response"] = llm_response
    entry["has_recommendation_language"] = contains_recommendation_language(llm_response)
    entry["has_disguised_question"] = contains_disguised_question(llm_response)
    entry["has_genuine_question"] = contains_genuine_question(llm_response)
    return entry


def print_summary(results: list) -> None:
    n = len(results)
    successful = [r for r in results if r["response"] is not None]
    n_ok = len(successful)
    n_errors = n - n_ok

    print("\n" + "=" * 70)
    print("TWO-PART PROMPT — AGGREGATE RESULTS")
    print("=" * 70)
    print(f"Total calls attempted: {n}")
    print(f"Successful responses: {n_ok}/{n}")
    if n_errors:
        print(f"Errors/unavailable: {n_errors}/{n} — see '{OUTPUT_FILE}' for details")

    if n_ok:
        n_rec_lang = sum(1 for r in successful if r["has_recommendation_language"])
        n_disguised = sum(1 for r in successful if r["has_disguised_question"])
        n_genuine_q = sum(1 for r in successful if r["has_genuine_question"])
        latencies = [r["latency_seconds"] for r in successful]

        print(f"Recommendation language present: {n_rec_lang}/{n_ok} ({n_rec_lang/n_ok*100:.1f}%)")
        print(f"Disguised questions (directive-as-question): {n_disguised}/{n_ok} ({n_disguised/n_ok*100:.1f}%)")
        print(f"Contains a genuine question mark: {n_genuine_q}/{n_ok} ({n_genuine_q/n_ok*100:.1f}%)")
        print(f"Latency — mean: {statistics.mean(latencies):.2f}s, median: {statistics.median(latencies):.2f}s")

        print("\nCOMPARISON TO ORIGINAL PROMPT BASELINE:")
        print("  Original soft-recommendation rate: 46.7% (14/30)")
        print(f"  Two-part prompt rate: {n_rec_lang/n_ok*100:.1f}% ({n_rec_lang}/{n_ok})")
    else:
        print("\nNo successful responses — check Ollama is running and reachable.")

    print(f"\nFull results (including raw response text) saved to: {OUTPUT_FILE}")


def main():
    total_calls = len(TEST_FINDINGS) * N_RUNS_PER_FINDING
    print(f"Starting evaluation: {len(TEST_FINDINGS)} findings x {N_RUNS_PER_FINDING} "
          f"runs = {total_calls} total calls.")
    print(f"Results will be saved incrementally to '{OUTPUT_FILE}'.\n")

    results = []
    call_num = 0

    for finding in TEST_FINDINGS:
        for run_idx in range(N_RUNS_PER_FINDING):
            call_num += 1
            entry = run_single_call(finding, run_idx)
            results.append(entry)

            save_results(results, partial=(call_num < total_calls))

            status = "ERROR" if entry["error"] else "ok"
            extra = ""
            if entry["response"] is not None:
                extra = (f" rec_lang={entry['has_recommendation_language']} "
                         f"disguised_q={entry['has_disguised_question']} "
                         f"has_question={entry['has_genuine_question']}")
            print(f"[{call_num}/{total_calls}] {entry['teammate_id']} / "
                  f"{entry['finding_type']} / run {run_idx} -> {status}"
                  f"{' (' + entry['error'] + ')' if entry['error'] else ''}"
                  f"{extra} latency={entry['latency_seconds']}s")

    save_results(results, partial=False)
    print_summary(results)


if __name__ == "__main__":
    main()