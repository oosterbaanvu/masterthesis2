# Data-quality control evaluation: `uci_credit`
> Exploratory evidence from controlled, synthetic error injection on public data. It shows which *injected* errors the configured controls catch; it does not estimate real error rates and alerts on untouched cells are not verified false positives.
## Run
- Run id `demo_uci_credit-20261020T054950`, framework 0.1.0, started 2026-10-20T05:49:47+00:00, 1144.2 s.
- Split: random (seed 1); reference 18000 rows; evaluated partition `dev` with 5997 rows per scenario; 164 scenarios + 1 untouched copy.
- Conventional controls: dbt Core (- installed: 1.12.6; - duckdb: 1.11.0 - Up to date!), 20 deterministic and 39 statistical rule definitions; dbt test statuses {'warn': 41, 'pass': 40} (warn = failing rows found). Recorded but not enforced: D_EDUCATION_DOCUMENTED, D_BILL_OVER_LIMIT.
- Learned detector: `cdc_hgb` (CONDITIONAL), config {"set_rule": "inclusive", "base_quantile": null, "confidence": 0.999, "calibration_rows": 1000, "max_iter": 100, "learning_rate": 0.1, "min_samples_leaf": 20, "seed": 0, "target_columns": null}, fit 847.648 s, score 235.699 s.
  - limitation: Assumes the reference partition is (mostly) error-free; errors in it widen intervals.
  - limitation: Mondrian calibration: labels with few calibration examples get wide sets and are rarely flagged.
  - limitation: Re-implementation with a different base learner than the published experiments.

## Alert burden on the untouched partition
Baseline controls implicate 47.2 cells per 1,000 rows; the learned detector flags 15.7 cells per 1,000 rows (11.2 not already implicated by the baseline).

Top rules by alerts on untouched data:

| rule_id | tier | rule_status | alerts | alerts_per_1k_rows |
|---|---|---|---|---|
| S_BILL6_TO_LIMIT | statistical | provisional | 11 | 1.83 |
| S_PAY_TO_BILL2 | statistical | provisional | 11 | 1.83 |
| S_RARE_PAY_6 | statistical | provisional | 11 | 1.83 |
| S_BILL_MOM2 | statistical | provisional | 11 | 1.83 |
| S_BILL1_TO_LIMIT | statistical | provisional | 10 | 1.67 |
| S_PAY_TO_BILL4 | statistical | provisional | 10 | 1.67 |
| S_BILL2_TO_LIMIT | statistical | provisional | 9 | 1.50 |
| S_BILL5_TO_LIMIT | statistical | provisional | 9 | 1.50 |
| S_ENV_BILL_AMT1 | statistical | provisional | 8 | 1.33 |
| S_ENV_BILL_AMT6 | statistical | provisional | 8 | 1.33 |

Detector flags on untouched data (top columns):

| column | flags | flag_rate |
|---|---|---|
| AGE | 22 | 0.0037 |
| PAY_AMT6 | 22 | 0.0037 |
| MARRIAGE | 14 | 0.0023 |
| BILL_AMT5 | 6 | 0.0010 |
| PAY_AMT5 | 6 | 0.0010 |
| SEX | 4 | 0.0007 |
| BILL_AMT6 | 4 | 0.0007 |
| PAY_AMT3 | 3 | 0.0005 |

## Detection of injected errors
Recall is the share of injected cells implicated by a control (`det` = deterministic rules only, `B` = deterministic + statistical, `L` = learned detector at its own threshold). `ΔR@k` is the share of injected cells found by the k highest-ranked learned-detector cells per 1,000 rows that the baseline did not already implicate (fixed extra review capacity).

