"""
Explanation Layer — Rigorous End-to-End Evaluation

Runs many real Ollama calls across a realistic mix of findings and measures,
with actual statistics rather than a handful of hand-picked examples:

  1. Validation pass rate      — % of real responses that pass validate_response()
  2. Recommendation-language rate — % of real responses containing soft-recommendation
                                     phrasing, despite the prompt explicitly forbidding it
  3. Response latency           — mean/median/min/max time per call
  4. Fallback trigger rate      — % of findings that ended up using the deterministic
                                     fallback template rather than a real LLM response

Run this on your own machine, where Ollama is actually installed and running
(`ollama serve`, with a model pulled, e.g. `ollama pull mistral`).

Usage: python explanation_layer_evaluation.py
"""

import time
import re
import statistics
from hitl.explanation_layer import (
    normalize_finding, build_prompt, call_llm, validate_response,
    fallback_explanation, explain_finding,
)

# Recommendation-language patterns — a simple, transparent heuristic, not a
# claim of perfect detection. Documented explicitly so results are honestly
# interpretable rather than treated as ground truth.
RECOMMENDATION_PATTERNS = [
    r"\bshould\b", r"\brecommend", r"\bneeds? to\b", r"\bimportant (that|for)\b",
    r"\bmust\b", r"\bought to\b", r"\bit is (essential|critical|necessary)\b",
]

def contains_recommendation_language(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in RECOMMENDATION_PATTERNS)


# A realistic mix of findings — mirrors the actual variety this system
# encounters: real MinoriLabs individuals across both finding types.
TEST_FINDINGS = [
    {"finding_type": "rule_breach", "metric": "Idle Rate", "value": 0.359, "benchmark": 0.05, "teammate_id": "T-023"},
    {"finding_type": "rule_breach", "metric": "ETA Achievement", "value": 0.391, "benchmark": 1.0, "teammate_id": "T-018"},
    {"finding_type": "rule_breach", "metric": "Rework Rate", "value": 0.369, "benchmark": 0.10, "teammate_id": "T-018"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-018"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-022"},
    {"finding_type": "anomaly", "cluster_label": -1, "is_noise": True, "teammate_id": "T-023"},
]

N_RUNS_PER_FINDING = 5  # repeat each finding this many times to capture LLM variability


def main():
    results = []

    for finding in TEST_FINDINGS:
        for run_idx in range(N_RUNS_PER_FINDING):
            normalized = normalize_finding(finding)
            prompt = build_prompt(normalized)

            start = time.time()
            llm_response = call_llm(prompt, backend="ollama")
            elapsed = time.time() - start

            if llm_response is None:
                results.append({
                    "finding": finding, "run": run_idx, "response": None,
                    "latency": elapsed, "passed_validation": False,
                    "has_recommendation_language": None, "used_fallback": True,
                })
                continue

            passed = validate_response(llm_response, normalized)
            has_rec_lang = contains_recommendation_language(llm_response)

            results.append({
                "finding": finding, "run": run_idx, "response": llm_response,
                "latency": elapsed, "passed_validation": passed,
                "has_recommendation_language": has_rec_lang,
                "used_fallback": not passed,
            })

            print(f"[{finding.get('teammate_id')} / {finding['finding_type']} / run {run_idx}] "
                  f"passed={passed}, rec_language={has_rec_lang}, latency={elapsed:.2f}s")

    # --- Aggregate statistics ---
    n = len(results)
    n_llm_available = sum(1 for r in results if r["response"] is not None)
    n_passed = sum(1 for r in results if r["passed_validation"])
    n_rec_language = sum(1 for r in results if r["has_recommendation_language"])
    n_fallback = sum(1 for r in results if r["used_fallback"])
    latencies = [r["latency"] for r in results if r["response"] is not None]

    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    print(f"Total calls: {n}")
    print(f"LLM available (non-null response): {n_llm_available}/{n} ({n_llm_available/n*100:.1f}%)")
    print(f"Passed validate_response(): {n_passed}/{n} ({n_passed/n*100:.1f}%)")
    print(f"Fallback triggered: {n_fallback}/{n} ({n_fallback/n*100:.1f}%)")
    if n_llm_available:
        print(f"Contains recommendation language (heuristic): {n_rec_language}/{n_llm_available} ({n_rec_language/n_llm_available*100:.1f}%)")
    if latencies:
        print(f"Latency — mean: {statistics.mean(latencies):.2f}s, median: {statistics.median(latencies):.2f}s, "
              f"min: {min(latencies):.2f}s, max: {max(latencies):.2f}s")

    return results


if __name__ == "__main__":
    main()