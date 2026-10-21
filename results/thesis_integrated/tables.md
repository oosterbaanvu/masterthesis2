### Completed runs

| dataset | scheme | runs | scenarios | failed | elapsed_s | reserved |
|---|---|---|---|---|---|---|
| uci_bank_marketing | delivery | 2 | 552 | 104 | 556.900 | 8236 |
| uci_bank_marketing | random | 3 | 984 | 0 | 847.800 | 8236 |
| uci_credit | random | 3 | 1206 | 0 | 1284.300 | 6003 |
| uci_wine_white | random | 3 | 576 | 6 | 197.800 | 959 |

Scenario counts include selection, target and sanity cases. Time is summed job time, not wall time.

### Primary shared-budget results

Budget 25/1,000. Recall quantities below are percentages; gain and interval endpoints are percentage points. Each error case receives equal weight after dependent observations are averaged.

| dataset | baseline | detector | base_recall | solo_recall | recall | utility | precision_lb | ap_all_scored | scored_positive_coverage | conditional_case_ci_lo | conditional_case_ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| uci_bank_marketing | deterministic | cdc | 8.812 | 12.654 | 16.870 | 8.058 | 9.318 | 8.051 | 100.000 | 0.022 | 17.781 |
| uci_bank_marketing | deterministic | dboost_gaussian | 8.812 | 4.708 | 8.381 | -0.431 | 4.298 | 4.558 | 95.238 | -4.535 | 3.557 |
| uci_bank_marketing | deterministic | dboost_gaussian_text | 8.812 | 9.646 | 13.299 | 4.487 | 7.225 | 9.418 | 100.000 | -3.034 | 13.625 |
| uci_bank_marketing | deterministic | iqr_outlier | 8.812 | 1.048 | 7.124 | -1.688 | 3.564 | — | — | -5.366 | 0.975 |
| uci_bank_marketing | full | cdc | 9.692 | 12.654 | 6.457 | -3.234 | 3.724 | 8.051 | 100.000 | -7.117 | 0.422 |
| uci_bank_marketing | full | dboost_gaussian | 9.692 | 4.708 | 4.731 | -4.961 | 2.685 | 4.558 | 95.238 | -7.964 | -1.972 |
| uci_bank_marketing | full | dboost_gaussian_text | 9.692 | 9.646 | 6.470 | -3.222 | 3.707 | 9.418 | 100.000 | -6.777 | 0.224 |
| uci_bank_marketing | full | iqr_outlier | 9.692 | 1.048 | 4.828 | -4.863 | 2.751 | — | — | -7.878 | -1.845 |
| uci_credit | deterministic | cdc | 2.779 | 8.891 | 11.283 | 8.504 | 6.649 | 3.764 | 100.000 | 3.974 | 13.819 |
| uci_credit | deterministic | dboost_gaussian | 2.779 | 5.184 | 6.855 | 4.076 | 4.119 | 3.411 | 91.713 | 0.936 | 8.111 |
| uci_credit | deterministic | dboost_gaussian_text | 2.779 | 4.110 | 6.871 | 4.092 | 4.032 | 3.396 | 100.000 | 0.170 | 11.265 |
| uci_credit | deterministic | iqr_outlier | 2.779 | 0.475 | 3.210 | 0.431 | 1.957 | — | — | 0.148 | 0.751 |
| uci_credit | full | cdc | 6.044 | 8.891 | 4.482 | -1.562 | 2.679 | 3.764 | 100.000 | -3.678 | 0.618 |
| uci_credit | full | dboost_gaussian | 6.044 | 5.184 | 3.041 | -3.002 | 1.806 | 3.411 | 91.713 | -4.740 | -1.585 |
| uci_credit | full | dboost_gaussian_text | 6.044 | 4.110 | 5.370 | -0.674 | 3.139 | 3.396 | 100.000 | -3.981 | 3.875 |
| uci_credit | full | iqr_outlier | 6.044 | 0.475 | 3.112 | -2.932 | 1.844 | — | — | -4.650 | -1.548 |
| uci_wine_white | deterministic | cdc | 7.033 | 45.265 | 42.184 | 35.152 | 21.828 | 34.959 | 100.000 | 12.646 | 54.840 |
| uci_wine_white | deterministic | dboost_gaussian | 7.033 | 21.528 | 20.303 | 13.270 | 9.192 | 20.040 | 100.000 | -3.396 | 33.931 |
| uci_wine_white | deterministic | dboost_gaussian_text | 7.033 | 12.172 | 16.856 | 9.823 | 9.586 | 9.583 | 100.000 | -4.646 | 27.834 |
| uci_wine_white | deterministic | iqr_outlier | 7.033 | 4.583 | 8.283 | 1.250 | 4.253 | — | — | -5.366 | 5.758 |
| uci_wine_white | full | cdc | 23.990 | 45.265 | 26.023 | 2.033 | 11.535 | 34.959 | 100.000 | -12.994 | 17.122 |
| uci_wine_white | full | dboost_gaussian | 23.990 | 21.528 | 15.745 | -8.245 | 6.545 | 20.040 | 100.000 | -17.884 | 1.364 |
| uci_wine_white | full | dboost_gaussian_text | 23.990 | 12.172 | 17.412 | -6.578 | 8.576 | 9.583 | 100.000 | -17.403 | 5.266 |
| uci_wine_white | full | iqr_outlier | 23.990 | 4.583 | 13.497 | -10.492 | 6.424 | — | — | -18.562 | -3.181 |

