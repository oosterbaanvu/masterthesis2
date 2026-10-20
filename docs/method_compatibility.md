# Method compatibility

Status: 2026-10-20. Every PASS/CONDITIONAL/INCOMPATIBLE verdict below is backed by a real execution
recorded in `results/qualification/` (reproduce with `python scripts/qualify_detectors.py`,
`scripts/probe_flights_typed.py`, `scripts/probe_tax_bart.py`, `scripts/compare_rank_scores.py`).
Qualification uses the **dev** partition of split seed 1.

## 1. Candidates and requirements

| Method | Implementation used | Supervision | Output | Input requirements | Missing values | Compute (4 CPUs) |
|---|---|---|---|---|---|---|
| Conventional controls | dbt Core 1.12.6 + dbt-duckdb 1.11 on DuckDB, tests generated from contracts | none (rules from documentation; statistical bounds fitted on reference) | failing rows with rule id, implicated columns, observed/expected | contract per source | `not_null` per required column | ~10 s for ~1M stacked rows, 58–81 tests |
| **CDC – re-implementation** (`cdc_hgb`) | scikit-learn HistGradientBoosting per column + split conformal (CQR for numeric, Mondrian sets for categorical); conformal p-values for ranking | none, but needs a clean(ish) reference partition | cell score + flag | ≥2 columns; categorical ≤200 levels; ~1,000 calibration rows | native in features; missing target cells not scored | fit 30–50 s (23 columns, 18k rows); score ~1.5 s per 6k-row batch |
| **CDC – original** (`cdc_original`) | se-jaeger/conformal-data-cleaning @fd8a2126, conformal-inference @e25cb593, AutoGluon 0.8.2 (RF + XT; FASTAI omitted), Python 3.9 | as above | cell flag only | numeric or categorical (text raises); random cardinality heuristic for typing | imputes and counts pre-existing NaNs as "cleaned" | ~70–100 s for 2 targets |
| **Isolation Forest** (`iforest_row`) | scikit-learn IsolationForest (300 trees, 1,024 samples), threshold at the 99th reference-score percentile | none (reference data) | **row** score + flag | ordinal-encoded codes | sentinel | ~1 s fit, <1 s score |
| **Raha** (`raha`) | BigDaMa/raha 1.26, Python 3.9, private TMPDIR | **20 labelled tuples** from the batch under test (simulated from ground truth) | cell flag only | strings (CSV) | as text | 40–60 s for 1,000 × 23 |
| LUCARIO | – | – | – | – | – | not tested |
| SAGED | – | historical labelled datasets | – | – | – | not tested |

## 2. Compatibility matrix

| Detector × dataset | Verdict | Evidence (real execution) | Reasons / conditions |
|---|---|---|---|
| cdc_hgb × UCI Credit | **CONDITIONAL** | fit+score 18,000/5,997 rows; flag rate on untouched dev 0.07% | 4/7 EDUCATION, 2/4 MARRIAGE and 6–8 PAY_x labels have < 999 expected calibration examples at c = 0.999 → for them the conformal guarantee degrades to ≈1/(n+1) |
| cdc_hgb × Bank Marketing | **CONDITIONAL** | fit+score 24,716/8,236 rows; flag rate 0.16% (31 cells per 1,000 rows) | same rare-label effect: `marital = unknown` (n≈2) alerted in 69% of untouched cases |
| cdc_original × UCI Credit | **CONDITIONAL** | executed (`cdc_fidelity.json`) | strict `<` set rule: 9.6% of untouched PAY_0 cells flagged; heuristic typing turns LIMIT_BAL and AGE into categoricals; flags only |
| cdc_original × Bank Marketing | **CONDITIONAL** | targets job, age; untouched flag rate job 7.9%, age 0.01% | same strict-set effect |
| iforest_row × UCI Credit | **PASS** | flag rate 1.08% (≈ the 1% reference threshold) | record level only |
| iforest_row × Bank Marketing | **PASS** | flag rate 1.12% | record level only |
| raha × UCI Credit | **CONDITIONAL** (not informative) | 1,000 rows, 5% errors in one column: 0 and 2 erroneous cells among the labelled tuples; recall 0.00 and 0.08 | few-label supervision cannot learn single-column errors at realistic rates; different supervision → reported separately |
| raha × Bank Marketing | **CONDITIONAL** (not informative) | 0 erroneous cells labelled; recall 0.00 | as above |
| raha × Flights | **PASS** | published pair, 20 labelled tuples: P 0.883, R 0.681, F1 0.769 | real inter-source errors; transductive use of redundancy |
| cdc_hgb × Flights | **INCOMPATIBLE** | typed probe, split by flight: AUC 0.47–0.55 on real value errors (0.18 for sched_dep_time, which has only 3 value errors) | errors are conflicts between rows for the same flight; per-row conditional models cannot see them without leaking the truth |
| cdc_hgb × Tax (BART errors) | **CONDITIONAL** | typed probe: AUC ≈1.00 on BART errors in state / marital_status / has_child; our injected swaps 0.97–1.00; our substitutions in exemption columns 0.69–0.71 | high-cardinality strings excluded; synthetic FDs make these errors near-trivial (ceiling, so agreement is weak evidence); BART's exemption errors are unparseable strings caught by format checks |
| iforest_row × Flights; raha × Tax | NOT TESTED | – | not meaningful / not needed |
| LUCARIO, SAGED | NOT TESTED | – | LUCARIO paper not readable (403), code not verified; SAGED needs labelled historical datasets, no licence file |

