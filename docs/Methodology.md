# Revised Project Scope & Methodology (Draft)

## Part 1 — Revised Research Framing

### Why revise
The original framing bundles three sub-questions with very different data readiness:

| Component | Data status |
|---|---|
| Workflow-level behavioral patterns | Supported — 643 task-level rows, 23-teammate KPI ratios |
| Outcome validation (CSAT, defects, escalations, KPI achievement) | Blocked — columns confirmed empty, pending Capability Manager entry |
| Organizational interactions (who works with whom) | Unsupported — no communication/network data exists in the available files |

Answering all three as one unified claim makes the project dependent on external inputs outside your control, with a hard September 30 deadline. Splitting them lets the empirical core stand on data you already have, while the rest is named honestly rather than silently absent.

### Revised title
**Inferring Tribal Operational Intelligence from Delivery Workflows: A Human-in-the-Loop AI Approach**

*(dropping "and organizational interactions" from the title — retained in the literature review and limitations as the theoretically motivated but empirically unsupported half of the original question)*

### Revised research questions

**RQ1 (revised):** Can behavioral patterns indicative of tribal operational intelligence — undocumented, person-dependent operational knowledge — be surfaced from delivery workflow data using unsupervised and anomaly-detection methods, in the absence of formal outcome or interaction data?

**RQ2 (unchanged):** Can a Human-in-the-Loop AI system be designed and prototyped to surface, present, and log this inferred operational intelligence for managerial review?

**RQ1b (contingent, scoped as future validation):** Do the patterns surfaced under RQ1 correlate with client-facing delivery outcomes? — explicitly framed as the next phase, contingent on Capability Manager data entry, not a claim this project resolves.

This keeps the project's empirical center (RQ1) answerable entirely with data in hand, keeps RQ2 — already substantially built — as a strong second pillar, and reframes the outcome-validation question as a defined next step rather than a gap in the argument.

### What's explicitly out of scope, and why that's defensible
- **Organizational interaction/network data** — never captured at the organization; no email, meeting-attendee, or collaboration-graph data exists. Framed in the literature review as the natural extension (tying to Blau's social exchange theory and Diefenbach & Sillince's formal/informal hierarchy distinction, already in your Section 2.1), and to Zuin et al.'s (2025) relationship-network simulation as a model for how a future phase could capture it.
- **Outcome-validated supervised prediction** — the Random Forest work becomes a **methodological feasibility demonstration** (real n=21 vs. schema-matched synthetic n=1000) rather than a claim about the organization's actual client outcomes. This is intellectually honest and still substantive — it's evidence about *when* this class of method would work, once outcome data exists.

---

## Part 2 — Methodology (Section 3 draft)

### 3.1 Data Source and Collection

The empirical basis for this project is the organization's Phase 1 operational KPI dataset (May 2026), collected as part of the organization's standard capability-practice reporting process. Two levels of the same underlying data were used:

- **Task-level data** ("Raw Data," *n* = 643 rows): individual logged tasks across seven capability practices (Webtech, Execution, Graphics, Data, Content, Search Advertising, Calling Support), each recorded with a task category (10 standardized categories spanning production, QC, rework, meetings, idle time, and administrative categories), a free-text task description, hours logged, and a data-quality flag.
- **Teammate-level summary data** ("Phase 1 – KPI Summary," *n* = 23 teammates): seven derived input-side ratios (ETA Achievement, Rework Rate, Requirement Understanding Ratio, Meeting Overhead Ratio, Idle Rate, Effective Utilisation, Average Time Per Task) computed from the same underlying hours.

Four output-side columns in the summary table — CSAT, Number of Defects, Number of Escalations, and KPI Achievement — remain unpopulated pending manual entry by capability managers, and are treated throughout as unavailable rather than imputed. Populated outcome data exists for one practice (Execution: MQL, RoAS, weekly sales) but at a different level of granularity than the teammate-level behavioral data and was not merged into the core analysis for that reason.

Data covers a single reporting period (May 2026); no longitudinal or time-series dimension is available.

### 3.2 Data Preparation