### Budget sensitivity

| dataset | baseline | detector | 10 | 25 | 50 |
|---|---|---|---|---|---|
| uci_bank_marketing | deterministic | cdc | 2.149 | 8.058 | 14.168 |
| uci_bank_marketing | deterministic | dboost_gaussian | -1.688 | -0.431 | 1.416 |
| uci_bank_marketing | deterministic | dboost_gaussian_text | 1.898 | 4.487 | 7.578 |
| uci_bank_marketing | deterministic | iqr_outlier | -2.467 | -1.688 | 0.535 |
| uci_bank_marketing | full | cdc | -1.176 | -3.234 | -5.793 |
| uci_bank_marketing | full | dboost_gaussian | -1.814 | -4.961 | -7.403 |
| uci_bank_marketing | full | dboost_gaussian_text | -0.563 | -3.222 | -5.878 |
| uci_bank_marketing | full | iqr_outlier | -1.686 | -4.863 | -7.951 |
| uci_credit | deterministic | cdc | 0.878 | 8.504 | 14.875 |
| uci_credit | deterministic | dboost_gaussian | 1.229 | 4.076 | 5.624 |
| uci_credit | deterministic | dboost_gaussian_text | 1.495 | 4.092 | 5.086 |
| uci_credit | deterministic | iqr_outlier | -0.486 | 0.431 | 0.800 |
| uci_credit | full | cdc | -0.638 | -1.562 | -0.765 |
| uci_credit | full | dboost_gaussian | -1.078 | -3.002 | -4.521 |
| uci_credit | full | dboost_gaussian_text | 0.344 | -0.674 | -1.293 |
| uci_credit | full | iqr_outlier | -1.039 | -2.932 | -4.753 |
| uci_wine_white | deterministic | cdc | 21.793 | 35.152 | 48.409 |
| uci_wine_white | deterministic | dboost_gaussian | 6.553 | 13.270 | 31.907 |
| uci_wine_white | deterministic | dboost_gaussian_text | 2.235 | 9.823 | 13.396 |
| uci_wine_white | deterministic | iqr_outlier | 0.379 | 1.250 | 8.258 |
| uci_wine_white | full | cdc | 3.788 | 2.033 | 10.391 |
| uci_wine_white | full | dboost_gaussian | -3.750 | -8.245 | -1.528 |
| uci_wine_white | full | dboost_gaussian_text | -2.386 | -6.578 | -1.970 |
| uci_wine_white | full | iqr_outlier | -3.687 | -10.492 | -10.354 |

### Family variation

