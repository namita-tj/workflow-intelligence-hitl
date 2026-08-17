# Workflow Intelligence & HITL AI

A personal research project exploring whether **tribal operational
intelligence** — undocumented, person-dependent operational knowledge — can
be inferred from delivery workflow data, and prototyping a **Human-in-the-Loop
AI system** to surface it for manager review.

## Project questions

- **Q1:** Can behavioral patterns indicative of tribal operational
  intelligence be surfaced from delivery workflow data using unsupervised
  and anomaly-detection methods, without outcome or interaction data?
- **Q2:** Can a Human-in-the-Loop AI system be designed and prototyped to
  surface, present, and log this inferred operational intelligence for
  manager review?

See `docs/Methodology.md` for full scope, rationale, and methodology.

## Structure

```
notebooks/   Analysis notebooks (correlation, EDA, clustering)
hitl/        Q2 pipeline — rule-based detector, anomaly detector,
             explanation layer, review mechanism, ledger
tests/       pytest suites for hitl/ components
docs/        Methodology and project notes
data/        Processed/derived data only — see note below
outputs/     Generated CSVs/figures (gitignored, regenerate by running notebooks)
```

## Data note

Only cleaned, derived, non-raw data is committed (`data/processed/`). Raw
source files are **not** included here — keep those local only, under
`data/raw/`, which is gitignored. `ledger.jsonl` (runtime output of the HITL
pipeline) is also gitignored, since it's regenerable, not source data.

## Setup

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

## Status

| Area                                                    | Status                                                                                                                                                                                                    |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data collection, cleaning, EDA                          | ~95%                                                                                                                                                                                                      |
| Correlation analysis                                    | ~95%                                                                                                                                                                                                      |
| Clustering (Q1)                                         | ~85% — stability check confirmed on external validation data, not yet on this project's own core data                                                                                                     |
| RF feasibility demo                                     | ~90%                                                                                                                                                                                                      |
| External validation (independent ground-truth datasets) | ~90% — strong result, not yet written up as a clean notebook                                                                                                                                              |
| **HITL pipeline (Q2)**                                  | **100% — all five components (rule-based detector, anomaly detector, explanation layer, review mechanism, ledger) built, tested, and verified working together in a real, fully unmocked end-to-end run** |
| Methodology write-up (planning doc)                     | ~85%                                                                                                                                                                                                      |
| Literature review                                       | ~40% — most sources verified, prose still thin                                                                                                                                                            |
| Results / Discussion / Conclusion                       | Not started                                                                                                                                                                                               |

## Remaining work

- [x] Rule-based benchmark-breach detector — built, tested (`hitl/rule_based_detector.py`)
- [x] DBSCAN-based anomaly detector — built, tested (`hitl/anomaly_detector.py`)
- [x] Explanation layer (LLM-based, constrained generation) — built, tested, verified against a real local LLM (Ollama)
- [x] Human review mechanism — built, tested, manually verified end-to-end (`hitl/review.py`)
- [x] Persistent ledger + full pipeline orchestration — built, tested, verified in a real end-to-end run (`hitl/ledger.py`)
- [ ] Cluster stability check on this project's own core dataset (only validated on external data so far)
- [ ] Expert validation session (not yet scheduled)
- [ ] Results write-up
- [ ] Literature review — remaining sections
- [ ] Introduction, Discussion, Conclusion
- [ ] Final assembly

## Known, documented limitations

- The explanation layer's automated validator checks for factual accuracy
  only — it does not detect soft recommendation language. Across three
  independent live Ollama calls, the model included mild recommendation
  phrasing ("it is essential for the manager to investigate further")
  despite explicit prompt instructions against this. Documented rather than
  engineered away — see `docs/Methodology.md` and `hitl/explanation_layer.py`.
- DBSCAN-based anomaly detection is parameter-sensitive on this project's
  small sample size; results should be treated as candidates for human
  review, not confirmed findings.
