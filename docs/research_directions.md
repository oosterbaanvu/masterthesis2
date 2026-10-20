# Research directions: comparison and recommendation

Status: recommendation for supervisor review (2026-10-19). Evidence: `literature_review.md`,
`research_gap.md`, qualification results in `results/qualification/` and the feasibility runs in
`reports/`.

## 1. Candidate directions

### A – Incremental value of a learned detector beyond conventional controls
*When does a learned cell-level detector add meaningful detection coverage over a strong dbt + statistical
control suite, at a fixed review budget and an acceptable alert burden?*

### B – Reliability of injection-based evaluation and adoption decisions
*Do adoption decisions derived from controlled error-injection experiments (ECAR-only vs. mechanism-diverse)
remain correct under held-out mechanisms, error types, datasets and – where possible – real errors?*

### C – Mutation-analysis adequacy of conventional data test suites (own proposal)
*Treat injected errors as mutants of a data batch and the dbt/statistical suite as the test suite: what is
its mutation score under realistic error models, which errors survive (including "equivalent mutants" that
are indistinguishable from valid data), and does the mechanism change the score?* Borrowed methodology:
mutation score, surviving mutants, coupling with real faults (Just et al. 2014), suite-size confound
(Papadakis et al. 2018).

### Considered and rejected
- **Multi-table inconsistency detection** – out of the agreed scope; no labelled data.
- **LLM-based error detection** (ZeroED, TableEG-style) – costly, non-reproducible API dependence, and
  sending (even public) data to external services conflicts with the safety constraints of the brief.
- **Building a real-error financial benchmark** from SEC 10-K/A amendments or revision histories – realistic
  but high semantic-labelling effort and alignment risk (`dataset_qualification.md` §SEC); suitable as future
  work.
- **Benchmarking many ML detectors** – the pilot showed that a detector zoo answers "which detector wins",
  which is neither novel nor the operational question.

## 2. Comparison

Scores: ++ strong, + adequate, o weak, – problematic.

| Criterion | A | B | C |
|---|---|---|---|
| Scientific originality | + (conditional, budgeted increment not found; complementarity itself is known) | + (decision reliability under mechanism shift not found; close to AutoAnoEval/SWSA for row-level AD) | ++ (no peer-reviewed mutation analysis of data test suites found) |
| Strength of related literature to build on | ++ | + | ++ (SE mutation literature) |
| Measurability | ++ (ΔR@k, alert burden) | + on synthetic held-out conditions; o for real transfer | ++ (mutation score, survival profiles) |
| Dataset availability / ground truth | ++ (injection gives exact labels) | o (real-error benchmarks incompatible with CDC, none financial) | ++ |
| Detector compatibility | + (CDC, Isolation Forest qualified) | + | not needed for the core; needed for the increment |
| Methodological risks | baseline strength dominates the result; increment may be ~0 | circularity of held-out design; null result plausible | "relabelling" critique; equivalent mutants must be defined |
| Practical value for financial data engineering | ++ (tells an engineer whether to add ML) | + (tells how much to trust the evaluation) | ++ (directly evaluates the dbt suite they own) |
| Implementation complexity | moderate (done in this repo) | moderate (protocol on top of A) | low on top of A |
| MSc scope | fits | fits as secondary | fits |

## 3. Recommendation

**Combine them, with B as the scientific question, A as the core measurement and C as the framing of the
engineering artefact.** This preserves the original idea (reliability of the adoption decision), addresses
the pilot's weaknesses, and does not change direction for its own sake.

### Recommended research question (provisional)

> **How reliable are decisions to add a learned cell-level detector to an existing suite of conventional
> data-quality controls when these decisions are derived from controlled error-injection experiments, and
> the error mechanism, error type or data source under which the decision must hold differ from those used
> in the evaluation?**

Sub-questions:

1. **Adequacy (C/A).** Which non-trivial injected errors survive a strong conventional control suite (dbt
   deterministic rules + statistical controls fitted on reference data), and how does the survival rate
   depend on the error type and on the *shape and strength* of the error mechanism?
2. **Increment (A).** At a fixed review budget, what share of the injected errors does a learned detector
   recover beyond the suite (cell-level CDC; record-level Isolation Forest), and at what additional alert
   burden on untouched data?
3. **Decision reliability (B).** How often does an adopt / do-not-adopt / insufficient-evidence decision made
   from ECAR-only scenarios differ from the decision under held-out conditions (unseen mechanism shape or
   strength, unseen error type, second dataset)? Does a mechanism-diverse evaluation reduce decision regret
   under leave-one-condition-out validation, compared with what detector dominance alone predicts?
4. **Bounded validity check.** Where an independent error source is compatible with the detector, do the
   conclusions agree with it (Raha on real Flights errors; CDC on BART-generated errors in Tax, if the
   qualification probe passes)? This is reported as a coupling check, not as a transfer estimate.

### Why this is the strongest defensible option

- It keeps the most interesting element of the original idea (decision reliability) but removes the
  circular and dominance-driven design of the pilot (decisions are taken *against the baseline* and
  validated on held-out conditions).
- The core quantity (ΔR@k conditional on the baseline) is measurable with exact ground truth and is what
  an engineer needs.
- Mechanism strength as a continuous factor turns the mechanism from a label into a dose-response variable;
  that is where decisions can actually flip.
- A null result ("ECAR-only evaluation is as reliable as a mechanism-diverse one", or "the learned detector
  adds nothing at this budget") is still informative and publishable as an evaluation-methodology finding.

### Effect on scope, data and detectors

- Main question changes only in emphasis (decision against the baseline instead of choice among detectors).
- Datasets: UCI Credit (primary) and UCI Bank Marketing (secondary, replaces the blocked BAF; has real
  monthly delivery periods). No new data source is required.
- Detectors: CDC (re-implementation, cross-checked against the original) and a row-level Isolation Forest.
  Raha only for the bounded real-error check.
- Engineering effort: the protocol runs on the framework in this repository; remaining work is the
  confirmatory protocol, the power analysis and the hierarchical analysis (see `next_steps.md`).