| dataset | detector | keying | precision | scale | shift | substitution | valid_category |
|---|---|---|---|---|---|---|---|
| uci_bank_marketing | cdc | 0.000 | -2.320 | -12.091 | -3.400 | -7.123 | 2.006 |
| uci_bank_marketing | dboost_gaussian | 0.000 | -2.320 | -11.303 | -6.268 | -7.072 | -1.757 |
| uci_bank_marketing | dboost_gaussian_text | 0.000 | -2.320 | -2.836 | -6.268 | -7.082 | -1.459 |
| uci_bank_marketing | iqr_outlier | 0.841 | -2.241 | -11.052 | -6.268 | -7.042 | -1.757 |
| uci_credit | cdc | -8.215 | -0.189 | -4.577 | 0.661 | -1.631 | 4.823 |
| uci_credit | dboost_gaussian | -8.215 | -0.126 | -4.702 | -0.083 | -2.191 | -1.046 |
| uci_credit | dboost_gaussian_text | -8.215 | -0.189 | 2.987 | 0.230 | -1.818 | -1.095 |
| uci_credit | iqr_outlier | -8.048 | -0.189 | -4.497 | -0.041 | -2.191 | -1.095 |
| uci_wine_white | cdc | -6.389 | 11.042 | -30.000 | — | 19.333 | — |
| uci_wine_white | dboost_gaussian | -10.139 | -6.944 | -30.833 | — | 5.167 | — |
| uci_wine_white | dboost_gaussian_text | -10.139 | 15.417 | -30.833 | — | -0.111 | — |
| uci_wine_white | iqr_outlier | -9.861 | -6.944 | -30.741 | — | 0.111 | — |

### Placement mechanism contrasts

Matched test-diverse cases, full baseline, budget 25. EAR/ENAR minus ECAR gain in percentage points; descriptive averages, no independent-seed inference.

| dataset | detector | EAR_minus_ECAR | ENAR_minus_ECAR |
|---|---|---|---|
| uci_bank_marketing | cdc | 0.702 | 1.279 |
| uci_bank_marketing | dboost_gaussian | 0.372 | 0.884 |
| uci_bank_marketing | dboost_gaussian_text | 0.545 | 4.015 |
| uci_bank_marketing | iqr_outlier | 0.394 | 0.963 |
| uci_credit | cdc | 0.445 | -0.611 |
| uci_credit | dboost_gaussian | 1.254 | 0.224 |
| uci_credit | dboost_gaussian_text | 1.187 | -0.390 |
| uci_credit | iqr_outlier | 1.004 | 0.118 |
| uci_wine_white | cdc | -1.806 | -1.845 |
| uci_wine_white | dboost_gaussian | -2.639 | -0.536 |
| uci_wine_white | dboost_gaussian_text | -2.639 | -0.536 |
| uci_wine_white | iqr_outlier | -2.639 | -0.536 |

### Selector performance

Budget 25, full baseline. Regret/utility are recall fractions. Rates are descriptive dependent conditions.

