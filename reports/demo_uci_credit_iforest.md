# Data-quality control evaluation: `uci_credit`
> Exploratory evidence from controlled, synthetic error injection on public data. It shows which *injected* errors the configured controls catch; it does not estimate real error rates and alerts on untouched cells are not verified false positives.
## Run
- Run id `demo_uci_credit_iforest-20261020T063141`, framework 0.1.0, started 2026-10-20T06:31:39+00:00, 40.9 s.
- Split: random (seed 1); reference 18000 rows; evaluated partition `dev` with 5997 rows per scenario; 164 scenarios + 1 untouched copy.
- Conventional controls: dbt Core (- installed: 1.12.6; - duckdb: 1.11.0 - Up to date!), 20 deterministic and 39 statistical rule definitions; dbt test statuses {'warn': 41, 'pass': 40} (warn = failing rows found). Recorded but not enforced: D_EDUCATION_DOCUMENTED, D_BILL_OVER_LIMIT.
- Learned detector: `iforest_row` (PASS), config {"n_estimators": 300, "max_samples": 1024, "reference_alert_rate": 0.01, "seed": 0}, fit 0.936 s, score 16.968 s.
  - limitation: Row-level only: says which record is unusual, not which field.
  - limitation: Ordinal encoding of categorical codes imposes an arbitrary order.
  - limitation: Global outlierness: plausible-but-wrong values inside the joint distribution are not detectable.

## Alert burden on the untouched partition
Baseline controls implicate 47.2 cells per 1,000 rows; the learned detector flags – cells per 1,000 rows (– not already implicated by the baseline).

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
| <row> | 65 | 0.0108 |

Record level: the learned detector flags 6.3 untouched records per 1,000 rows that the baseline does not already alert.

## Detection of injected errors
Recall is the share of injected cells implicated by a control (`det` = deterministic rules only, `B` = deterministic + statistical, `L` = learned detector at its own threshold). `ΔR@k` is the share of injected cells found by the k highest-ranked learned-detector cells per 1,000 rows that the baseline did not already implicate (fixed extra review capacity).

Row-level detector: cell-level columns refer to the baseline only; `rowR`/`rowΔR` are record-level (a record counts as found when any control alerts any of its cells).

