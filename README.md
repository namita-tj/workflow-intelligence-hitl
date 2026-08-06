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
jupyter notebook
```

## Status

| Area | Status |
|---|---|
| Data collection, cleaning, EDA | ~95% |
| Clustering (Q1) | ~90% |
| HITL prototype (Q2) | ~85% — *not yet in this repo, see below* |
| RF feasibility demo | ~90% |
| Methodology write-up | ~85% |
| Literature review | ~30–40% |
| Results / Discussion / Conclusion | Not started |

**Missing from this repo:** the HITL copilot demo and pipeline notebook
built in an earlier session aren't available in this environment — add
them here manually (e.g. under a new `hitl/` folder) once you have them.

## Remaining work

- [ ] Cluster stability check (multiple seeds/bootstrap)
- [ ] Expert validation of clusters (domain review)
- [ ] Results write-up
- [ ] Literature review (remaining sections)
- [ ] Introduction, Discussion, Conclusion
- [ ] Final assembly
