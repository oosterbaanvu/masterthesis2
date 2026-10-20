# Data-quality scan: scan_bank_marketing_period13

Dataset `uci_bank_marketing` · history 24,368 rows · new batch 609 rows · run 2026-10-20T19:03:58+00:00 · framework 0.1.0

> Findings are **review candidates**, not verified errors: this batch has no ground truth. Recommendations rest on offline evidence from synthetic errors.

## Existing controls

dbt tests: {'pass': 48, 'warn': 10}; alerts: 3687 ({'statistical': 3687}); implicated cells 6054.2 per 1,000 rows (untouched evaluation partitions of the pilot: 6212.0; ratio 0.97).

## Learned and literature detectors

| detector | level | learns on | scores | flags | extra beyond controls (per 1k rows) | listed | seconds |
|---|---|---|---|---|---|---|---|
| cdc | cell | reference | yes | 4324 | 649 (1065.7) | 651 | 30.1 |
| dboost_gaussian_text | cell | reference | yes | 390 | 377 (619.0) | 377 | 1.3 |
| dboost_gaussian | cell | reference | yes | 3212 | 751 (1233.2) | 751 | 0.6 |
| lucario_core | cell | batch | no | 81 | 66 (108.4) | 66 | 0.1 |
| iforest | row | reference | yes | 149 | 149 (244.7) | 149 | 1.3 |

Review budget: 25 extra cells per 1,000 rows = 15 cells for this batch; scored detectors list their top cells within that budget plus their own flags, binary detectors list their flags.

## Recommendation per detector

- **cdc: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.009 [0.002, 0.019] over 4 pilot replications (ranked; scheme delivery)
- **dboost_gaussian_text: INSUFFICIENT_EVIDENCE** – offline held-out utility at 25 reviews/1k rows: 0.047 [0.016, 0.068] over 4 pilot replications (ranked; scheme delivery)
- **dboost_gaussian: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.012 [0.000, 0.037] over 4 pilot replications (ranked; scheme delivery)
- **lucario_core: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.005 [0.000, 0.015] over 4 pilot replications (budget-capped flags; scheme delivery); extra alerts on this batch beyond the existing controls: 108.4 per 1,000 rows (cap 50)

## Findings (first 40 of 8117; full list in findings.csv)

