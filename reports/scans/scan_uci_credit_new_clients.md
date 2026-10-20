# Data-quality scan: scan_uci_credit_new_clients

Dataset `uci_credit` · history 11,988 rows · new batch 4,013 rows · run 2026-10-20T19:04:55+00:00 · framework 0.1.0

> Findings are **review candidates**, not verified errors: this batch has no ground truth. Recommendations rest on offline evidence from synthetic errors.

## Existing controls

dbt tests: {'pass': 45, 'warn': 36}; alerts: 181 ({'statistical': 180, 'deterministic': 1}); implicated cells 64.8 per 1,000 rows (untouched evaluation partitions of the pilot: 47.6; ratio 1.36).

## Learned and literature detectors

| detector | level | learns on | scores | flags | extra beyond controls (per 1k rows) | listed | seconds |
|---|---|---|---|---|---|---|---|
| cdc | cell | reference | yes | 153 | 112 (27.9) | 169 | 37.2 |
| dboost_gaussian_text | cell | reference | yes | 601 | 576 (143.5) | 576 | 0.9 |
| dboost_gaussian | cell | reference | yes | 2982 | 2865 (713.9) | 2865 | 0.2 |
| lucario_core | cell | batch | no | 521 | 504 (125.6) | 504 | 0.3 |
| iforest | row | reference | yes | 34 | 34 (8.5) | 100 | 0.9 |

Review budget: 25 extra cells per 1,000 rows = 100 cells for this batch; scored detectors list their top cells within that budget plus their own flags, binary detectors list their flags.

## Recommendation per detector

- **cdc: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.035 [0.029, 0.043] over 5 pilot replications (ranked; scheme random)
- **dboost_gaussian_text: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.013 [0.013, 0.015] over 5 pilot replications (ranked; scheme random)
- **dboost_gaussian: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.005 [0.001, 0.013] over 5 pilot replications (ranked; scheme random)
- **lucario_core: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.004 [0.002, 0.005] over 5 pilot replications (budget-capped flags; scheme random); extra alerts on this batch beyond the existing controls: 125.6 per 1,000 rows (cap 50)

## Findings (first 40 of 4558; full list in findings.csv)

