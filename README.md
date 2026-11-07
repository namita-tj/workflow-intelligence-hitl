![Tests](https://github.com/namita-tj/workflow-intelligence-hitl/actions/workflows/tests.yml/badge.svg)

# A Human-in-the-Loop System for Surfacing and Validating Tribal Knowledge from Organisational Workflow Data

This is the code for my bachelor's thesis in Computer Science (B.Sc. Informatik) at TH Bingen, written with
MinoriLabs, a digital marketing organisation (submitted September 2026, grade 1.0).

**The question:** a lot of what a delivery team knows is never written down and sits with a few people
("tribal knowledge"). Capturing it usually means interviews or documentation, which costs time from exactly
those people. I wanted to find out whether you can instead infer *where* that knowledge sits from records that
already exist, in this case timesheets, and whether a human-in-the-loop (HITL) system can help an expert check
what comes out.

**The answer, in short:** timesheet data can point to events worth talking about, but not reliably to the people
who hold tribal knowledge.

- The pipeline surfaced six candidate cases and two patterns at the level of a practice (capability).
- A MinoriLabs Capability Manager explained every one of them by an operational cause, such as a staffing
  change, a project starting or ending, or seasonal client demand. None was explained by tribal knowledge.
- As a positive control, he named two knowledge holders before seeing any results. The pipeline flagged one of
  them, for an unrelated reason, and missed the other. That is no better than chance.

So the statistics found *where* things deviated, and the expert was needed to say *what* it meant. That is
also why the second half of the project, the HITL system, exists.

## Try it in two minutes (synthetic data)

The real data can't be published, so `demo/` generates a fake KPI export in exactly the same format: 20
invented teammates with a few planted patterns (a rework-heavy profile, an idle pair, a recording artefact).

```bash
pip install -r requirements.txt
python demo/run_demo.py
```

This runs the whole loop (detect → explain → review → ledger) without Ollama. Two scripted reviewers review
every finding independently, and at the end you see the ledger, where they disagreed and their Fleiss' kappa.
To be the reviewer yourself:

```bash
python demo/make_demo_data.py
python main.py --kpi-file demo/demo_kpi_export.xlsx --backend none
```

## Research questions

- **RQ1:** Can tribal knowledge be inferred from timesheet-based workflow data within an organisation through
  uncovering behavioural patterns?
- **RQ2:** Can a HITL AI system be designed to support expert validation of surfaced behavioural candidates and
  log confirmed findings for organisational reference?

## How it works

**RQ1, finding candidates** (`notebooks/`). Each teammate is described by how their logged hours split across
10 task categories (22 active teammates, May 2026). Three methods look for people who deviate from the team:

- K-means clustering (k = 3), where the smallest cluster gives the candidates;
- DBSCAN anomaly detection, swept over a grid of parameters because it is sensitive to them;
- rule-based thresholds taken from MinoriLabs' own KPI benchmarks.

Because MinoriLabs' data has no ground truth, I also ran the same candidate logic on eight public software
repositories whose critical contributors are known (truck-factor datasets).

**RQ2, the HITL system** (`hitl/`, run by `main.py`). Five components run in sequence:

1. **Rule-based detector:** checks each teammate's KPIs against the thresholds.
2. **Anomaly detector:** DBSCAN on the time-allocation profiles (ε = 4.0, minPts = 3).
3. **Explanation layer:** a local model (Mistral 7B via Ollama, so no data leaves the machine) explains each
   finding in plain language. A validator checks the response, with a deterministic fallback.
4. **Review:** the reviewer has to confirm or reject each finding and write a justification. The system never
   recommends a decision.
5. **Ledger:** every decision goes into an append-only record.

## Key results

| Result | Value | Thesis |
| --- | --- | --- |
| Expert validation of the 6 individual candidate cases | 6 of 6 explained by operational causes, 0 by tribal knowledge | 4.1.7 |
| Positive control (2 knowledge holders named in advance) | 1 flagged, for an unrelated reason; no better than chance | 4.1.7 |
| External validation on 8 truck-factor repositories | 5 of 8 correct; precision 0.667, recall 0.150, F1 0.245 | 4.1.3 |
| K-means silhouette score (k = 3, MinoriLabs data) | 0.364 | 3.2.1 |
| DBSCAN noise rate of flagged teammates | 51.9% to 88.9% across 27 parameter settings | 4.1.2 |
| Unit tests at submission | 60 (58 pass, 2 skipped without the private data file); 111 today, with the demo and the newer modules | 4.2.1 |
| Code coverage at submission, five core components | 80% (ledger 100%, review 98%, rule detector 88%, explanation 77%, anomaly detector 16%) | 4.2.3 |
| Defects found and fixed | 5 (3 by unit tests, 2 only by live end-to-end runs) | 4.2.2, 4.2.8 |
| Explanation validator pass rate (30 live calls) | 100% (30/30) | 4.2.6 |
| Recommendation language, original prompt | 46.7% (14/30) | 4.2.6 |
| Recommendation language, two-part prompt | 0% (0/30) | 4.2.7 |
| Mean response latency, original vs. two-part prompt | 25.07 s vs. 57.24 s | 4.2.6, 4.2.7 |

The 100% pass rate next to 46.7% recommendation language is the point of that test: the validator only checks
facts, so a response can pass while still telling the reviewer what to do. The two-part prompt (a bare
statistical statement, then open questions for the reviewer) fixed that, at the cost of more than double the
response time. No external benchmark exists for the clustering-based numbers, because this specific task has no
established precedent (thesis Section 2.4).

## Repository structure

```
main.py      End-to-end RQ2 pipeline: detect -> explain -> review -> store
hitl/        The HITL system
             rule_based_detector.py   threshold checks against MinoriLabs' KPI benchmarks (Appendix B)
             anomaly_detector.py      DBSCAN-based outlier detection
             explanation_layer.py     plain-language explanation with validation and fallback
             two_part_prompt.py       the redesigned prompt (statistical statement + open questions)
             review.py                confirm/reject with a required annotation and prior-review context
             ledger.py                append-only record; runs explain -> review -> store per finding,
                                      flags disagreement with earlier reviews
             agreement.py             disagreements and Fleiss' kappa across reviewers
             quality_metrics.py       optional per-call quality log for the explanation layer
             pattern_aggregation.py   groups findings that breach the same metric
notebooks/   00_KPI_Cleaning_Correlation.ipynb     data cleaning and correlation
             01_EDA_and_Baseline_Clustering.ipynb  exploratory analysis, K-means baseline
             02_Clustering_Validation_DBSCAN.ipynb seed stability, PCA check, DBSCAN sweep
             03_RF_Synthetic_Feasibility.ipynb     can a supervised model work at this sample size?
             04_External_Validation_Metrics.ipynb  precision/recall on the truck-factor datasets
scripts/     explanation_layer_evaluation.py       30 live calls, original prompt
             two_part_prompt_evaluation.py         30 live calls, two-part prompt
             check_parameter_drift.py              flags when a new month's data no longer fits k = 3 / eps = 4.0
             review_agreement.py                   disagreements and Fleiss' kappa for a ledger
demo/        make_demo_data.py   synthetic KPI export in the real format
             run_demo.py         the whole pipeline on it, with two scripted reviewers
tests/       pytest suites for hitl/, the demo data and main.py
```

Run notebook 01 before 02: 01 writes `teammate_time_allocation_clusters.csv` (local, gitignored), which 02 loads.

## Data note

No MinoriLabs data is in this repository, raw or processed. The KPI export and everything derived from it
(cleaned tables, cluster assignments) stay local: `data/raw/` and `data/processed/` are gitignored, and the
notebooks are saved without outputs. The ledger and quality-metrics files written at runtime are gitignored too.
The external truck-factor datasets used in notebook 04 are downloaded at runtime from their public source.

## Running it

```bash
pip install -r requirements.txt
pytest tests/ -v
jupyter notebook
```

With the real data, the full RQ2 pipeline needs the KPI export at
`data/MinoriLabs - Phase 1 KPI Table - May 2026.xlsx` (gitignored) and Ollama with the Mistral model:

```bash
ollama pull mistral
python main.py --limit 3                              # quick run, 3 findings
python main.py                                        # all findings
python main.py --prompt-style two_part                # the redesigned prompt
python main.py --metrics-path quality_metrics.jsonl   # log explanation quality per call
python main.py --reviewer Anna --blind-review         # independent review, earlier decisions hidden
python scripts/review_agreement.py                    # disagreements and Fleiss' kappa in the ledger
python scripts/explanation_layer_evaluation.py        # 30-call evaluation, original prompt
python scripts/two_part_prompt_evaluation.py          # 30-call evaluation, two-part prompt
python scripts/check_parameter_drift.py --kpi-file <path to a new month's export>
```

The review step is interactive: you enter your name, a confirm/reject decision and a written annotation for each
finding, and both confirmed and rejected findings are appended to `ledger.jsonl`.

If the same teammate and metric were reviewed in an earlier run, the reviewer sees the earlier decision and
annotation as context. Past decisions are never applied automatically, because that would bring back the
automation bias the design is meant to avoid (thesis Sections 3.3.4 and 3.5). When a new decision contradicts an
earlier one, both stay in the ledger, the conflict is shown and recorded (`disagrees_with`), and
`scripts/review_agreement.py` lists every such case.

**Several reviewers.** For an agreement measure the reviews have to be independent, so each reviewer runs
`main.py --blind-review`, which hides earlier decisions. `scripts/review_agreement.py` then reports Fleiss' kappa
over the findings reviewed by two or more people (thesis Section 6.2, "Consensus across Multiple Reviewers").

Findings that breach the same metric in one run are grouped, so the reviewer sees how many other teammates have
the same breach. This grouping rediscovers the T-022/T-023 Idle Rate pairing from the raw data, with no
hard-coded reference to either person.

## Limitations

These follow thesis Section 5.5, plus what is specific to the code:

- **One organisation, one month, 22 people.** Clustering 22 teammates in a 10-dimensional space is unstable;
  seed-stability runs and PCA checks reduce this but can't remove it. Some capability findings rest on n = 2.
- **DBSCAN is parameter-sensitive** at this sample size, which is why every finding is a candidate for review
  and not a result.
- **Recall is limited by design** in the external validation: only the smallest cluster is flagged, so most
  critical contributors are missed when a repository has many.
- **One reviewer, not blinded,** corroborated for one case by a second Capability Manager. The system was
  demonstrated to him, not used by him, so there is no formal usability evaluation.
- **The validator knows a fixed list of paraphrases.** Since the thesis, it accepts plain-language descriptions of
  each metric ("time without active tasks" for Idle Rate, thesis 4.2.4) as well as the exact name, from a list in
  `hitl/explanation_layer.py`. A correct wording outside that list still triggers the fallback.
- **Only two finding types are supported.** A finding outside the rule-breach and anomaly schemas, such as a
  deviation from a teammate's own history, used to be misclassified silently (thesis 4.2.5). It is now rejected
  with a clear error before it reaches the reviewer, but the pipeline still can't explain or review it.
- **The two-part prompt** has the 30-call evaluation but not the same unit and live end-to-end coverage as the
  original prompt, so treat `--prompt-style two_part` as experimental.
- `quality_metrics.py`'s hallucination check only catches one pattern (naming a different known metric as
  breached). `pattern_aggregation.py` only groups rule breaches, not anomaly findings.
- **Coverage now vs. at submission.** The 80% in the table was measured on the five core components at
  submission. Since then the modules added later have tests too, and the anomaly detector is tested on the
  synthetic data, so the whole `hitl/` package is at about 90%. The two tests that check the exact noise set on
  the real data still need the private file; `tests/test_demo.py` runs the same checks on synthetic data.
- **The demo data is invented.** It shows that the pipeline runs and what its output looks like. Its planted
  patterns say nothing about real teams, and with some random seeds DBSCAN misses the planted idle pair, the same
  parameter sensitivity as on the real data.
- K-means candidates are printed by `main.py` for information only and are not sent to review, because they
  would need a new finding schema (thesis Section 3.5).

## Future work

From thesis Section 6.2:

- a larger positive control with several Capability Managers;
- testing meeting and coordination time as a proxy for knowledge holders;
- richer input data (client feedback, task-level outcomes);
- feeding validated ledger decisions back into thresholds and prompts;
- several reviewers per finding, with inter-rater agreement (Fleiss' kappa);
- monthly ingestion for longitudinal patterns;
- combining timesheets with communication metadata.

## License

MIT, see [LICENSE](LICENSE).
