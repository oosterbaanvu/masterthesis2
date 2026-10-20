# Data-quality control evaluation: `uci_bank_marketing`
> Exploratory evidence from controlled, synthetic error injection on public data. It shows which *injected* errors the configured controls catch; it does not estimate real error rates and alerts on untouched cells are not verified false positives.
## Run
- Run id `demo_uci_bank_marketing-20261020T072157`, framework 0.1.0, started 2026-10-20T07:21:55+00:00, 238.1 s.
- Split: random (seed 1); reference 24716 rows; evaluated partition `dev` with 8236 rows per scenario; 96 scenarios + 1 untouched copy.
- Conventional controls: dbt Core (- installed: 1.12.6; - duckdb: 1.11.0 - Up to date!), 18 deterministic and 21 statistical rule definitions; dbt test statuses {'pass': 48, 'warn': 10} (warn = failing rows found). Recorded but not enforced: D_PDAYS999_NO_PREVIOUS.
- Learned detector: `cdc_hgb` (CONDITIONAL), config {"rank_score": "normalized_residual", "set_rule": "inclusive", "base_quantile": null, "confidence": 0.999, "calibration_rows": 1000, "max_iter": 100, "learning_rate": 0.1, "min_samples_leaf": 20, "seed": 0, "target_columns": null}, fit 31.769 s, score 161.498 s.
  - limitation: Assumes the reference partition is (mostly) error-free; errors in it widen intervals.
  - limitation: Class-conditional (Mondrian) calibration: for labels with n < 1/(1-c) calibration examples the threshold is the calibration maximum, so genuine values of rare labels are alerted at about 1/(n+1) and swaps into them are rarely flagged.
  - limitation: Re-implementation with a different base learner than the published experiments.

## Alert burden on the untouched partition
Baseline controls implicate 3.5 cells per 1,000 rows; the learned detector flags 31.2 cells per 1,000 rows (29.9 not already implicated by the baseline).

Top rules by alerts on untouched data:

| rule_id | tier | rule_status | alerts | alerts_per_1k_rows |
|---|---|---|---|---|
| S_ENV_duration | statistical | provisional | 9 | 1.09 |
| S_ENV_previous | statistical | provisional | 6 | 0.73 |
| S_ENV_campaign | statistical | provisional | 4 | 0.49 |
| S_ENV_age | statistical | provisional | 4 | 0.49 |
| S_ENV_euribor3m | statistical | provisional | 3 | 0.36 |
| S_RARE_education | statistical | provisional | 3 | 0.36 |

Detector flags on untouched data (top columns):

| column | flags | flag_rate |
|---|---|---|
| marital | 55 | 0.0067 |
| job | 48 | 0.0058 |
| day_of_week | 34 | 0.0041 |
| education | 26 | 0.0032 |
| contact | 24 | 0.0029 |
| poutcome | 18 | 0.0022 |
| loan | 12 | 0.0015 |
| age | 11 | 0.0013 |

## Detection of injected errors
Recall is the share of injected cells implicated by a control (`det` = deterministic rules only, `B` = deterministic + statistical, `L` = learned detector at its own threshold). `ΔR@k` is the share of injected cells found by the k highest-ranked learned-detector cells per 1,000 rows that the baseline did not already implicate (fixed extra review capacity).