| id | record | column | value | source | score | explanation |
|---|---|---|---|---|---|---|
| F00001 | 27004 | LIMIT_BAL | 16000 | rule:D_LIMIT_GRANULARITY |  | observed 16000.0; expected holds: LIMIT_BAL % 10000 = 0 |
| F00002 | 27466 | BILL_AMT1 | -10682 | rule:S_BILL1_TO_LIMIT |  | observed -0.097109; expected within reference envelope [-0.058017, 2.810575] |
| F00003 | 27466 | LIMIT_BAL | 110000 | rule:S_BILL1_TO_LIMIT |  | observed -0.097109; expected within reference envelope [-0.058017, 2.810575] |
| F00004 | 29564 | BILL_AMT1 | -2086 | rule:S_BILL1_TO_LIMIT |  | observed -0.1043; expected within reference envelope [-0.058017, 2.810575] |
| F00005 | 29564 | LIMIT_BAL | 20000 | rule:S_BILL1_TO_LIMIT |  | observed -0.1043; expected within reference envelope [-0.058017, 2.810575] |
| F00006 | 25601 | BILL_AMT2 | -14115 | rule:S_BILL2_TO_LIMIT |  | observed -0.14115; expected within reference envelope [-0.067767, 2.398516] |
| F00007 | 25601 | LIMIT_BAL | 100000 | rule:S_BILL2_TO_LIMIT |  | observed -0.14115; expected within reference envelope [-0.067767, 2.398516] |
| F00008 | 25863 | BILL_AMT2 | -67526 | rule:S_BILL2_TO_LIMIT |  | observed -0.964657; expected within reference envelope [-0.067767, 2.398516] |
| F00009 | 25863 | LIMIT_BAL | 70000 | rule:S_BILL2_TO_LIMIT |  | observed -0.964657; expected within reference envelope [-0.067767, 2.398516] |
| F00010 | 25093 | BILL_AMT3 | 53069 | rule:S_BILL3_TO_LIMIT |  | observed 2.65345; expected within reference envelope [-0.075785, 2.52722] |
| F00011 | 25093 | LIMIT_BAL | 20000 | rule:S_BILL3_TO_LIMIT |  | observed 2.65345; expected within reference envelope [-0.075785, 2.52722] |
| F00012 | 25732 | BILL_AMT3 | 855086 | rule:S_BILL3_TO_LIMIT |  | observed 10.688575; expected within reference envelope [-0.075785, 2.52722] |
| F00013 | 25732 | LIMIT_BAL | 80000 | rule:S_BILL3_TO_LIMIT |  | observed 10.688575; expected within reference envelope [-0.075785, 2.52722] |
| F00014 | 29492 | BILL_AMT3 | -46127 | rule:S_BILL3_TO_LIMIT |  | observed -0.144147; expected within reference envelope [-0.075785, 2.52722] |
| F00015 | 29492 | LIMIT_BAL | 320000 | rule:S_BILL3_TO_LIMIT |  | observed -0.144147; expected within reference envelope [-0.075785, 2.52722] |
| F00016 | 26161 | BILL_AMT4 | -10938 | rule:S_BILL4_TO_LIMIT |  | observed -0.10938; expected within reference envelope [-0.106796, 1.996737] |
| F00017 | 26161 | LIMIT_BAL | 100000 | rule:S_BILL4_TO_LIMIT |  | observed -0.10938; expected within reference envelope [-0.106796, 1.996737] |
| F00018 | 27427 | BILL_AMT4 | -2830 | rule:S_BILL4_TO_LIMIT |  | observed -0.1415; expected within reference envelope [-0.106796, 1.996737] |
| F00019 | 27427 | LIMIT_BAL | 20000 | rule:S_BILL4_TO_LIMIT |  | observed -0.1415; expected within reference envelope [-0.106796, 1.996737] |
| F00020 | 27655 | BILL_AMT4 | -8758 | rule:S_BILL4_TO_LIMIT |  | observed -0.8758; expected within reference envelope [-0.106796, 1.996737] |
| F00345 | 28348 | MARRIAGE | 1 | detector:cdc | 0.9990 | CDC: most likely '0' (p=1.00); observed value has p=0.000 |
| F00346 | 25020 | BILL_AMT1 | 1193 | detector:cdc | 0.9990 | CDC: predicted median 1647; conformal interval [-4.98e+04, 3.494e+04] (c=0.999) |
| F00347 | 29038 | BILL_AMT1 | 1978 | detector:cdc | 0.9990 | CDC: predicted median 2427; conformal interval [-5.06e+04, 3.712e+04] (c=0.999) |
| F00348 | 29050 | BILL_AMT1 | 0 | detector:cdc | 0.9990 | CDC: predicted median 0.6949; conformal interval [-5.065e+04, 4.764e+04] (c=0.999) |
| F00349 | 29152 | BILL_AMT3 | 1950 | detector:cdc | 0.9990 | CDC: predicted median 1586; conformal interval [-8.497e+04, 7.953e+04] (c=0.999) |
| F01090 | 25597 | PAY_AMT3 | 191260 | detector:dboost_gaussian | 31.5911 | dBoost gaussian: 'id' outside mean ± 3 sd [-4.439e+04, 5.381e+04] |
| F01091 | 26891 | PAY_AMT3 | 174169 | detector:dboost_gaussian | 31.5911 | dBoost gaussian: 'id' outside mean ± 3 sd [-4.439e+04, 5.381e+04] |
| F01092 | 28451 | PAY_AMT3 | 203000 | detector:dboost_gaussian | 31.5911 | dBoost gaussian: 'id' outside mean ± 3 sd [-4.439e+04, 5.381e+04] |
| F01093 | 29076 | PAY_AMT3 | 199209 | detector:dboost_gaussian | 31.5911 | dBoost gaussian: 'id' outside mean ± 3 sd [-4.439e+04, 5.381e+04] |
| F01094 | 26062 | PAY_AMT4 | 265852 | detector:dboost_gaussian | 29.2453 | dBoost gaussian: 'id' outside mean ± 3 sd [-4.36e+04, 5.337e+04] |
| F00514 | 25096 | BILL_AMT1 | -11 | detector:dboost_gaussian_text | 6.9088 | dBoost gaussian: 'is digit' outside mean ± 3 sd [0.5542, 1.405] |
| F00515 | 25200 | BILL_AMT1 | -5 | detector:dboost_gaussian_text | 6.9088 | dBoost gaussian: 'is digit' outside mean ± 3 sd [0.5542, 1.405] |
| F00516 | 25262 | BILL_AMT1 | -69 | detector:dboost_gaussian_text | 6.9088 | dBoost gaussian: 'is digit' outside mean ± 3 sd [0.5542, 1.405] |
| F00517 | 25408 | BILL_AMT1 | -122 | detector:dboost_gaussian_text | 6.9088 | dBoost gaussian: 'is digit' outside mean ± 3 sd [0.5542, 1.405] |
| F00518 | 25450 | BILL_AMT1 | -1037 | detector:dboost_gaussian_text | 6.9088 | dBoost gaussian: 'is digit' outside mean ± 3 sd [0.5542, 1.405] |
| F04529 | 28717 | <record> |  | detector:iforest | 0.7607 | iforest_row: record-level outlier score (reference threshold 0.5865) |
| F04472 | 25870 | <record> |  | detector:iforest | 0.7382 | iforest_row: record-level outlier score (reference threshold 0.5865) |
| F04515 | 28004 | <record> |  | detector:iforest | 0.7098 | iforest_row: record-level outlier score (reference threshold 0.5865) |
| F04503 | 27468 | <record> |  | detector:iforest | 0.6918 | iforest_row: record-level outlier score (reference threshold 0.5865) |
| F04502 | 27441 | <record> |  | detector:iforest | 0.6783 | iforest_row: record-level outlier score (reference threshold 0.5865) |

## Feedback

Annotate `feedback.csv` (verdict: confirmed_error / not_an_error / unsure) and run `dqf feedback <scan_dir>` for adjudicated precision per source.