| id | record | column | value | source | score | explanation |
|---|---|---|---|---|---|---|
| F00001 | 37126 | age | 18 | rule:S_ENV_age |  | observed 18.0; expected within reference envelope [19.0, 81.8165] |
| F00002 | 37141 | age | 17 | rule:S_ENV_age |  | observed 17.0; expected within reference envelope [19.0, 81.8165] |
| F00003 | 37214 | age | 82 | rule:S_ENV_age |  | observed 82.0; expected within reference envelope [19.0, 81.8165] |
| F00004 | 37342 | age | 85 | rule:S_ENV_age |  | observed 85.0; expected within reference envelope [19.0, 81.8165] |
| F00005 | 37473 | age | 88 | rule:S_ENV_age |  | observed 88.0; expected within reference envelope [19.0, 81.8165] |
| F00006 | 37540 | age | 17 | rule:S_ENV_age |  | observed 17.0; expected within reference envelope [19.0, 81.8165] |
| F00007 | 37559 | age | 17 | rule:S_ENV_age |  | observed 17.0; expected within reference envelope [19.0, 81.8165] |
| F00008 | 37627 | age | 18 | rule:S_ENV_age |  | observed 18.0; expected within reference envelope [19.0, 81.8165] |
| F00009 | 37744 | age | 87 | rule:S_ENV_age |  | observed 87.0; expected within reference envelope [19.0, 81.8165] |
| F00010 | 37776 | age | 88 | rule:S_ENV_age |  | observed 88.0; expected within reference envelope [19.0, 81.8165] |
| F00011 | 37120 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00012 | 37121 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00013 | 37122 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00014 | 37123 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00015 | 37124 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00016 | 37125 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00017 | 37126 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00018 | 37127 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00019 | 37128 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F00020 | 37129 | cons.conf.idx | -31.4 | rule:S_ENV_cons.conf.idx |  | observed -31.4; expected within reference envelope [-50.0, -36.1] |
| F06124 | 37154 | campaign | 1 | detector:cdc | 0.9990 | CDC: predicted median 2.031; conformal interval [-9.137, 8.721] (c=0.999) |
| F06125 | 37368 | campaign | 1 | detector:cdc | 0.9990 | CDC: predicted median 1.862; conformal interval [-9.137, 8.286] (c=0.999) |
| F06126 | 37388 | marital | unknown | detector:cdc | 0.9990 | CDC: most likely 'married' (p=0.99); observed value has p=0.000 |
| F06127 | 37844 | day_of_week | fri | detector:cdc | 0.9990 | CDC: most likely 'thu' (p=1.00); observed value has p=0.000 |
| F06128 | 37735 | day_of_week | fri | detector:cdc | 0.9990 | CDC: most likely 'thu' (p=1.00); observed value has p=0.000 |
| F07152 | 37339 | pdays | 10 | detector:dboost_gaussian | 47.0561 | dBoost gaussian: 'id' outside mean ± 3 sd [819.6, 1171] |
| F07153 | 37705 | pdays | 9 | detector:dboost_gaussian | 47.0561 | dBoost gaussian: 'id' outside mean ± 3 sd [819.6, 1171] |
| F07154 | 37872 | pdays | 9 | detector:dboost_gaussian | 47.0561 | dBoost gaussian: 'id' outside mean ± 3 sd [819.6, 1171] |
| F07155 | 37280 | pdays | 5 | detector:dboost_gaussian | 32.5343 | dBoost gaussian: 'id' outside mean ± 3 sd [819.6, 1171] |
| F07156 | 37377 | pdays | 5 | detector:dboost_gaussian | 32.5343 | dBoost gaussian: 'id' outside mean ± 3 sd [819.6, 1171] |
| F06775 | 37122 | pdays | 4 | detector:dboost_gaussian_text | 17.1312 | dBoost gaussian: 'length' outside mean ± 3 sd [2.644, 3.342] |
| F06776 | 37129 | pdays | 4 | detector:dboost_gaussian_text | 17.1312 | dBoost gaussian: 'length' outside mean ± 3 sd [2.644, 3.342] |
| F06777 | 37141 | pdays | 4 | detector:dboost_gaussian_text | 17.1312 | dBoost gaussian: 'length' outside mean ± 3 sd [2.644, 3.342] |
| F06778 | 37143 | pdays | 2 | detector:dboost_gaussian_text | 17.1312 | dBoost gaussian: 'length' outside mean ± 3 sd [2.644, 3.342] |
| F06779 | 37147 | pdays | 4 | detector:dboost_gaussian_text | 17.1312 | dBoost gaussian: 'length' outside mean ± 3 sd [2.644, 3.342] |
| F08091 | 37764 | <record> |  | detector:iforest | 0.7031 | iforest_row: record-level outlier score (reference threshold 0.6196) |
| F08057 | 37591 | <record> |  | detector:iforest | 0.6947 | iforest_row: record-level outlier score (reference threshold 0.6196) |
| F08013 | 37356 | <record> |  | detector:iforest | 0.6936 | iforest_row: record-level outlier score (reference threshold 0.6196) |
| F07982 | 37197 | <record> |  | detector:iforest | 0.6927 | iforest_row: record-level outlier score (reference threshold 0.6196) |
| F07972 | 37141 | <record> |  | detector:iforest | 0.6922 | iforest_row: record-level outlier score (reference threshold 0.6196) |

## Feedback

Annotate `feedback.csv` (verdict: confirmed_error / not_an_error / unsure) and run `dqf feedback <scan_dir>` for adjudicated precision per source.