| column | operation | mechanism | tag | recall_det | recall_B | recall_L | ΔR(flag) | ΔR@5 | ΔR@10 | AUC_L |
|---|---|---|---|---|---|---|---|---|---|---|
| age | missing | soft_ear | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| age | missing | soft_ecar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| age | missing | soft_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| age | missing | tab_err_enar | sanity | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | – |
| age | plausible_substitution | soft_ear | primary | 0.000 | 0.000 | 0.024 | 0.024 | 0.000 | 0.030 | 0.716 |
| age | plausible_substitution | soft_ecar | primary | 0.000 | 0.000 | 0.024 | 0.024 | 0.000 | 0.024 | 0.788 |
| age | plausible_substitution | soft_enar | primary | 0.000 | 0.000 | 0.024 | 0.024 | 0.000 | 0.037 | 0.732 |
| age | plausible_substitution | tab_err_enar | primary | 0.000 | 0.000 | 0.018 | 0.018 | 0.000 | 0.049 | 0.777 |
| campaign | plausible_substitution | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.545 |
| campaign | plausible_substitution | soft_ecar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.557 |
| campaign | plausible_substitution | soft_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.561 |
| campaign | plausible_substitution | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.006 | 0.608 |
| duration | digit_transposition | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.590 |
| duration | digit_transposition | soft_ecar | primary | 0.000 | 0.006 | 0.006 | 0.000 | 0.000 | 0.000 | 0.620 |
| duration | digit_transposition | soft_enar | primary | 0.000 | 0.012 | 0.012 | 0.000 | 0.000 | 0.000 | 0.765 |
| duration | digit_transposition | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.545 |
| duration | scale | soft_ear | primary | 0.000 | 0.695 | 0.000 | 0.000 | 0.000 | 0.000 | 0.754 |
| duration | scale | soft_ecar | primary | 0.000 | 0.707 | 0.000 | 0.000 | 0.000 | 0.000 | 0.744 |
| duration | scale | soft_enar | primary | 0.000 | 0.220 | 0.000 | 0.000 | 0.000 | 0.000 | 0.770 |
| duration | scale | tab_err_enar | primary | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.747 |
| education | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.796 |
| education | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.006 | 0.006 | 0.000 | 0.000 | 0.823 |
| education | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.006 | 0.006 | 0.000 | 0.000 | 0.843 |
| education | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.829 |
| euribor3m | scale | soft_ear | primary | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| euribor3m | scale | soft_ecar | primary | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.999 |
| euribor3m | scale | soft_enar | primary | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| euribor3m | scale | tab_err_enar | primary | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.997 |
| housing | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.079 | 0.079 | 0.079 | 0.079 | 0.580 |
| housing | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.091 | 0.091 | 0.091 | 0.091 | 0.613 |
| housing | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.061 | 0.061 | 0.061 | 0.061 | 0.666 |
| housing | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.055 | 0.055 | 0.055 | 0.055 | 0.510 |
| job | category_swap | soft_ear | primary | 0.000 | 0.000 | 0.116 | 0.116 | 0.024 | 0.024 | 0.803 |
| job | category_swap | soft_ecar | primary | 0.000 | 0.000 | 0.171 | 0.171 | 0.012 | 0.012 | 0.807 |
| job | category_swap | soft_enar | primary | 0.000 | 0.000 | 0.256 | 0.256 | 0.037 | 0.037 | 0.870 |
| job | category_swap | tab_err_enar | primary | 0.000 | 0.000 | 0.152 | 0.152 | 0.006 | 0.006 | 0.859 |
| job | code_remap | soft_ear | primary | 0.000 | 0.000 | 0.067 | 0.067 | 0.006 | 0.006 | 0.873 |
| job | code_remap | soft_ecar | primary | 0.000 | 0.000 | 0.177 | 0.177 | 0.024 | 0.024 | 0.880 |
| job | code_remap | soft_enar | primary | 0.000 | 0.000 | 0.055 | 0.055 | 0.000 | 0.000 | 0.780 |
| job | code_remap | tab_err_enar | primary | 0.000 | 0.000 | 0.104 | 0.104 | 0.012 | 0.012 | 0.861 |
| job | invalid_code | soft_ear | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| job | invalid_code | soft_ecar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| job | invalid_code | soft_enar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| job | invalid_code | tab_err_enar | sanity | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| month | category_swap | soft_ear | primary | 0.000 | 1.000 | 0.994 | 0.000 | 0.000 | 0.000 | 1.000 |
| month | category_swap | soft_ecar | primary | 0.000 | 1.000 | 0.976 | 0.000 | 0.000 | 0.000 | 1.000 |
| month | category_swap | soft_enar | primary | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| month | category_swap | tab_err_enar | primary | 0.000 | 1.000 | 0.994 | 0.000 | 0.000 | 0.000 | 1.000 |

### By mechanism class (mean over operations, columns and seeds)

| mechanism_class | recall_B | row_recall_B | incremental_recall_at_10_per_1k | row_incremental_recall_at_10_per_1k | auc_L_target |
|---|---|---|---|---|---|
| EAR | 0.391 | 0.392 | 0.012 | 0.018 | 0.787 |
| ECAR | 0.393 | 0.396 | 0.013 | 0.021 | 0.803 |
| ENAR | 0.385 | 0.385 | 0.011 | 0.018 | 0.805 |

## Adoption indication under the pre-registered rule
Rule: ADOPT if the lower 95% bootstrap bound of `incremental_recall_at_10_per_1k` ≥ 0.05 and the extra review load ≤ 10.0 per 1,000 rows (for a budgeted metric the load equals the budget); DO_NOT_ADOPT if the upper bound < 0.05 or the load is exceeded; otherwise INSUFFICIENT_EVIDENCE. Computed per error case (column, operation, parameters) over seeds and mechanisms (n is small in a demonstration run; this is an indication, not a confirmatory result).

| column | operation | params | n | incremental_recall_at_10_per_1k mean | CI low | CI high | decision |
|---|---|---|---|---|---|---|---|
| age | plausible_substitution | {} | 8 | 0.035 | 0.026 | 0.044 | DO_NOT_ADOPT |
| campaign | plausible_substitution | {} | 8 | 0.002 | 0.000 | 0.005 | DO_NOT_ADOPT |
| duration | digit_transposition | {} | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| duration | scale | {"factor": 0.0166667} | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| education | category_swap | {"weighing": "frequency"} | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| euribor3m | scale | {"factor": 0.01} | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |
| housing | category_swap | {"weighing": "frequency"} | 8 | 0.072 | 0.059 | 0.085 | ADOPT |
| job | category_swap | {"weighing": "frequency"} | 8 | 0.020 | 0.009 | 0.030 | DO_NOT_ADOPT |
| job | code_remap | {} | 8 | 0.011 | 0.003 | 0.020 | DO_NOT_ADOPT |
| month | category_swap | {"weighing": "frequency"} | 8 | 0.000 | 0.000 | 0.000 | DO_NOT_ADOPT |

Pooled over primary cases: incremental_recall_at_10_per_1k = 0.014 [0.009, 0.020] (scenario-level bootstrap; scenarios share rows, so this interval is optimistic).

## Caveats
- Injected errors are synthetic; detection of these errors is not evidence about real error prevalence.
- Multi-column rules implicate all referenced cells; their cell-level precision is bounded by design.
- The reference partition is assumed clean; source anomalies in it are not adjudicated.
- Decisions here are not confirmatory: settings were not frozen and the number of seeds is small.