| column | operation | mechanism | tag | recall_det | recall_B | recall_L | ΔR(flag) | ΔR@5 | ΔR@10 | AUC_L |
|---|---|---|---|---|---|---|---|---|---|---|
| AGE | missing | soft_ear | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| AGE | missing | soft_ecar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| AGE | missing | soft_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| AGE | missing | tab_err_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| AGE | plausible_substitution | soft_ear | primary | 0.000 | 0.000 | 0.033 | 0.033 | 0.033 | 0.033 | 0.609 |
| AGE | plausible_substitution | soft_ecar | primary | 0.000 | 0.000 | 0.008 | 0.008 | 0.008 | 0.008 | 0.530 |
| AGE | plausible_substitution | soft_enar | primary | 0.000 | 0.000 | 0.017 | 0.017 | 0.017 | 0.017 | 0.599 |
| AGE | plausible_substitution | tab_err_enar | primary | 0.000 | 0.000 | 0.008 | 0.008 | 0.008 | 0.008 | 0.333 |
| BILL_AMT1 | digit_transposition | soft_ear | primary | 0.000 | 0.042 | 0.042 | 0.000 | 0.000 | 0.000 | 0.447 |
| BILL_AMT1 | digit_transposition | soft_ecar | primary | 0.000 | 0.050 | 0.025 | 0.000 | 0.000 | 0.000 | 0.482 |
| BILL_AMT1 | digit_transposition | soft_enar | primary | 0.000 | 0.075 | 0.042 | 0.000 | 0.000 | 0.000 | 0.328 |
| BILL_AMT1 | digit_transposition | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.689 |
| BILL_AMT1 | outlier | soft_ear | sanity | 0.000 | 0.650 | 0.000 | 0.000 | 0.000 | 0.000 | 0.767 |
| BILL_AMT1 | outlier | soft_ecar | sanity | 0.000 | 0.750 | 0.000 | 0.000 | 0.000 | 0.000 | 0.814 |
| BILL_AMT1 | outlier | soft_enar | sanity | 0.000 | 0.333 | 0.000 | 0.000 | 0.000 | 0.000 | 0.573 |
| BILL_AMT1 | outlier | tab_err_enar | sanity | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| BILL_AMT1 | period_shift | soft_ear | primary | 0.000 | 0.017 | 0.000 | 0.000 | 0.000 | 0.000 | 0.483 |
| BILL_AMT1 | period_shift | soft_ecar | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.484 |
| BILL_AMT1 | period_shift | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.273 |
| BILL_AMT1 | period_shift | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.685 |
| BILL_AMT1 | plausible_substitution | soft_ear | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.565 |
| BILL_AMT1 | plausible_substitution | soft_ecar | primary | 0.000 | 0.133 | 0.000 | 0.000 | 0.000 | 0.000 | 0.620 |
| BILL_AMT1 | plausible_substitution | soft_enar | primary | 0.000 | 0.042 | 0.000 | 0.000 | 0.000 | 0.000 | 0.697 |
| BILL_AMT1 | plausible_substitution | tab_err_enar | primary | 0.000 | 0.158 | 0.000 | 0.000 | 0.000 | 0.000 | 0.540 |
| BILL_AMT1 | scale | soft_ear | primary | 0.000 | 0.225 | 0.204 | 0.008 | 0.008 | 0.008 | 0.821 |
| BILL_AMT1 | scale | soft_ecar | primary | 0.000 | 0.342 | 0.221 | 0.000 | 0.000 | 0.000 | 0.893 |
| BILL_AMT1 | scale | soft_enar | primary | 0.000 | 0.517 | 0.421 | 0.004 | 0.004 | 0.004 | 0.981 |
| BILL_AMT1 | scale | tab_err_enar | primary | 0.000 | 0.158 | 0.000 | 0.000 | 0.000 | 0.000 | 0.691 |
| BILL_AMT1 | sign_flip | soft_ear | primary | 0.000 | 0.758 | 0.183 | 0.000 | 0.000 | 0.000 | 0.989 |
| BILL_AMT1 | sign_flip | soft_ecar | primary | 0.000 | 0.825 | 0.108 | 0.000 | 0.000 | 0.000 | 0.994 |
| BILL_AMT1 | sign_flip | soft_enar | primary | 0.000 | 1.000 | 0.317 | 0.000 | 0.000 | 0.000 | 0.999 |
| BILL_AMT1 | sign_flip | tab_err_enar | primary | 0.000 | 0.583 | 0.000 | 0.000 | 0.000 | 0.000 | 0.995 |
| EDUCATION | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.658 |
| EDUCATION | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.612 |
| EDUCATION | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.700 |
| EDUCATION | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.642 |
| EDUCATION | invalid_code | soft_ear | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| EDUCATION | invalid_code | soft_ecar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| EDUCATION | invalid_code | soft_enar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| EDUCATION | invalid_code | tab_err_enar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| LIMIT_BAL | digit_transposition | soft_ecar | primary | 0.533 | 0.633 | 0.117 | 0.025 | 0.025 | 0.033 | 0.509 |
| LIMIT_BAL | digit_transposition | soft_enar | primary | 0.517 | 0.675 | 0.158 | 0.008 | 0.008 | 0.058 | 0.495 |
| LIMIT_BAL | digit_transposition | tab_err_enar | primary | 0.500 | 0.500 | 0.025 | 0.025 | 0.025 | 0.058 | 0.677 |
| LIMIT_BAL | plausible_substitution | soft_ecar | primary | 0.000 | 0.142 | 0.000 | 0.000 | 0.000 | 0.008 | 0.524 |
| LIMIT_BAL | plausible_substitution | soft_enar | primary | 0.000 | 0.167 | 0.000 | 0.000 | 0.000 | 0.008 | 0.525 |
| LIMIT_BAL | plausible_substitution | tab_err_enar | primary | 0.000 | 0.058 | 0.008 | 0.008 | 0.008 | 0.008 | 0.438 |
| MARRIAGE | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.033 | 0.033 | 0.000 | 0.000 | 0.808 |
| MARRIAGE | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.033 | 0.033 | 0.000 | 0.000 | 0.803 |
| MARRIAGE | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.025 | 0.025 | 0.000 | 0.000 | 0.731 |
| MARRIAGE | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.033 | 0.033 | 0.000 | 0.000 | 0.688 |
| PAY_0 | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.805 |
| PAY_0 | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.806 |
| PAY_0 | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.821 |
| PAY_0 | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.801 |
| PAY_0 | code_remap | soft_ear | primary | 0.000 | 0.050 | 0.000 | 0.000 | 0.000 | 0.000 | 0.829 |
| PAY_0 | code_remap | soft_ecar | primary | 0.000 | 0.042 | 0.000 | 0.000 | 0.000 | 0.000 | 0.807 |
| PAY_0 | code_remap | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.781 |
| PAY_0 | code_remap | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.806 |
| PAY_0 | period_shift | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.608 |
| PAY_0 | period_shift | soft_ecar | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.634 |
| PAY_0 | period_shift | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.634 |
| PAY_0 | period_shift | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.665 |
| PAY_AMT1 | digit_transposition | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.310 |
| PAY_AMT1 | digit_transposition | soft_ecar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.356 |
| PAY_AMT1 | digit_transposition | soft_enar | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.210 |
| PAY_AMT1 | digit_transposition | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.501 |
| PAY_AMT1 | rounding | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.316 |
| PAY_AMT1 | rounding | soft_ecar | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.474 |
| PAY_AMT1 | rounding | soft_enar | primary | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 | 0.232 |
| PAY_AMT1 | rounding | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.640 |
| PAY_AMT1 | scale | soft_ear | primary | 0.000 | 0.117 | 0.050 | 0.000 | 0.000 | 0.000 | 0.345 |
| PAY_AMT1 | scale | soft_ecar | primary | 0.000 | 0.075 | 0.017 | 0.000 | 0.000 | 0.000 | 0.209 |
| PAY_AMT1 | scale | soft_enar | primary | 0.000 | 0.242 | 0.083 | 0.000 | 0.000 | 0.000 | 0.440 |
| PAY_AMT1 | scale | tab_err_enar | primary | 0.000 | 0.033 | 0.000 | 0.000 | 0.000 | 0.000 | 0.046 |
| PAY_AMT1 | sign_flip | soft_ear | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 |
| PAY_AMT1 | sign_flip | soft_ecar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.998 |
| PAY_AMT1 | sign_flip | soft_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 |
| PAY_AMT1 | sign_flip | tab_err_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.998 |