| column | operation | mechanism | tag | recall_det | recall_B | rowR_B | rowR_L | rowΔR(flag) | rowΔR@5 | rowΔR@10 |
|---|---|---|---|---|---|---|---|---|---|---|
| AGE | missing | soft_ear | sanity | 1.000 | 1.000 | 1.000 | 0.017 | 0.000 | 0.000 | 0.000 |
| AGE | missing | soft_ecar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| AGE | missing | soft_enar | sanity | 1.000 | 1.000 | 1.000 | 0.008 | 0.000 | 0.000 | 0.000 |
| AGE | missing | tab_err_enar | sanity | 1.000 | 1.000 | 1.000 | 0.017 | 0.000 | 0.000 | 0.000 |
| AGE | plausible_substitution | soft_ear | primary | 0.000 | 0.000 | 0.017 | 0.017 | 0.008 | 0.008 | 0.017 |
| AGE | plausible_substitution | soft_ecar | primary | 0.000 | 0.000 | 0.025 | 0.000 | 0.000 | 0.000 | 0.000 |
| AGE | plausible_substitution | soft_enar | primary | 0.000 | 0.000 | 0.025 | 0.008 | 0.008 | 0.008 | 0.008 |
| AGE | plausible_substitution | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.008 | 0.008 | 0.008 | 0.025 |
| BILL_AMT1 | digit_transposition | soft_ear | primary | 0.000 | 0.042 | 0.092 | 0.050 | 0.025 | 0.025 | 0.025 |
| BILL_AMT1 | digit_transposition | soft_ecar | primary | 0.000 | 0.050 | 0.058 | 0.017 | 0.008 | 0.008 | 0.008 |
| BILL_AMT1 | digit_transposition | soft_enar | primary | 0.000 | 0.075 | 0.092 | 0.025 | 0.008 | 0.008 | 0.008 |
| BILL_AMT1 | digit_transposition | tab_err_enar | primary | 0.000 | 0.000 | 0.017 | 0.008 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | outlier | soft_ear | sanity | 0.000 | 0.650 | 0.667 | 0.017 | 0.000 | 0.000 | 0.008 |
| BILL_AMT1 | outlier | soft_ecar | sanity | 0.000 | 0.750 | 0.758 | 0.000 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | outlier | soft_enar | sanity | 0.000 | 0.333 | 0.350 | 0.025 | 0.025 | 0.017 | 0.025 |
| BILL_AMT1 | outlier | tab_err_enar | sanity | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | period_shift | soft_ear | primary | 0.000 | 0.017 | 0.025 | 0.008 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | period_shift | soft_ecar | primary | 0.000 | 0.008 | 0.017 | 0.000 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | period_shift | soft_enar | primary | 0.000 | 0.000 | 0.025 | 0.033 | 0.017 | 0.017 | 0.017 |
| BILL_AMT1 | period_shift | tab_err_enar | primary | 0.000 | 0.000 | 0.025 | 0.008 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | plausible_substitution | soft_ear | primary | 0.000 | 0.008 | 0.025 | 0.000 | 0.000 | 0.000 | 0.008 |
| BILL_AMT1 | plausible_substitution | soft_ecar | primary | 0.000 | 0.133 | 0.142 | 0.000 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | plausible_substitution | soft_enar | primary | 0.000 | 0.042 | 0.067 | 0.017 | 0.017 | 0.008 | 0.017 |
| BILL_AMT1 | plausible_substitution | tab_err_enar | primary | 0.000 | 0.158 | 0.167 | 0.000 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | scale | soft_ear | primary | 0.000 | 0.225 | 0.246 | 0.033 | 0.004 | 0.000 | 0.012 |
| BILL_AMT1 | scale | soft_ecar | primary | 0.000 | 0.342 | 0.354 | 0.033 | 0.004 | 0.004 | 0.004 |
| BILL_AMT1 | scale | soft_enar | primary | 0.000 | 0.517 | 0.525 | 0.054 | 0.017 | 0.017 | 0.025 |
| BILL_AMT1 | scale | tab_err_enar | primary | 0.000 | 0.158 | 0.175 | 0.008 | 0.008 | 0.000 | 0.017 |
| BILL_AMT1 | sign_flip | soft_ear | primary | 0.000 | 0.758 | 0.758 | 0.025 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | sign_flip | soft_ecar | primary | 0.000 | 0.825 | 0.825 | 0.033 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | sign_flip | soft_enar | primary | 0.000 | 1.000 | 1.000 | 0.050 | 0.000 | 0.000 | 0.000 |
| BILL_AMT1 | sign_flip | tab_err_enar | primary | 0.000 | 0.583 | 0.583 | 0.008 | 0.000 | 0.000 | 0.008 |
| EDUCATION | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.017 | 0.017 | 0.008 | 0.008 | 0.017 |
| EDUCATION | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.025 | 0.000 | 0.000 | 0.000 | 0.000 |
| EDUCATION | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.033 | 0.017 | 0.017 | 0.017 | 0.017 |
| EDUCATION | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.008 | 0.008 | 0.008 | 0.008 | 0.008 |
| EDUCATION | invalid_code | soft_ear | sanity | 1.000 | 1.000 | 1.000 | 0.017 | 0.000 | 0.000 | 0.000 |
| EDUCATION | invalid_code | soft_ecar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| EDUCATION | invalid_code | soft_enar | sanity | 1.000 | 1.000 | 1.000 | 0.017 | 0.000 | 0.000 | 0.000 |
| EDUCATION | invalid_code | tab_err_enar | sanity | 1.000 | 1.000 | 1.000 | 0.008 | 0.000 | 0.000 | 0.000 |
| LIMIT_BAL | digit_transposition | soft_ecar | primary | 0.533 | 0.633 | 0.633 | 0.000 | 0.000 | 0.000 | 0.008 |
| LIMIT_BAL | digit_transposition | soft_enar | primary | 0.517 | 0.675 | 0.683 | 0.008 | 0.000 | 0.000 | 0.008 |
| LIMIT_BAL | digit_transposition | tab_err_enar | primary | 0.500 | 0.500 | 0.508 | 0.000 | 0.000 | 0.000 | 0.000 |
| LIMIT_BAL | plausible_substitution | soft_ecar | primary | 0.000 | 0.142 | 0.142 | 0.000 | 0.000 | 0.000 | 0.000 |
| LIMIT_BAL | plausible_substitution | soft_enar | primary | 0.000 | 0.167 | 0.167 | 0.017 | 0.008 | 0.000 | 0.017 |
| LIMIT_BAL | plausible_substitution | tab_err_enar | primary | 0.000 | 0.058 | 0.067 | 0.000 | 0.000 | 0.000 | 0.008 |
| MARRIAGE | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.017 | 0.017 | 0.008 | 0.008 | 0.017 |
| MARRIAGE | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.025 | 0.000 | 0.000 | 0.000 | 0.000 |
| MARRIAGE | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.042 | 0.033 | 0.025 | 0.025 | 0.033 |
| MARRIAGE | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_0 | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.017 | 0.008 | 0.008 | 0.008 | 0.017 |
| PAY_0 | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.025 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_0 | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_0 | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.042 | 0.017 | 0.008 | 0.008 | 0.008 |
| PAY_0 | code_remap | soft_ear | primary | 0.000 | 0.050 | 0.067 | 0.017 | 0.008 | 0.008 | 0.025 |
| PAY_0 | code_remap | soft_ecar | primary | 0.000 | 0.042 | 0.067 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_0 | code_remap | soft_enar | primary | 0.000 | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.008 |
| PAY_0 | code_remap | tab_err_enar | primary | 0.000 | 0.000 | 0.042 | 0.017 | 0.008 | 0.008 | 0.008 |
| PAY_0 | period_shift | soft_ear | primary | 0.000 | 0.000 | 0.033 | 0.025 | 0.025 | 0.025 | 0.033 |
| PAY_0 | period_shift | soft_ecar | primary | 0.000 | 0.008 | 0.025 | 0.008 | 0.008 | 0.008 | 0.008 |
| PAY_0 | period_shift | soft_enar | primary | 0.000 | 0.000 | 0.025 | 0.008 | 0.000 | 0.000 | 0.008 |
| PAY_0 | period_shift | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.008 | 0.008 | 0.008 | 0.008 |
| PAY_AMT1 | digit_transposition | soft_ear | primary | 0.000 | 0.000 | 0.008 | 0.033 | 0.025 | 0.017 | 0.033 |
| PAY_AMT1 | digit_transposition | soft_ecar | primary | 0.000 | 0.000 | 0.008 | 0.017 | 0.008 | 0.000 | 0.008 |
| PAY_AMT1 | digit_transposition | soft_enar | primary | 0.000 | 0.008 | 0.033 | 0.042 | 0.025 | 0.025 | 0.025 |
| PAY_AMT1 | digit_transposition | tab_err_enar | primary | 0.000 | 0.000 | 0.008 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | rounding | soft_ear | primary | 0.000 | 0.000 | 0.042 | 0.025 | 0.008 | 0.008 | 0.008 |
| PAY_AMT1 | rounding | soft_ecar | primary | 0.000 | 0.008 | 0.033 | 0.008 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | rounding | soft_enar | primary | 0.000 | 0.008 | 0.025 | 0.025 | 0.017 | 0.017 | 0.042 |
| PAY_AMT1 | rounding | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | scale | soft_ear | primary | 0.000 | 0.117 | 0.117 | 0.042 | 0.017 | 0.008 | 0.017 |
| PAY_AMT1 | scale | soft_ecar | primary | 0.000 | 0.075 | 0.100 | 0.008 | 0.000 | 0.000 | 0.008 |
| PAY_AMT1 | scale | soft_enar | primary | 0.000 | 0.242 | 0.258 | 0.058 | 0.025 | 0.017 | 0.025 |
| PAY_AMT1 | scale | tab_err_enar | primary | 0.000 | 0.033 | 0.033 | 0.000 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | sign_flip | soft_ear | sanity | 1.000 | 1.000 | 1.000 | 0.008 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | sign_flip | soft_ecar | sanity | 1.000 | 1.000 | 1.000 | 0.008 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | sign_flip | soft_enar | sanity | 1.000 | 1.000 | 1.000 | 0.025 | 0.000 | 0.000 | 0.000 |
| PAY_AMT1 | sign_flip | tab_err_enar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |

### By mechanism class (mean over operations, columns and seeds)

| mechanism_class | recall_B | row_recall_B | row_incremental_recall_at_10_per_1k |
|---|---|---|---|
| EAR | 0.268 | 0.284 | 0.013 |
| ECAR | 0.303 | 0.315 | 0.002 |
| ENAR | 0.291 | 0.304 | 0.010 |

## Adoption indication under the pre-registered rule
Rule: ADOPT if the lower 95% bootstrap bound of `row_incremental_recall_at_10_per_1k` ≥ 0.05 and the extra review load ≤ 10.0 per 1,000 rows (for a budgeted metric the load equals the budget); DO_NOT_ADOPT if the upper bound < 0.05 or the load is exceeded; otherwise INSUFFICIENT_EVIDENCE. Computed per error case (column, operation, parameters) over seeds and mechanisms (n is small in a demonstration run; this is an indication, not a confirmatory result).

| column | operation | params | n | row_incremental_recall_at_10_per_1k mean | CI low | CI high | decision |
|---|---|---|---|---|---|---|---|
| AGE | plausible_substitution | {} | 8 | 0.012 | 0.002 | 0.025 | DO_NOT_ADOPT |
| BILL_AMT1 | digit_transposition | {} | 8 | 0.010 | 0.004 | 0.019 | DO_NOT_ADOPT |
| BILL_AMT1 | period_shift | {"source_column": "BILL_AMT2"} | 8 | 0.004 | 0.000 | 0.012 | DO_NOT_ADOPT |
| BILL_AMT1 | plausible_substitution | {} | 8 | 0.006 | 0.002 | 0.012 | DO_NOT_ADOPT |
| BILL_AMT1 | scale | {"factor": 0.001} | 8 | 0.023 | 0.015 | 0.033 | DO_NOT_ADOPT |
| BILL_AMT1 | scale | {"factor": 10} | 8 | 0.006 | 0.000 | 0.012 | DO_NOT_ADOPT |
| BILL_AMT1 | sign_flip | {} | 8 | 0.002 | 0.000 | 0.006 | DO_NOT_ADOPT |
| EDUCATION | category_swap | {"weighing": "frequency"} | 8 | 0.010 | 0.002 | 0.019 | DO_NOT_ADOPT |
| LIMIT_BAL | digit_transposition | {} | 6 | 0.006 | 0.000 | 0.011 | DO_NOT_ADOPT |
| LIMIT_BAL | plausible_substitution | {} | 6 | 0.008 | 0.000 | 0.019 | DO_NOT_ADOPT |
| MARRIAGE | category_swap | {"weighing": "frequency"} | 8 | 0.012 | 0.002 | 0.025 | DO_NOT_ADOPT |
| PAY_0 | category_swap | {"weighing": "frequency"} | 8 | 0.006 | 0.002 | 0.012 | DO_NOT_ADOPT |
| PAY_0 | code_remap | {} | 8 | 0.010 | 0.002 | 0.019 | DO_NOT_ADOPT |
| PAY_0 | period_shift | {"source_column": "PAY_2"} | 8 | 0.015 | 0.006 | 0.023 | DO_NOT_ADOPT |
| PAY_AMT1 | digit_transposition | {} | 8 | 0.017 | 0.006 | 0.027 | DO_NOT_ADOPT |
| PAY_AMT1 | rounding | {"unit": 1000} | 8 | 0.012 | 0.002 | 0.025 | DO_NOT_ADOPT |
| PAY_AMT1 | scale | {"factor": 10} | 8 | 0.012 | 0.006 | 0.021 | DO_NOT_ADOPT |

Pooled over primary cases: row_incremental_recall_at_10_per_1k = 0.010 [0.008, 0.013] (scenario-level bootstrap; scenarios share rows, so this interval is optimistic).

## Caveats
- Injected errors are synthetic; detection of these errors is not evidence about real error prevalence.
- Multi-column rules implicate all referenced cells; their cell-level precision is bounded by design.
- The reference partition is assumed clean; source anomalies in it are not adjudicated.
- Decisions here are not confirmatory: settings were not frozen and the number of seeds is small.
