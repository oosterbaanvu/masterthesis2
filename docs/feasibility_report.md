# Feasibility report and final assessment

Date: 2026-10-20 · Branch `claude/eager-davinci-u8fn78` · Status: foundation and qualification complete;
confirmatory experiments **not** run.

Evidence labels: **Verified** – supported by executed tests or primary sources inspected here;
**Provisional** – supported by evidence but not experimentally confirmed (e.g. feasibility runs with two
seeds on the dev partition); **Unknown / blocked** – insufficient evidence.

---

## 1. What was done

| Phase | Result | Main artefacts |
|---|---|---|
| 0 Environment | Python 3.12 (uv lock), 4 CPUs, 15 GB RAM, Docker available; UCI, arXiv, PyPI, raw GitHub reachable; github.com web pages, ACM DL, Kaggle downloads blocked or login-only. Isolated Python 3.9 envs for original CDC (AutoGluon 0.8.2) and Raha 1.26 installed. CI on GitHub Actions green. | `pyproject.toml`, `uv.lock`, `envs/`, `.github/workflows/ci.yml` |
| 1 Literature | 120 verified references; novelty assessment; three directions compared; refined RQ | `literature_review.md`, `research_gap.md`, `research_directions.md`, `references.bib` |
| 2 Datasets | 6 datasets downloaded and hash-verified automatically; BAF blocked; qualification of 15+ candidates | `config/datasets.yaml`, `dataset_qualification.md`, `data/manifests/` |
| 3 Detectors and injection | Compatibility matrix with real executions; CDC fidelity check against the original; 582 injection scenario variants validated | `method_compatibility.md`, `error_injection_validation.md`, `results/qualification/` |
| 4 End-to-end demo | dbt controls + injection + learned detector + budgeted evaluation + report on two financial datasets by configuration only | `reports/demo_*.md` |
| 5 Assessment | this document, research design, use case, decision log, next steps | `docs/` |

## 2. Feasibility results (dev partition, split seed 1, 1% errors, 2 seeds per cell – indicative only)

**UCI Credit, CDC (re-implementation), 132 primary scenarios** – `reports/demo_uci_credit.md`

| Quantity | Value |
|---|---|
| Recall of deterministic dbt rules on injected non-trivial errors | 0.023 |
| Recall of rules + statistical controls ("strong baseline") | 0.136 |
| Learned detector, increment over the strong baseline at 10 / 25 / 50 extra review cells per 1,000 rows | 0.003 / 0.024 / 0.030 |
| Detector ranking quality on the corrupted column (mean AUC) | 0.76 |
| Alerts on the untouched partition: baseline / detector / detector-only (cells per 1,000 rows) | 47.2 / 15.7 / 11.2 |
| Record-level increment at 10 / 50 records per 1,000 | 0.020 / 0.128 |

Largest increments: `PAY_AMT1` ×10 (baseline 0.12; +0.27 at k = 25, +0.31 at k = 50) and `LIMIT_BAL` digit
transposition (+0.08 at k = 50). Near zero: valid-code swaps in PAY_0/EDUCATION, period shifts, rounding,
sign flips (already caught by the envelope).

**UCI Bank Marketing, CDC, 80 primary scenarios** – `reports/demo_uci_bank_marketing.md`: deterministic
rules 0.00, strong baseline 0.27 (driven by the trivially detected `euribor3m` unit error and month swaps that
break the monthly-indicator lookup); increment 0.014 / 0.025 / 0.035 at k = 10 / 25 / 50; mean AUC 0.78;
**detector alert burden 31.2 cells per 1,000 untouched rows vs. 3.5 for the baseline** (rare categorical
labels, see §3). Largest increments: `job` code-remap (+0.13 at k = 50), `housing` swaps (+0.07).

**UCI Credit, Isolation Forest (record level)** – `reports/demo_uci_credit_iforest.md`: record-level
increment 0.010 at 10 and 0.07 at 50 records per 1,000; 6.3 extra untouched records per 1,000.

**Decision sensitivity** (`scripts/analyse_decision_sensitivity.py`, self-checked against the pipeline
metrics; `results/qualification/decision_sensitivity_*.csv`). Decision rule: ADOPT if the lower bootstrap
bound of the budgeted increment ≥ 0.05.

