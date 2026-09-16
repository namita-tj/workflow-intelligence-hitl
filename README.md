# Workflow Intelligence & HITL AI

A bachelor's thesis investigating whether **tribal operational intelligence**
(undocumented, person-dependent operational knowledge) can be inferred
from delivery workflow data, and whether a **Human-in-the-Loop AI system**
can be designed to surface this intelligence for expert validation, without
replacing human judgment.

The work is grounded in Polanyi's theory of tacit knowledge and the SECI
model of organizational knowledge creation (Nonaka & Takeuchi, 1995), and
positions the proposed system specifically at the Externalization stage of
that model, converting candidate behavioral patterns into an explicit,
persistent, human-validated record.

## Research questions

- **RQ1:** Can behavioral patterns indicative of tribal operational
  intelligence be surfaced from delivery workflow data?
- **RQ2:** Can a Human-in-the-Loop AI system be designed to
  surface and log this inferred operational intelligence for
  expert review?

## Repository structure

```
main.py      End-to-end RQ2 orchestrator — chains real detection, explanation,
             review, and ledger storage into one runnable pipeline (see below)
notebooks/   00_KPI_Cleaning_Correlation.ipynb      — data cleaning & correlation
             01_EDA_and_Baseline_Clustering.ipynb   — task-level EDA, K-means baseline
             02_Clustering_Validation_DBSCAN.ipynb  — stability, PCA check, DBSCAN sweep
             03_RF_Synthetic_Feasibility.ipynb      — supervised-learning feasibility test
             04_External_Validation_Metrics.ipynb   — precision/recall/F1 vs. ground truth
hitl/        RQ2 system:
             rule_based_detector.py     — contextual-benchmark threshold checks
             anomaly_detector.py        — DBSCAN-based behavioral outlier detection
             explanation_layer.py       — LLM-based plain-language explanation, with
                                          validation and deterministic fallback
             two_part_prompt.py         — alternative explanation prompt design
                                          (see "Two-part prompt" below)
             review.py                  — human review interface (confirm/reject,
                                          required annotation, prior-review context)
             ledger.py                  — append-only persistent record; orchestrates
                                          explain -> review -> store per finding
             quality_metrics.py         — optional per-call LLM quality logging
             pattern_aggregation.py     — groups findings sharing a breached metric
tests/       pytest suites for hitl/ components
scripts/     Standalone evaluation scripts, run outside the main pipeline:
             explanation_layer_evaluation.py   — original-prompt 30-call evaluation
             two_part_prompt_evaluation.py     — two-part-prompt 30-call evaluation
data/        Processed/derived data only — see note below
outputs/     Generated CSVs/figures (gitignored, regenerate by running notebooks)
```

Notebooks 01–02 depend on each other in sequence: `01_...` exports
`teammate_time_allocation_clusters.csv`, which `02_...` loads rather than
recomputing the baseline clustering. Run 01 before 02.

## Data note

Only cleaned, derived, non-raw data is committed (`data/processed/`). Raw
source files are **not** included here and are kept local only, under
`data/raw/`, which is gitignored. `ledger.jsonl` and `quality_metrics.jsonl`
(runtime artifacts of the HITL system) are likewise gitignored, as they are
regenerable rather than source data. External ground-truth data used for
validation (notebook 04) is cloned fresh at runtime from its own public
source and is not committed here.

## Reproducing the analysis

```bash
pip install -r requirements.txt
pytest tests/ -v
jupyter notebook
```

## Running the full RQ2 pipeline end-to-end

`main.py` chains all HITL components together into one operation: detect
(rule-based + DBSCAN anomaly detection) -> explain -> review -> store,
using real MinoriLabs KPI data. Requires Ollama running locally with the
`mistral` model pulled:

```bash
ollama pull mistral
python main.py --limit 3                    # small test run, 3 findings
python main.py                               # full run, all findings
python main.py --prompt-style two_part       # use the alternative explanation prompt
python main.py --metrics-path quality_metrics.jsonl   # log LLM quality metrics (default path)
```

Place the raw KPI Excel file at
`data/raw/MinoriLabs - Phase 1 KPI Table - May 2026.xlsx` (gitignored; not
committed — see Data note above).

The review step is interactive: you will be prompted for your name, a
confirm/reject decision, and a written annotation for each finding.
Confirmed and rejected findings are both appended to `ledger.jsonl`.

**Recurring findings:** if a finding for the same teammate and metric was
reviewed in a previous run, the reviewer is shown the prior decision,
reviewer, and annotation as context before making a fresh decision. Past
decisions are never auto-applied — this is a deliberate design choice
consistent with this thesis's stance on avoiding automation bias
(Section 3.8.4) — but disagreement between reviews is not currently
detected or flagged; both entries simply persist independently.

