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

notebooks/ Analysis notebooks (correlation, EDA, clustering)
hitl/ RQ2 system — rule-based detector, anomaly detector,
explanation layer, review mechanism, ledger
tests/ pytest suites for hitl/ components
data/ Processed/derived data only — see note below
outputs/ Generated CSVs/figures (gitignored, regenerate by running notebooks)

## Data note

Only cleaned, derived, non-raw data is committed (`data/processed/`). Raw
source files are **not** included here and are kept local only, under
`data/raw/`, which is gitignored. `ledger.jsonl` (a runtime artifact of the
HITL system) is likewise gitignored, as it is regenerable rather than
source data.

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
  only — it does not detect soft recommendation language. Across three
  independent live Ollama calls, the model included mild recommendation
  phrasing ("it is essential for the manager to investigate further")
  despite explicit prompt instructions against this. This is documented
  as a known limitation rather than engineered away — see
  `hitl/explanation_layer.py`. This decision is
  informed by human-AI decision-making literature on automation bias,
  which motivated a deliberate choice not to implement recommendation
  generation in this system.
- DBSCAN-based anomaly detection is parameter-sensitive at this project's
  sample size; results are treated as candidates for expert review, not
  confirmed findings — this distinction is the central motivation for
  RQ2's human validation layer.