| Dataset | Baseline | k = 10 | k = 25 | k = 50 | ECAR decision = EAR / ENAR decision |
|---|---|---|---|---|---|
| Credit (17 cases) | full (rules + statistics) | 0 adopt, 1 insufficient; mean gain 0.004 | 1 / 2; 0.025 | 1 / 2; 0.031 | 87–100% / 88–100% |
| Credit | deterministic only | 1 / 2; 0.029 | 3 / 1; 0.057 | 3 / 2; 0.073 | 73–93% / 71–82% |
| Bank (10 cases) | full | 1 / 0; 0.014 | 1 / 3; 0.025 | 1 / 3; 0.035 | 80–100% / 80–90% |
| Bank | deterministic only | 2 / 0; 0.108 | 3 / 3; 0.189 | 3 / 3; 0.199 | 80–100% / 70–90% |

Against the strong baseline at tight budgets the decision is almost always DO_NOT_ADOPT; with a weaker
baseline or larger budgets several cases become ADOPT or INSUFFICIENT_EVIDENCE, and the decision based on
ECAR scenarios differs from the decision under a held-out mechanism in up to 29% of the cases. With two
seeds per cell these per-mechanism decisions are noise-dominated (Provisional); the analysis shows *where*
the decision question is non-trivial and motivates the power analysis.