Standard cleaning was applied prior to analysis: placeholder strings (`"-"`) were converted to missing values and affected columns coerced to numeric type; teammates with zero logged billable hours were identified and, where the zero reflected a genuine data-entry gap rather than inactivity (confirmed by cross-referencing task-level records), noted as a data-quality limitation rather than corrected in place. One pair of KPI ratios (ETA Achievement, Effective Utilisation) was excluded from correlation analysis due to a formula-overlap artifact — Effective Utilisation's numerator arithmetically contains ETA Achievement's, so any correlation between them reflects construction, not behavior.

### 3.3 Exploratory Data Analysis

EDA proceeded at both data levels. At the task level: distribution of task categories overall and by capability practice; total hours by practice × category (identifying where time actually concentrates within each function); and flagged-rate analysis by category (data-quality flags, not defect indicators, per inspection of the underlying field definition). At the teammate level: the correlation structure among the seven input ratios (Spearman, given small sample size and skewed distributions), reported with an explicit multiple-comparisons caveat given 21 simultaneous tests at *n* = 21.

### 3.4 Unsupervised Pattern Discovery

Two complementary clustering approaches were used to surface candidate tribal-knowledge signals without assuming in advance who or what would be anomalous:

1. **Behavioral clustering (teammate level).** Each teammate's hours were converted into a category-share profile (percentage of total hours in each of the 10 task categories), standardized, and clustered via *k*-means. Cluster count was selected using elbow (inertia) and silhouette diagnostics, with explicit attention to cluster-size degeneracy — a known risk at *n* ≈ 22, where a favorable silhouette score can reflect isolation of one or two outliers rather than balanced behavioral groups.
2. **Text clustering (task level).** Task descriptions were vectorized with TF-IDF (unigrams and bigrams, English stop-words removed) and clustered via *k*-means, to test whether natural task themes emerge independent of the existing category labels. Silhouette scores in this setting were modest (≈0.07–0.12), consistent with the short, formulaic nature of the source text; results are interpreted qualitatively via top-weighted terms per cluster rather than treated as a well-separated solution.

### 3.5 Cross-Validation Against Prior Anomaly Detection

Teammates previously flagged by a rule-based task-concentration heuristic (three prior analyses, four flagged teammates) were cross-referenced against the behavioral clustering output. Agreement was partial — one of four previously flagged teammates fell into a distinct cluster — and is reported as such. This partial convergence between two independently derived methods is treated as suggestive corroboration, not confirmation.

### 3.6 Supervised Modeling: Feasibility and Sample-Size Sensitivity

Because outcome labels (CSAT, defects, escalations, KPI achievement) are unavailable, Random Forest could not be applied to test the project's core predictive claim. Instead, a controlled feasibility demonstration was conducted: a synthetic dataset was constructed matching the organization's actual column distributions and schema (avoiding the domain mismatch risk of substituting an unrelated public dataset), and the same Random Forest pipeline was run at *n* = 1,000 (recovering signal, R² ≈ 0.49) and at *n* = 21 (matching the real available sample, performance indistinguishable from chance across random draws). This is presented as a methodological contribution — evidence of *when* the proposed approach becomes viable — rather than a result about the organization's actual outcomes.

### 3.7 Human-in-the-Loop System Design and Prototype

Building on Amershi et al.'s HITL design guidelines and the detect–explain–review–feedback loop structure (contrasted against fully autonomous approaches, e.g., Zuin et al., 2025), a two-part prototype was developed: (1) an interactive demo seeded with real Phase 1 findings, illustrating how surfaced patterns would be presented to a manager for confirmation, rejection, or annotation; and (2) a backend pipeline combining rule-based benchmark-breach detection, task-concentration anomaly detection, and LLM-assisted risk-language classification, feeding a persistent tribal-knowledge log. This system operationalizes the SECI model's Externalization step — converting tacit operational patterns into an explicit, reviewable, cumulative organizational record — with the human reviewer retaining final judgment at every step, consistent with the project's HITL-as-copilot framing rather than autonomous decision-making.

### 3.8 Limitations and Scope

- Single-month snapshot; no data on how patterns change over time.
- Small sample size at the teammate level (*n* = 21–23) limits statistical generalizability of both correlation and clustering results; findings are presented as exploratory and worth human review, not as confirmed population-level patterns.
- No organizational interaction/communication data was available, leaving the "organizational interactions" component of the original research question empirically untested in this project; this is named as a direction for future work rather than resolved.
- Outcome-side validation (RQ1b) is contingent on data not yet entered by capability managers and is scoped as a defined next phase rather than a result of the current work.
