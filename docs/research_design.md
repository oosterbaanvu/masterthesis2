# Research design (proposed confirmatory protocol)

Status: **proposal for supervisor review – not yet pre-registered, not yet run.** Everything that is
measured in this repository so far is qualification or feasibility evidence (dev partition of split seed 1).

## 1. Research question

> How reliable are decisions to add a learned cell-level detector to an existing suite of conventional
> data-quality controls when these decisions are derived from controlled error-injection experiments, and
> the error mechanism, error type or data source under which the decision must hold differ from those used
> in the evaluation?

Sub-questions (rationale in `research_directions.md`):

- **SQ1 Adequacy.** Which non-trivial injected errors survive the conventional suite, by error type and
  mechanism shape/strength?
- **SQ2 Increment.** What share of injected errors does a learned detector add at a fixed review budget,
  and at what alert burden on untouched data?
- **SQ3 Decision reliability.** How often does an ECAR-based adoption decision differ from the decision under
  held-out conditions, and does a mechanism-diverse design reduce regret?
- **SQ4 Bounded validity check.** Agreement with independently generated or real errors where the detector
  is compatible.

## 2. Hypotheses (directional, to be fixed before the confirmatory run)

- H1: Baseline survival differs by error family: domain-valid, in-range errors (plausible substitution,
  frequency-weighted code swaps, period shift, rounding) survive far more often than scale/sign errors.
- H2: The increment ΔR@k of CDC is concentrated in error types whose true value is predictable from other
  columns (e.g. code swaps in correlated status series, scaling of series with strong month-to-month
  dependence) and is near zero for weakly predictable columns (payments, limits).
- H3: ΔR@k depends on mechanism *strength*: ENAR towards high values increases baseline recall for scale
  errors and therefore reduces ΔR@k; EAR concentrated in a segment changes the reference/score relation.
- H4 (reliability): ECAR-only decisions disagree with held-out-condition decisions more often than
  dominance alone predicts; a mechanism-diverse design reduces regret but not to zero.

Null results for H2–H4 are informative and will be reported.

## 3. Factors

| Factor | Levels (proposal) |
|---|---|
| Dataset | UCI Credit; UCI Bank Marketing |
| Split | 5 split seeds (group-aware random); Bank additionally temporal split by `_period` |
| Error case (column × operation) | catalog `config/experiments/scenario_catalog.yaml`, *primary* role only (sanity cases reported separately) |
| Mechanism shape | ECAR; soft (exponential-rank) EAR / ENAR; tab_err window EAR / ENAR |
| Mechanism strength (soft) | 0 (= ECAR), 1, 2, 4, 8 |
| Mechanism direction / segment | ENAR high vs. low; EAR conditioning attribute (two per dataset, stated rationale) |
| Error rate | 0.5%, 1%, 2% of rows in the target column |
| Injection seeds | 5 per cell of the design (after power analysis) |
| Review budget k | 5, 10, 25 cells per 1,000 rows (to be confirmed with practitioners) |
| Baseline strength | documented-only rules; full suite (rules + statistical controls) |
| Learned detector | CDC (re-implementation, fixed configuration); Isolation Forest (record level) |

Detector configuration (confidence, base learner, iterations) and statistical-control thresholds are
frozen **before** the confirmatory run, using dev partitions only.

## 4. Metrics

Per scenario: recall of deterministic rules and of the full suite (cell and record level); ΔR@k
(primary); own-threshold increment; extra alerts on untouched data per 1,000 rows (burden); AUC/AP of the
detector on the target column (diagnostic); runtime.

Per *decision unit* (dataset × error case × budget): decision ∈ {ADOPT, DO_NOT_ADOPT,
INSUFFICIENT_EVIDENCE} from the bootstrap CI of ΔR@k against a minimum gain δ and a burden cap.

Decision reliability (SQ3):

- **Agreement** between the decision from evaluation design E (ECAR-only vs. mechanism-diverse with the
  same number of scenarios) and the "target" decision computed on held-out condition T.
- **Dominance-aware reference:** the agreement expected if every decision were the majority decision.
- **Regret:** the difference in expected net value (ΔR@k − λ·burden) between the decision taken and the
  best decision under T.
- **Validation schemes:** leave-one-mechanism-shape-out, leave-one-strength-level-out,
  leave-one-error-family-out, leave-one-dataset-out, temporal (Bank). T is never part of E's scenarios
  (avoids the circularity of the pilot design).

## 5. Analysis

- Unit of replication: split seed (independent reference/evaluation partitions); injection seeds are nested.
- Mixed-effects / Bayesian hierarchical model of logit(ΔR@k) (and of baseline survival) with fixed effects
  for operation, mechanism shape × strength, rate, budget and random effects for split seed and column
  (template: Emmott et al.; Corani et al. 2017).
- Pairwise decision comparisons with Bayesian signed-rank tests and a ROPE (Benavoli et al. 2017) or
  bootstrap over split seeds; multiple comparisons controlled (Benjamini–Yekutieli, as in CleanML).
- **Power analysis by simulation** before the main run, using the feasibility results to set the number of
  split and injection seeds needed to detect a ΔR@k difference of δ between mechanism conditions.

## 6. Safeguards

- Rules, statistical-control specifications, scenario catalog, detector configurations and decision
  thresholds are frozen and tagged in git before the confirmatory run; test partitions and new split seeds
  are used only then.
- All scenarios are reported, including sanity cases, failures and null results.
- Untouched-data alerts are burden, not false positives; a sample of them can be adjudicated manually and
  reported separately.
- Compatibility verdicts are reported; incompatible detector/dataset pairs get no score.
- Runtime and environment versions are recorded in every run manifest.

## 7. Bounded validity checks (SQ4)

- **Out-of-generator:** CDC on BART-generated errors in Raha Tax vs. our injected errors in the same columns
  (`scripts/probe_tax_bart.py`); reported per column as agreement of ranking quality, not as transfer to
  real data.
- **Real errors:** Raha on Flights (real inter-source conflicts) only; CDC is incompatible with that error
  structure (chance-level AUC in the qualification probe).

## 8. Compute budget (estimate from the feasibility runs)

A demo run with 156 scenarios × 6,000 rows takes ~6 minutes on 4 CPUs (dbt ~1–2 min on ~1M stacked rows;
CDC fit ~45 s; scoring dominates). The proposed design (≈2 datasets × 5 split seeds × ~20 cases × ~10
mechanism settings × 3 rates × 5 seeds ≈ 30,000 scenarios) needs roughly 20 CPU-hours; feasible locally or
on a small cloud VM. The power analysis may reduce it. Run the scorer with `OMP_NUM_THREADS` set so that
parallel runs do not oversubscribe cores.