**Interpretation (Provisional).** Under a strong, documented baseline and tight review budgets, the
learned detectors add little for most realistic error types – even when they rank the corrupted column well
(AUC 0.76–0.78) – because table-wide budgets are consumed by naturally unusual cells in 20+ columns
(a multiplicity effect) and by errors the baseline already catches. Earlier pilot conclusions ("CDC wins
clearly") came from a weak baseline and target-column metrics. The decision is sensitive to baseline
strength and budget – exactly the parameters an engineer controls – which makes the reliability question
meaningful.

## 3. Key technical findings (Verified)

1. **tab_err 0.2.1** (with pandas 2.3): CategorySwap maps every true code to one wrong code per call; its
   error mask counts unchanged cells (e.g. ×10 on zeros); frequency weighting ignores the seed; AddDelta's
   default is immaterial; EAR/ENAR are hard windows at random positions whose tie order follows the file. All
   reproduced in `tests/test_tab_err_behaviour.py`; worked around in the framework.
2. **Original CDC**: strict `<` in its conformal sets flags ~9.6% of untouched PAY_0 cells (7.9% of `job`) at
   c = 0.999; its random typing heuristic turns LIMIT_BAL and AGE into categoricals. With ~1,000 calibration
   rows, class-conditional thresholds equal the calibration maximum: genuine rare labels are alerted at
   ≈1/(n+1) (69% for `marital = unknown`), and flag recall on PAY_0 swaps is 0.00 for all five calibration
   seeds while ranking AUC is stable (0.81–0.89).
3. **CQR ranking** is inverted for zero-inflated, multimodal amounts (AUC 0.18–0.44); a normalised-residual
   conformal score fixes this (mean AUC 0.61 → 0.75 on dev scenarios).
4. **Benchmarks:** 97.6% of Raha Tax "errors" are formatting artefacts; ~7% of Flights errors rest on imputed
   truth; Flights' real errors are inter-source conflicts on which CDC is at chance (AUC ≈ 0.5); Raha cannot
   learn from 20 labelled tuples at low single-column error rates (0 erroneous cells labelled). On BART errors
   in Tax, CDC and our own injections both reach a ceiling (AUC ≈ 0.97–1.00), so that out-of-generator check is
   only weakly informative.
5. **Engineering:** dbt executes 81 (Credit) / 58 (Bank) generated tests on ~1M stacked rows in ~10 s; a full
   demo run with 164 scenarios takes ~6 minutes on 4 CPUs.

---

## 4. Required final evaluation

### Scientific assessment

1. **Recommended research question** – "How reliable are decisions to add a learned cell-level detector to an
   existing suite of conventional data-quality controls when these decisions are derived from controlled
   error-injection experiments, and the error mechanism, error type or data source under which the decision
   must hold differ from those used in the evaluation?" with sub-questions on adequacy, increment, decision
   reliability and a bounded validity check (`research_directions.md`). *Provisional (supervisor review).*
2. **Most directly overlapping work** – Abedjan et al. (PVLDB 2016); Jung et al. (JDIQ 2025) with CURED and
   MechDetect; Jäger & Biessmann (AISTATS 2024); AutoAnoEval (EACL Findings 2026) and SWSA; ECB Statistics
   Paper 41 and the Bank of Thailand IFC study; Just et al. (FSE 2014) for the injected-fault validity
   analogue. *Verified (sources inspected; JDIQ full text not read).*
3. **Already investigated by others** – complementarity of ML and rules (qualitatively); type-dependence of
   detector rankings (row-level AD); effect of realistic error mechanisms on cleaning benchmarks (claimed);
   synthetic pseudo-validation for model selection (row-level); partial validity of injected faults
   (software). *Verified.*
4. **Smallest defensible novelty** – decision reliability for adding a learned cell-level detector *conditional
   on* a documented conventional suite, at a fixed review budget, with the mechanism as a dose-controlled
   factor and leave-one-condition-out validation; plus the reusable artefact that produces this evidence.
   *Provisional.*
5. **Sufficient for an MSc AI thesis?** – Yes, if the confirmatory study is run as designed (factorial
   design, power analysis, hierarchical analysis) and the engineering artefact is delivered; the AI content
   lies in conformal/anomaly detection, evaluation methodology under distribution (mechanism) shift and
   decision reliability. A risk is a uniformly "do not adopt" outcome; the design mitigates this by varying
   baseline strength and budget, where decisions are shown to be non-trivial. *Provisional.*
6. **Strongest methodological objections** – (a) synthetic errors say nothing about real prevalence; (b) the
   baseline determines the result (straw-man or over-fitted); (c) mechanism and conditioning choices are
   arbitrary; (d) single learned detector; (e) seeds share rows, inflating confidence; (f) no real financial
   errors for external validation; (g) detector configuration chosen post hoc.
7. **How they are addressed** – (a) claims restricted to plausible-error coverage and decision stability;
   (b) contract-first rules with evidence status, frozen before injection results, two baseline strengths
   reported; (c) rationale per conditioning attribute, mechanism strength as a continuous factor, tab_err
   window kept as a separate shape; (d) CDC cross-checked against the original plus a record-level Isolation
   Forest; the RQ is about adding *a* detector; (e) split seed as unit of replication, hierarchical model,
   power analysis; (f) stated as limitation; bounded checks on BART errors (Tax) and real errors (Raha on
   Flights); (g) all configuration choices so far made on dev data and logged; frozen and tagged before test
   partitions are used.

### Dataset assessment

8. **Acquired** – UCI Default of Credit Card Clients, UCI Bank Marketing (both full archives), Raha Flights,
   Tax, Beers, Hospital (pinned commit). *Verified (hash-pinned, `scripts/verify_datasets.py`).*
9. **Suitable for controlled financial experiments** – UCI Credit (primary), UCI Bank Marketing (secondary,
   with real monthly delivery periods). *Verified for technical suitability; semantics partly undocumented.*
10. **Trustworthy dirty/clean ground truth** – Flights (real errors, with ~7% imputed-truth caveat); Tax only
    after removing 97.6% formatting artefacts (synthetic errors); Hospital and Beers are synthetic or
    format-only. *Verified.*
11. **Unsuitable** – BAF (blocked: login, NC licence; fraud label ≠ DQ label); TableEG, AuditBench, SGCD,
    SEC-FinTables (earlier pilots); CleanML, ZeroED Billionaire (trivial/synthetic/no truth); Li et al. Stock
    (truth = majority vote, tolerance-dependent labels); SEC amendments (not packaged).
12. **Demonstrably better alternatives** – none found for a financial real-error benchmark; AddressTable
    (2026) is a new large real-error set but string-only and non-financial. *Verified within a bounded search.*
13. **Common evaluation basis** – yes for the pipeline (same contracts → dbt → injection → detector →
    metrics); comparisons across datasets should be made on decisions and effect directions, not on raw
    recall, because their error catalogs differ. *Verified (both demos run by configuration only).*

### Detector and injection assessment

14. **Fairly comparable learned detectors** – CDC (re-implementation; cell level) and Isolation Forest (record
    level), both trained on the reference partition without labels; compared against the same baseline at
    the same budgets, but at their own granularity. Raha only on Flights (different supervision). *Verified.*
15. **Supervision / preprocessing** – CDC: clean reference data, ~1,000 calibration rows, contract-based
    typing, categorical levels fixed to the reference; Isolation Forest: ordinal encoding of codes, missing
    sentinel; Raha: 20 labelled tuples from the batch under test, string serialisation. *Verified.*
16. **Incompatibilities** – CDC × Flights (error structure; chance-level AUC); Raha × low-rate single-column
    errors (no errors in labels); original CDC: Python 3.9-only, strict set rule, random typing heuristic,
    no scores; Mondrian calibration at c = 0.999 with rare labels. LUCARIO and SAGED not tested. *Verified.*
17. **Valid error operations** – scale (non-zero cells), sign flip, digit transposition, period shift,
    rounding, plausible substitution, per-cell category swap (frequency-weighted), code remap, missing,
    invalid code, outlier; trivial ones are labelled *sanity*. *Verified (582 variants).*
18. **ECAR/EAR/ENAR implemented correctly?** – qualitatively yes in both families (placement tests: ECAR ≈
    sampling floor, EAR depends on the condition, ENAR on the own value). tab_err's EAR/ENAR are valid but
    uncontrolled in shape/position/ties; the formal JDIQ definitions remain to be quoted. *Verified (code and
    tests) / Unknown (formal definitions).*
19. **Changes compared with the original pilot** – strong documented baseline in dbt; decisions against the
    baseline instead of choosing among detectors; held-out conditions not drawn from the training mixture;
    real-change ground truth; no synthetic `source_system`; mechanism strength as a factor; frequency-weighted
    swaps; ranking-based budgeted metrics; CDC inclusive sets and contract typing; more seeds and a power
    analysis.

### Engineering assessment

20. **What to build** – the "Financial Data Quality Evaluation Framework" in this repository: contract →
    generated dbt tests → evidence; controlled error catalog; detector adapters with compatibility checks;
    budgeted incremental evaluation; auditable reports and decisions. Core exists; next: decision-reliability
    module, documented-only baseline variant, parallel execution.
21. **Why an engineer would use it** – to know which plausible errors current checks miss, to evaluate an ML
    check *conditional on* existing checks and review capacity, and to get an auditable "adopt / do not adopt
    / insufficient evidence" answer for a new source with little code (`practical_use_case.md`).
22. **Justified technologies** – Python, DuckDB, dbt Core (real SQL controls with stored failures), YAML
    contracts, Parquet, scikit-learn, uv lockfile, pytest, GitHub Actions; isolated venvs for incompatible
    originals. Not needed now: MLflow, Docker for the main env, Spark/Databricks, a web UI.
23. **Skills demonstrated** – data contracts and versioned rules; dbt on DuckDB with evidence tables;
    reproducible acquisition and lineage (hashes, manifests); dependency isolation; conformal prediction and
    anomaly detection; experimental design and statistical evaluation; testing and CI.
24. **Exclude** – web front-end, multi-table research, LLM detectors, automatic repair, production deployment,
    building new benchmarks.

### Practical execution

25. **Commands and tests run** – `scripts/download_datasets.py`, `scripts/verify_datasets.py`,
    `dqf controls generate|check`, `scripts/validate_injection.py` (both datasets), `scripts/probe_flights_typed.py`,
    `scripts/probe_tax_bart.py`, `scripts/qualify_detectors.py`, `scripts/compare_rank_scores.py`,
    `dqf run` (three demos), `dqf report`, `scripts/analyse_decision_sensitivity.py`, `pytest` (116 tests), `ruff`; Raha on
    Flights; original CDC on Credit and Bank.
26. **Passed / failed / blocked** – passed: acquisition and verification of 6 datasets, dbt execution, 582
    injection variants, test suite, CI, demos on two datasets, original-CDC and Raha environments. Failed or
    negative (and reported): CDC on Flights (chance), Raha on low-rate controlled errors, tab_err components
    listed above, first CI run (lint). Blocked: BAF download/licence; JDIQ and LUCARIO full texts (403); Kaggle.
27. **Files created** – see the repository layout in `README.md`; documentation in `docs/`; results in
    `results/qualification/` and `reports/`.
28. **Commits** – branch `claude/eager-davinci-u8fn78` on `oosterbaanvu/masterthesis2` (no pull request
    opened; can be created on request).
29. **What the student must do** – review RQ and provisional decisions with supervisors; obtain the JDIQ PDF;
    ask the industry contact the eight questions (review budget, observed errors, concentration); decide on
    BAF (Kaggle download + licence confirmation) only if still wanted (`next_steps.md` §A).
30. **Next to implement** – documented-only baseline variant; mechanism-strength grid; decision-reliability
    module with leave-one-condition-out validation; simulation-based power analysis; hierarchical analysis;
    then freeze and run the confirmatory study (`next_steps.md` §B–C).

## 5. Limitations of this foundation

- Two financial datasets, both public and old (2005; 2008–2010); semantics partly undocumented.
- Feasibility numbers use one split seed and two injection seeds; they are not estimates.
- The learned-detector configuration (rank score, confidence) was adjusted during qualification on dev
  data; it must be frozen before confirmatory runs.
- No adjudication of alerts on untouched data (some are genuine source anomalies).
- Industry context is based on one practitioner's description.