### By mechanism class (mean over operations, columns and seeds)

| mechanism_class | recall_B | incremental_recall_at_10_per_1k | auc_L_target |
|---|---|---|---|
| EAR | 0.268 | 0.003 | 0.677 |
| ECAR | 0.303 | 0.002 | 0.672 |
| ENAR | 0.291 | 0.004 | 0.663 |

## Adoption indication under the pre-registered rule
Rule: ADOPT if the lower 95% bootstrap bound of `incremental_recall_at_10_per_1k` ≥ 0.05 and the extra alert burden ≤ 10.0 per 1,000 rows; DO_NOT_ADOPT if the upper bound < 0.05 or the burden is exceeded; otherwise INSUFFICIENT_EVIDENCE. Computed per error case over seeds and mechanisms (n is small in a demonstration run; this is an indication, not a confirmatory result).

| column | operation | n | ΔR@10 mean | CI low | CI high | decision |
|---|---|---|---|---|---|---|
| AGE | plausible_substitution | 8 | 0.017 | 0.008 | 0.025 | DO_NOT_ADOPT |
| BILL_AMT1 | digit_transposition | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| BILL_AMT1 | period_shift | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| BILL_AMT1 | plausible_substitution | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| BILL_AMT1 | scale | 16 | 0.003 | 0.000 | 0.006 | DO_NOT_ADOPT |
| BILL_AMT1 | sign_flip | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| EDUCATION | category_swap | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| LIMIT_BAL | digit_transposition | 6 | 0.050 | 0.022 | 0.081 | DO_NOT_ADOPT |
| LIMIT_BAL | plausible_substitution | 6 | 0.008 | 0.003 | 0.014 | DO_NOT_ADOPT |
| MARRIAGE | category_swap | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_0 | category_swap | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_0 | code_remap | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_0 | period_shift | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_AMT1 | digit_transposition | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_AMT1 | rounding | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| PAY_AMT1 | scale | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |

Pooled over primary cases: ΔR@10 = 0.004 [0.002, 0.007] (scenario-level bootstrap; scenarios share rows, so this interval is optimistic).

## Caveats
- Injected errors are synthetic; detection of these errors is not evidence about real error prevalence.
- Multi-column rules implicate all referenced cells; their cell-level precision is bounded by design.
- The reference partition is assumed clean; source anomalies in it are not adjudicated.
- Decisions here are not confirmatory: settings were not frozen and the number of seeds is small.