| dataset | condition | selector | regret | utility | agreement | no_addition | insufficient | net_added_hits | decisions |
|---|---|---|---|---|---|---|---|---|---|
| uci_bank_marketing | rate_strength_shift | naive | 0.003 | 0.003 | 0.400 | 0.600 | 0.000 | 0.214 | 10 |
| uci_bank_marketing | rate_strength_shift | robust | 0.005 | 0.000 | 0.400 | 1.000 | 0.400 | 0.000 | 10 |
| uci_bank_marketing | test_diverse | naive | 0.000 | 0.010 | 0.800 | 0.600 | 0.000 | 0.581 | 10 |
| uci_bank_marketing | test_diverse | robust | 0.010 | 0.000 | 0.800 | 1.000 | 0.400 | 0.000 | 10 |
| uci_bank_marketing | test_heldout | naive | 0.003 | 0.002 | 0.600 | 0.600 | 0.000 | 0.120 | 10 |
| uci_bank_marketing | test_heldout | robust | 0.005 | 0.000 | 0.800 | 1.000 | 0.400 | 0.000 | 10 |
| uci_bank_marketing | test_simple | naive | 0.000 | 0.006 | 0.800 | 0.600 | 0.000 | 0.370 | 10 |
| uci_bank_marketing | test_simple | robust | 0.006 | 0.000 | 0.800 | 1.000 | 0.400 | 0.000 | 10 |
| uci_bank_marketing | unseen_family (pooled) | naive | 0.016 | -0.004 | 0.438 | 0.604 | 0.000 | -0.105 | 48 |
| uci_bank_marketing | unseen_family (pooled) | robust | 0.012 | 0.000 | 0.625 | 1.000 | 0.396 | 0.000 | 48 |
| uci_bank_marketing | unseen_source | naive | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 2 |
| uci_bank_marketing | unseen_source | robust | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 2 |
| uci_credit | rate_strength_shift | naive | 0.000 | 0.007 | 1.000 | 0.667 | 0.000 | 0.317 | 6 |
| uci_credit | rate_strength_shift | robust | 0.007 | 0.000 | 0.667 | 1.000 | 0.333 | 0.000 | 6 |
| uci_credit | test_diverse | naive | 0.004 | 0.002 | 0.500 | 0.667 | 0.000 | 0.097 | 6 |
| uci_credit | test_diverse | robust | 0.007 | 0.000 | 0.333 | 1.000 | 0.333 | 0.000 | 6 |
| uci_credit | test_heldout | naive | 0.006 | 0.002 | 0.667 | 0.667 | 0.000 | 0.044 | 6 |
| uci_credit | test_heldout | robust | 0.008 | 0.000 | 0.667 | 1.000 | 0.333 | 0.000 | 6 |
| uci_credit | test_simple | naive | 0.003 | 0.002 | 0.500 | 0.667 | 0.000 | 0.105 | 6 |
| uci_credit | test_simple | robust | 0.006 | 0.000 | 0.333 | 1.000 | 0.333 | 0.000 | 6 |
| uci_credit | unseen_family (pooled) | naive | 0.030 | -0.014 | 0.333 | 0.528 | 0.000 | -0.472 | 36 |
| uci_credit | unseen_family (pooled) | robust | 0.016 | 0.000 | 0.611 | 1.000 | 0.472 | 0.000 | 36 |
| uci_credit | unseen_source | naive | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 2 |
| uci_credit | unseen_source | robust | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 2 |
| uci_wine_white | rate_strength_shift | naive | 0.217 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | rate_strength_shift | robust | 0.217 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_diverse | naive | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_diverse | robust | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_heldout | naive | 0.185 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_heldout | robust | 0.185 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_simple | naive | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | test_simple | robust | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 6 |
| uci_wine_white | unseen_family (pooled) | naive | 0.106 | -0.012 | 0.458 | 0.958 | 0.000 | -0.179 | 24 |
| uci_wine_white | unseen_family (pooled) | robust | 0.094 | 0.000 | 0.500 | 1.000 | 0.042 | 0.000 | 24 |
| uci_wine_white | unseen_source | naive | 0.212 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 2 |
| uci_wine_white | unseen_source | robust | 0.212 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 2 |

### Paired selection-design contrast

| dataset | baseline | selector | diverse_minus_simple_regret |
|---|---|---|---|
| uci_bank_marketing | deterministic | naive | 0.000 |
| uci_bank_marketing | deterministic | robust | 0.000 |
| uci_bank_marketing | full | naive | 0.000 |
| uci_bank_marketing | full | robust | 0.000 |
| uci_credit | deterministic | naive | -0.022 |
| uci_credit | deterministic | robust | 0.000 |
| uci_credit | full | naive | 0.005 |
| uci_credit | full | robust | 0.000 |
| uci_wine_white | deterministic | naive | 0.000 |
| uci_wine_white | deterministic | robust | 0.000 |
| uci_wine_white | full | naive | 0.000 |
| uci_wine_white | full | robust | 0.000 |

Negative means diverse selection has lower regret; zero means no observed difference.

### Native alert workload

| dataset | detector | alerts_per_1k | flags_per_1k |
|---|---|---|---|
| uci_bank_marketing | &lt;baseline&gt; | 2552.694 | — |
| uci_bank_marketing | cdc | 708.574 | 3240.946 |
| uci_bank_marketing | dboost_gaussian | 219.159 | 1368.230 |
| uci_bank_marketing | dboost_gaussian_text | 180.914 | 678.987 |
| uci_bank_marketing | iqr_outlier | 253.964 | 909.886 |
| uci_credit | &lt;baseline&gt; | 60.613 | — |
| uci_credit | cdc | 49.349 | 59.574 |
| uci_credit | dboost_gaussian | 660.637 | 689.980 |
| uci_credit | dboost_gaussian_text | 106.845 | 115.589 |
| uci_credit | iqr_outlier | 1041.194 | 1057.793 |
| uci_wine_white | &lt;baseline&gt; | 23.403 | — |
| uci_wine_white | cdc | 16.644 | 25.659 |
| uci_wine_white | dboost_gaussian | 278.090 | 293.794 |
| uci_wine_white | dboost_gaussian_text | 134.772 | 138.109 |
| uci_wine_white | iqr_outlier | 175.749 | 188.438 |

