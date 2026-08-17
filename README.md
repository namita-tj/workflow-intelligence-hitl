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
hitl/        Q2 pipeline components — detectors, tested Python modules
tests/       pytest suites for hitl/ components
docs/        Methodology and project notes
data/        Processed/derived data only — see note below
outputs/     Generated CSVs/figures (gitignored, regenerate by running notebooks)
```

## Data note

Only cleaned, derived, non-raw data is committed (`data/processed/`). Raw
source files are **not** included here — keep those local only, under
`data/raw/`, which is gitignored.

## Setup

```bash
pip install -r requirements.txt
pytest tests/ -v
jupyter notebook
```

## Status

| Area                                                    | Status                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data collection, cleaning, EDA                          | ~95%                                                                                                                                                                                                                                                                              |
| Correlation analysis                                    | ~95%                                                                                                                                                                                                                                                                              |
| Clustering (Q1)                                         | ~85% — stability check confirmed on external validation data, not yet on this project's own core data                                                                                                                                                                             |
| RF feasibility demo                                     | ~90%                                                                                                                                                                                                                                                                              |
| External validation (independent ground-truth datasets) | ~90% — strong result, not yet written up as a clean notebook                                                                                                                                                                                                                      |
| **HITL pipeline (Q2)**                                  | **~60% — rule-based detector, anomaly detector, and explanation layer built and tested (26/26 passing); explanation layer verified against a real local LLM (Ollama), with a documented limitation around soft-recommendation detection; review mechanism and ledger still open** |
| Methodology write-up (planning doc)                     | ~85%                                                                                                                                                                                                                                                                              |
| Literature review                                       | ~40% — most sources verified, prose still thin                                                                                                                                                                                                                                    |
| Results / Discussion / Conclusion                       | Not started                                                                                                                                                                                                                                                                       |

## Remaining work

- [x] Rule-based benchmark-breach detector — built, tested (`hitl/rule_based_detector.py`)
- [x] DBSCAN-based anomaly detector — built, tested (`hitl/anomaly_detector.py`)
- [ ] Explanation layer (LLM-based, constrained generation — design decided, not built)
- [ ] Human review mechanism
- [ ] Persistent ledger
- [ ] Cluster stability check on this project's own core dataset (only validated on external data so far)
- [ ] Expert validation session (not yet scheduled)
- [ ] Results write-up
- [ ] Literature review — remaining sections
- [ ] Introduction, Discussion, Conclusion
- [ ] Final assembly
