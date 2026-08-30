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
notebooks/   00_KPI_Cleaning_Correlation.ipynb      — data cleaning & correlation
             01_EDA_and_Baseline_Clustering.ipynb   — task-level EDA, K-means baseline
             02_Clustering_Validation_DBSCAN.ipynb  — stability, PCA check, DBSCAN sweep
             03_RF_Synthetic_Feasibility.ipynb      — supervised-learning feasibility test
             04_External_Validation_Metrics.ipynb   — precision/recall/F1 vs. ground truth
hitl/        RQ2 system — rule-based detector, anomaly detector,
             explanation layer, review mechanism, ledger
tests/       pytest suites for hitl/ components
scripts/     Standalone evaluation scripts (e.g. explanation layer
             live-evaluation, run outside the notebook pipeline)
data/        Processed/derived data only — see note below
outputs/     Generated CSVs/figures (gitignored, regenerate by running notebooks)
```

Notebooks 01–02 depend on each other in sequence: `01_...` exports
`teammate_time_allocation_clusters.csv`, which `02_...` loads rather than
recomputing the baseline clustering. Run 01 before 02.

## Data note

Only cleaned, derived, non-raw data is committed (`data/processed/`). Raw
source files are **not** included here and are kept local only, under
`data/raw/`, which is gitignored. `ledger.jsonl` (a runtime artifact of the
HITL system) is likewise gitignored, as it is regenerable rather than
source data. External ground-truth data used for validation (notebook 04)
is cloned fresh at runtime from its own public source and is not committed
here.

## Reproducing the analysis

```bash
pip install -r requirements.txt
pytest tests/ -v
jupyter notebook
```

To run the full HITL pipeline against a real finding (requires
[Ollama](https://ollama.com) running locally with a pulled model, e.g.
`ollama pull mistral`):

```python
from hitl.rule_based_detector import find_metric_breaches, THRESHOLDS
from hitl.ledger import process_finding

breaches = find_metric_breaches(some_teammate_row, THRESHOLDS)
result = process_finding(breaches[0], backend="ollama")
```

To run a large-scale, statistical evaluation of the explanation layer
(validation pass rate, recommendation-language frequency, latency),
requiring Ollama running locally:

```bash
python scripts/explanation_layer_evaluation.py
```

## Key Results

| Metric                                 | Value         | Source                                             |
| -------------------------------------- | ------------- | -------------------------------------------------- |
| External validation precision          | 0.667         | 8 independent repositories, published ground truth |
| External validation recall             | 0.150         | Same                                               |
| DBSCAN noise-flag range                | 50%–89%       | Parameter sensitivity sweep, real data             |
| Clustering silhouette score (k=3)      | 0.364         | MinoriLabs' own data                               |
| Explanation layer validation pass rate | 100% (30/30)  | Live Ollama evaluation                             |
| Soft-recommendation rate               | 46.7% (14/30) | Same                                               |
| Mean response latency                  | 25.07s        | Same                                               |

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
  negative-control check against documented project delays, which found
  no behavioral anomaly where the cause was external — indirect
  supporting evidence, not a full outcome validation.
- The explanation layer's automated validator checks for factual accuracy
  only — it does not detect soft recommendation language, as shown in the
  results above. This is documented as a known limitation rather than
  engineered away — see `hitl/explanation_layer.py`. This decision is
  informed by human-AI decision-making literature on automation bias,
  which motivated a deliberate choice not to implement recommendation
  generation in this system.
- DBSCAN-based anomaly detection is parameter-sensitive at this project's
  sample size, as shown in the results above; results are treated as
  candidates for expert review, not confirmed findings, which is the
  central motivation for RQ2's human validation layer.
- The low recall in external validation reflects a structural property of
  the method: flagging only the smallest cluster per case means most true
  positives are missed in cases where many exist (e.g. one repository has
  15 confirmed critical contributors, of which only one could be
  identified).
