# Data-quality scan: scan_bank_marketing_rules_only

Dataset `uci_bank_marketing` · history 26,336 rows · new batch 3,308 rows · run 2026-10-20T19:07:11+00:00 · framework 0.1.0

> Findings are **review candidates**, not verified errors: this batch has no ground truth. Recommendations rest on offline evidence from synthetic errors.

## Existing controls

dbt tests: {'pass': 53, 'warn': 5}; alerts: 20 ({'statistical': 20}); implicated cells 6.0 per 1,000 rows (untouched evaluation partitions of the pilot: 13.9; ratio 0.44).

## Learned and literature detectors

| detector | level | learns on | scores | flags | extra beyond controls (per 1k rows) | listed | seconds |
|---|---|---|---|---|---|---|---|
| cdc | cell | reference | yes | 141 | 141 (42.6) | 190 | 33.9 |
| dboost_gaussian_text | cell | reference | yes | 711 | 711 (214.9) | 711 | 1.6 |
| dboost_gaussian | cell | reference | yes | 902 | 902 (272.7) | 902 | 0.8 |

Review budget: 25 extra cells per 1,000 rows = 83 cells for this batch; scored detectors list their top cells within that budget plus their own flags, binary detectors list their flags.

## Recommendation per detector

- **cdc: ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.143 [0.131, 0.152] over 5 pilot replications (ranked; scheme random)
- **dboost_gaussian_text: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.039 [0.038, 0.041] over 5 pilot replications (ranked; scheme random)
- **dboost_gaussian: DO_NOT_ADOPT** – offline held-out utility at 25 reviews/1k rows: 0.031 [0.027, 0.035] over 5 pilot replications (ranked; scheme random)

## Findings (first 40 of 1823; full list in findings.csv)

| id | record | column | value | source | score | explanation |
|---|---|---|---|---|---|---|
| F00001 | 37559 | age | 17 | rule:S_ENV_age |  | observed 17.0; expected within reference envelope [18.0, 88.0] |
| F00002 | 18729 | campaign | 43 | rule:S_ENV_campaign |  | observed 43.0; expected within reference envelope [1.0, 32.0] |
| F00003 | 18829 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00004 | 18839 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00005 | 18859 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00006 | 18869 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00007 | 18879 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00008 | 18899 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00009 | 18919 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00010 | 18929 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00011 | 18939 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00012 | 18949 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00013 | 18959 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00014 | 18969 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00015 | 18979 | euribor3m | 4.97 | rule:S_ENV_euribor3m |  | observed 4.97; expected within reference envelope [0.635, 4.97] |
| F00016 | 23999 | euribor3m | 5.045 | rule:S_ENV_euribor3m |  | observed 5.045; expected within reference envelope [0.635, 4.97] |
| F00017 | 24009 | euribor3m | 5 | rule:S_ENV_euribor3m |  | observed 5.0; expected within reference envelope [0.635, 4.97] |
| F00018 | 39389 | euribor3m | 0.634 | rule:S_ENV_euribor3m |  | observed 0.634; expected within reference envelope [0.635, 4.97] |
| F00019 | 40699 | previous | 5 | rule:S_ENV_previous |  | observed 5.0; expected within reference envelope [0.0, 4.8325] |
| F00020 | 6929 | education | illiterate | rule:S_RARE_education |  | observed illiterate; expected value seen in reference with sufficient frequency |
| F00021 | 8009 | campaign | 1 | detector:cdc | 0.9990 | CDC: predicted median 2; conformal interval [-8.266, 9.678] (c=0.999) |
| F00022 | 7369 | marital | unknown | detector:cdc | 0.9990 | CDC: most likely 'married' (p=0.83); observed value has p=0.000 |
| F00023 | 3479 | marital | unknown | detector:cdc | 0.9990 | CDC: most likely 'married' (p=0.76); observed value has p=0.000 |
| F00024 | 37259 | marital | unknown | detector:cdc | 0.9990 | CDC: most likely 'single' (p=0.91); observed value has p=0.000 |
| F00025 | 26729 | job | student | detector:cdc | 0.9990 | CDC: most likely 'admin.' (p=0.48); observed value has p=0.000 |
| F00922 | 18729 | campaign | 43 | detector:dboost_gaussian | 40.5586 | dBoost gaussian: 'id' outside mean ± 3 sd [-5.739, 10.87] |
| F00923 | 40399 | pdays | 16 | detector:dboost_gaussian | 33.1109 | dBoost gaussian: 'id' outside mean ± 3 sd [405.4, 1520] |
| F00924 | 40669 | pdays | 22 | detector:dboost_gaussian | 33.1109 | dBoost gaussian: 'id' outside mean ± 3 sd [405.4, 1520] |
| F00925 | 41029 | pdays | 17 | detector:dboost_gaussian | 33.1109 | dBoost gaussian: 'id' outside mean ± 3 sd [405.4, 1520] |
| F00926 | 37339 | previous | 4 | detector:dboost_gaussian | 21.4717 | dBoost gaussian: 'id' outside mean ± 3 sd [-1.3, 1.646] |
| F00211 | 24009 | euribor3m | 5 | detector:dboost_gaussian_text | 41.8895 | dBoost gaussian: 'is digit' outside mean ± 3 sd [-0.07101, 0.07215] |
| F00212 | 40979 | euribor3m | 1 | detector:dboost_gaussian_text | 41.8895 | dBoost gaussian: 'is digit' outside mean ± 3 sd [-0.07101, 0.07215] |
| F00213 | 40989 | euribor3m | 1 | detector:dboost_gaussian_text | 41.8895 | dBoost gaussian: 'is digit' outside mean ± 3 sd [-0.07101, 0.07215] |
| F00214 | 3019 | campaign | 10 | detector:dboost_gaussian_text | 6.0561 | dBoost gaussian: 'length' outside mean ± 3 sd [0.5443, 1.509] |
| F00215 | 3439 | campaign | 25 | detector:dboost_gaussian_text | 6.0561 | dBoost gaussian: 'length' outside mean ± 3 sd [0.5443, 1.509] |

## Feedback

Annotate `feedback.csv` (verdict: confirmed_error / not_an_error / unsure) and run `dqf feedback <scan_dir>` for adjudicated precision per source.