No incompatible pair is given a score anywhere in the reports.

## 3. CDC fidelity: re-implementation vs. original (same stacked batch)

UCI Credit dev, 5% ECAR errors, targets BILL_AMT1 (×10) and PAY_0 (frequency-weighted swap), c = 0.999
(`results/qualification/cdc_fidelity.json`):

| Implementation | BILL_AMT1 ×10 recall (flag) | untouched BILL_AMT1 flags | PAY_0 swap recall (flag) | untouched PAY_0 flags |
|---|---|---|---|---|
| cdc_hgb, inclusive sets | 0.45 | 0.0% | 0.00 | 0.0% |
| cdc_hgb, `strict_original` sets | 0.45 | 0.0% | 0.55 | 20.2% |
| original, contract typing | 0.55 | 0.05% | 0.87 | 9.6% |
| original, original heuristic typing | 0.54 | 0.03% | 0.88 | 9.2% |

Numeric behaviour is comparable. The categorical difference is explained by the strict `<` in the original's
prediction sets (reproduced by `strict_original`): with tied tree probabilities a label whose score equals
q̂ is excluded, so the original "detects" swaps by flagging a large share of all cells. The re-implementation
uses the standard inclusive set (s ≤ q̂).

## 4. CDC design findings

1. **Mondrian calibration at c = 0.999** needs ≥ 999 calibration examples per label; with ~1,000 calibration
   rows almost every label falls short, so thresholds equal the calibration maximum: flag recall on PAY_0
   swaps is 0.00 (all five calibration seeds) while ranking AUC is 0.81–0.89
   (`cdc_seed_variance.json`). Use ranking (budgets) rather than flags, or larger calibration sets / lower c.
2. **Ranking score.** The CQR nonconformity measures distance to the interval edge. For zero-inflated or
   multimodal amounts (payments, exemptions) the interval spans several modes and wrong values in its middle
   look more conforming than correct values on its edge: AUC 0.18 for PAY_AMT1 ×10. A normalised-residual
   conformal score (|y − median| / interval width) raises the mean target-column AUC over 17 numeric dev
   cases from 0.61 to 0.75 (`cdc_rank_score_comparison.csv`); CQR remains better for shrinking errors (÷1000,
   ÷60) and sign flips. Default for ranking: normalised residual; flags: CQR as in the original.
3. **Ties.** Conformal p-values have resolution 1/(n_cal+1); on 23 columns ≈23 cells per 1,000 rows reach the
   minimal p-value on clean data alone – more than a 10-per-1,000 review budget. A tie-breaker (< p-value
   resolution) orders them by normalised nonconformity. This multiplicity is a substantive reason why
   table-wide budgets dilute cell-level detectors.
4. **Seeds.** Calibration splits are drawn per column from a hash of (seed, column), so results do not depend
   on the order of target columns.

## 5. Fairness of comparisons

- CDC and Isolation Forest receive the same reference partition and no labels; Raha receives labels and is
  never compared like-for-like with them.
- Cell-level metrics are computed only for cell-level detectors; record-level metrics for all (cell output
  aggregated to rows by max score / any flag; nothing is mapped from rows to cells).
- Multi-column rules implicate all referenced cells, which bounds the baseline's cell-level precision but is
  what an engineer sees; record-level metrics are reported alongside.
- Detector configuration choices made during qualification (inclusive sets, rank score, contract typing)
  are logged in `decision_log.md` (D-08) and will be frozen before confirmatory runs.