**Pattern aggregation:** findings sharing the same breached metric within a
single run are grouped, and a reviewer sees how many other teammates
breached the same metric before making their decision (e.g., this
mechanism independently rediscovers the T-022/T-023 Idle Rate pairing from
raw data, with no hardcoded reference to either individual).

To run a large-scale, statistical evaluation of either explanation prompt
design (validation pass rate, recommendation-language frequency, latency),
requiring Ollama running locally:

```bash
python scripts/explanation_layer_evaluation.py      # original prompt
python scripts/two_part_prompt_evaluation.py         # two-part prompt
```

### Two-part prompt

`hitl/two_part_prompt.py` implements an alternative prompt design
(statistical description + open questions for the reviewer), developed in
response to the soft-recommendation-drift limitation documented below. A
30-call evaluation found this design reduced recommendation-language
occurrence from 46.7% to 0%, with a latency trade-off (25.07s -> 57.24s
mean), and confirmed compatibility with the existing `validate_response()`
logic (30/30 pass). This design has **not** been run through the same full
unit/live-E2E suite that covers the original prompt — treat
`--prompt-style two_part` as experimental until it has been.

## Key Results

| Metric                                     | Value         | Source                                                  |
| ------------------------------------------ | ------------- | ------------------------------------------------------- |
| External validation precision              | 0.667         | 8 independent repositories, published ground truth      |
| External validation recall                 | 0.150         | Same                                                    |
| DBSCAN noise-flag range                    | 50%–89%       | Parameter sensitivity sweep, real data                  |
| Clustering silhouette score (k=3)          | 0.364         | MinoriLabs' own data                                    |
| Explanation layer validation pass rate     | 100% (30/30)  | Live Ollama evaluation, original prompt                 |
| Soft-recommendation rate (original prompt) | 46.7% (14/30) | Same                                                    |
| Soft-recommendation rate (two-part prompt) | 0% (0/30)     | Live Ollama evaluation, `two_part_prompt_evaluation.py` |
| Mean response latency (original prompt)    | 25.07s        | Live Ollama evaluation                                  |
| Mean response latency (two-part prompt)    | 57.24s        | Same                                                    |

No external benchmark exists for the clustering-based metrics above, since
this specific task (passive behavioral clustering for tribal-knowledge
candidate detection) has no established precedent in the literature — see
thesis Section 2.4. Full detail and derivation for each metric is in the
corresponding notebook, listed above.

## Documented limitations

- Per-teammate output data (CSAT, Defects, Escalations, KPI Achievement)
  aligned to the same period and granularity as the behavioral data was
  not obtainable — confirmed across every available source, including
  client-level CSAT histories, project risk trackers, and a portfolio
  dashboard. This is the central structural limitation on RQ1's outcome-
  validation scope. One narrow, period-matched exception was achieved: a
  cross-check against a documented project delay, which found no
  behavioral anomaly where the cause was external — indirect supporting
  evidence, not a full outcome validation.
- The explanation layer's automated validator checks for factual accuracy
  only — it does not detect soft recommendation language, as shown in the
  results above. This is documented as a known limitation rather than
  engineered away for the original prompt — see `hitl/explanation_layer.py`.
  The two-part prompt (above) addresses this specific limitation directly,
  though it introduces its own latency trade-off and lacks equivalent test
  coverage.
- `hitl/quality_metrics.py`'s hallucination check is a narrow heuristic
  (detects only one pattern: a response naming a different known metric as
  breached), not a comprehensive hallucination detector. It has not yet
  been exercised against real, accumulated live-Ollama data — its output
  is only meaningful once run repeatedly, over time, against real findings.
- `hitl/pattern_aggregation.py` currently groups by shared metric breach
  only; it does not group DBSCAN anomaly findings, since every noise point
  shares the same cluster label by definition and would produce a
  meaningless single group. Anomaly findings remain presented individually.
- Neither `quality_metrics.py`, `pattern_aggregation.py`, nor the
  recurring-finding context feature in `review.py`/`ledger.py` carry unit
  test coverage equivalent to the rest of `hitl/` (60 tests); they have
  been manually verified against real and synthetic data but not built out
  to the same testing standard.
- DBSCAN-based anomaly detection is parameter-sensitive at this project's
  sample size, as shown in the results above; results are treated as
  candidates for expert review, not confirmed findings, which is the
  central motivation for RQ2's human validation layer.
- The low recall in external validation reflects a structural property of
  the method: flagging only the smallest cluster per case means most true
  positives are missed in cases where many exist (e.g. one repository has
  15 confirmed critical contributors, of which only one could be
  identified).