For detectors, alerts_per_1k counts native flags absent from full controls, while flags_per_1k counts all native flags. The baseline row counts total rule alerts. These are burden, not verified false positives.

### Detector runtime

| dataset | detector | fit_seconds | score_seconds |
|---|---|---|---|
| uci_bank_marketing | cdc | 44.794 | 141.368 |
| uci_bank_marketing | dboost_gaussian | 0.152 | 4.358 |
| uci_bank_marketing | dboost_gaussian_text | 0.304 | 4.779 |
| uci_bank_marketing | iqr_outlier | 0.002 | 2.182 |
| uci_credit | cdc | 58.241 | 250.717 |
| uci_credit | dboost_gaussian | 0.033 | 6.088 |
| uci_credit | dboost_gaussian_text | 0.288 | 7.265 |
| uci_credit | iqr_outlier | 0.003 | 3.436 |
| uci_wine_white | cdc | 14.083 | 25.385 |
| uci_wine_white | dboost_gaussian | 0.008 | 1.257 |
| uci_wine_white | dboost_gaussian_text | 0.085 | 1.803 |
| uci_wine_white | iqr_outlier | 0.002 | 0.985 |

### Published shared-budget transfer

| dataset | baseline | selector | status | choice | utility | regret |
|---|---|---|---|---|---|---|
| jung_cars | deterministic | naive | REFERENCE_RELATIVE_SYNTHETIC | dboost_gaussian_text | -0.040 | 0.040 |
| jung_cars | deterministic | robust | REFERENCE_RELATIVE_SYNTHETIC | dboost_gaussian_text | -0.040 | 0.040 |
| jung_cars | full | naive | REFERENCE_RELATIVE_SYNTHETIC | NO_ADDITION | 0.000 | 0.000 |
| jung_cars | full | robust | REFERENCE_RELATIVE_SYNTHETIC | NO_ADDITION | 0.000 | 0.000 |
| jung_restaurant | deterministic | naive | REFERENCE_RELATIVE_SYNTHETIC | dboost_gaussian_text | -0.078 | 0.078 |
| jung_restaurant | deterministic | robust | REFERENCE_RELATIVE_SYNTHETIC | dboost_gaussian_text | -0.078 | 0.078 |
| jung_restaurant | full | naive | REFERENCE_RELATIVE_SYNTHETIC | NO_ADDITION | 0.000 | 0.000 |
| jung_restaurant | full | robust | REFERENCE_RELATIVE_SYNTHETIC | NO_ADDITION | 0.000 | 0.000 |
| raha_rayyan | deterministic | naive | UNADJUDICATED_NOT_SCORABLE | dboost_gaussian_text | — | — |
| raha_rayyan | deterministic | robust | UNADJUDICATED_NOT_SCORABLE | dboost_gaussian_text | — | — |
| raha_rayyan | full | naive | UNADJUDICATED_NOT_SCORABLE | NO_ADDITION | — | — |
| raha_rayyan | full | robust | UNADJUDICATED_NOT_SCORABLE | NO_ADDITION | — | — |

### Failed injection scenarios

| dataset | case_id | stage | error | count |
|---|---|---|---|---|
| uci_bank_marketing | h_cci_subst | injection | no cell changed | 6 |
| uci_bank_marketing | h_contact_swap | injection | need 42 eligible cells but only 0 are eligible | 3 |
| uci_bank_marketing | h_contact_swap | injection | need 83 eligible cells but only 0 are eligible | 3 |
| uci_bank_marketing | h_previous_subst | injection | no cell changed | 8 |
| uci_bank_marketing | month_prev | injection | need 22 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_prev | injection | need 30 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_prev | injection | need 42 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_prev | injection | need 44 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_prev | injection | need 59 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_prev | injection | need 83 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 106 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 22 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 30 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 42 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 44 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 53 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 59 eligible cells but only 0 are eligible | 6 |
| uci_bank_marketing | month_swap | injection | need 83 eligible cells but only 0 are eligible | 6 |
| uci_wine_white | h_chloride_subst | injection | no cell changed | 6 |
