# Independent ground truth: benchmark qualification and bounded validity checks

Status: 2026-10-20. Earlier negative results (`dataset_qualification.md`) were the starting point; each source
was re-checked against primary material in this session (`docs/sources/detector_benchmark_research_notes.md`).
Measured checks: `python scripts/independent_validation.py` → `results/qualification/independent_validation.json`
**[ours]**. Performance on *new synthetic errors* (pilot) and on *independently established errors* (this
document) are always reported separately.

## 1. Qualification of benchmark sources

| Source | Origin of errors | Reliability of the clean reference | Can our detectors see the error structure? | ≥ 2 candidates under comparable conditions? | Selection / test separable? | Verdict |
|---|---|---|---|---|---|---|
| **Raha Flights** (Li et al., PVLDB 2012; BigDaMa/raha) | natural: conflicting values from 38 web sources | gold standard from airline websites; ~7 % of error labels rest on imputed (scheduled) truth | transductive / redundancy-exploiting methods yes; CDC no (cross-row conflicts, chance-level AUC) | yes for transductive candidates (dBoost text, LUCARIO-core) and Raha | by row split only (flights repeat across sources) | **USE as separate real-error track** (non-financial; transductive methods) |
| **Raha Beers** | natural, manually cleaned listings | manual cleaning (Mahdavi et al.); mostly representation | format-type detectors yes; value-error detectors hardly | yes (transductive) | row split | **USE as separate track** (format errors; not value errors) |
| **Raha Tax** | synthetic (BART); 97.6 % of published differences are formatting artefacts | clean file has its own artefacts (dropped leading zeros, `0.0`) | yes after typing (≈ 2,000 substantive errors; 100 in our 10,000-row test sample) | yes (reference-trained and transductive) | yes (20k / 10k rows) | **USE as out-of-generator check** (synthetic) |
| Raha Hospital | synthetic `x` substitutions (508/509) | – | typo detectors only | – | – | not used |
| **REIN** datasets (Abdelaal et al., EDBT 2023) | 2 of 14 with real errors (Beers, Citation); 12 injected with BART / error-generator | clean = original public data | partly (injected outliers / noise in numeric tables) | in principle | yes | **BLOCKED**: data only on ResearchGate (HTTP 403 here), no data licence, code "All Rights Reserved"; REIN's dBoost results are tuned against ground truth |
| **Auto-Test** ST-/RT-Bench (Chen et al., SIGMOD 2025) | natural errors in crawled spreadsheet / BI columns | manual labels, cross-checked | **no**: each entry is a single column's list of distinct values (no rows, no other columns) | no (CDC, dBoost, IF need rows) | – | **DOCUMENT ONLY** |
| **AddressTable / Clean Me If You Can** (Ahmadi et al., arXiv 2606.31983) | natural web-extracted addresses | geocoder (Nominatim) output, 99.1 % agreement with Google on a 1k sample – agreement of two tools, not manual verification | string standardisation only | string detectors only | yes | **DOCUMENT ONLY** (code MIT, ground truth ODbL) |
| **TableEG Credit** (Liu et al., arXiv 2507.10934) | the dataset's own missing values and extreme incomes; most likely Kaggle "Give Me Some Credit" via CleanML (*provisional inference*) | "clean" values are repairs / imputations, not verified corrections; data on Google Drive without licence | – | – | – | **REJECTED as ground truth**; no connection to UCI Credit (no leakage risk) |
| BART (Arocena et al., PVLDB 2015) | generator (DC violations, typos, outliers) | by construction | yes | yes | yes | optional second generator; the Tax pair is used instead (`injection_strategies.md` §4) |

**No public financial dirty/clean benchmark with independently verified cell-level errors was found**
(consistent with the earlier, bounded search). The checks below are therefore either non-financial real-error
data or a different synthetic generator, and are reported as bounded validity checks.

## 2. Track A – out-of-generator: BART errors in Raha Tax [ours]

Reference-trained candidates are fitted on clean values of 20,000 rows; all candidates are scored on the dirty
values of 10,000 other rows (100 substantive BART errors: state 34, zip 24, single_exemp 17, marital_status 10,
has_child 10, child_exemp 5). The same candidates are evaluated on our injected errors (6 cases × 2 seeds,
1 % ECAR) in the same clean test rows. No conventional baseline exists for Tax (no contract), so increments
are over an empty baseline.

| detector | BART: recall | BART: precision (lb) | BART: dR@25 | ours: recall | ours: dR@25 |
|---|---|---|---|---|---|
| cdc (ranked) | 0.77 | 0.33 | **0.76** | 0.60 | **0.61** |
| lucario_core (batch) | 0.33 | **0.81** | 0.33 | 0.15 | 0.15 |
| dboost_histogram_text_batch | 0.57 | 0.01 | 0.03 | 0.24 | 0.01 |
| dboost_gaussian_text | 0.33 | 0.03 | 0.06 | 0.16 | 0.03 |
| dboost_gaussian | 0.11 | 0.004 | 0.01 | 0.21 | 0.02 |
| sd_outlier / iqr_outlier | 0.00 | 0.00 | 0.00 | 0.14 / 0.21 | 0.08 / 0.01 |

Selection agreement: at k = 10, 25 and 50 the detector selected on our injections (CDC) is also best on BART
errors (regret 0); rank correlation over all ten candidates is only ρ = 0.37 (the ordering below the winner
differs, e.g. SD is fourth on ours and last on BART). With flag-F1 as the utility the choice differs (ours: CDC,
BART: LUCARIO-core; regret 0.008). **Interpretation (provisional):** the top choice transfers to an
independent *synthetic* generator, in a setting where one method dominates; the rest of the ranking does not.

## 3. Track B – existing real errors: Flights and Beers [ours]

Only transductive candidates apply (CDC is incompatible with Flights; SD/IQR need numeric columns). Flights:
2,376 × 6, 4,920 erroneous cells (34.5 %); Beers: 2,410 × 9, 4,362 (20.1 %).

| dataset | detector | recall | precision | F1 | on our injected errors: F1 |
|---|---|---|---|---|---|
| Flights | lucario_core | 0.52 | 1.00 | **0.68** | 0.00 |
| Flights | dboost_histogram_text_batch | 0.26 | 0.55 | 0.35 | **0.10** |
| Flights | dboost_gaussian_text_batch | 0.04 | 0.82 | 0.08 | 0.00 |
| Beers | lucario_core | 0.27 | 0.80 | **0.41** | 0.002 |
| Beers | dboost_histogram_text_batch | 0.29 | 0.60 | 0.39 | **0.005** |
| Beers | dboost_gaussian_text_batch | 0.16 | 0.78 | 0.26 | 0.002 |

Selection on our injections (valid-code swaps and plausible substitutions in the clean files) picks the dBoost
histogram; on the real errors LUCARIO-core is best (Flights F1 regret 0.33; Beers 0.02). **But** 2,312 of
LUCARIO-core's 2,546 Flights flags are empty cells – errors that a `not_null` rule already catches; beyond
missing values it finds 222 of 2,608 real value conflicts (8.5 %). On Beers, 1,199 of its 1,496 flags are null
tokens (`N/A` etc.).

**Interpretation (provisional):** on real benchmark errors the mix is dominated by missing values and format
problems that our pilot catalog deliberately treats as *sanity* errors (caught by conventional rules), while
our primary catalog consists of in-domain value errors. A selection made on our catalog therefore does not
transfer to these benchmarks – not because the selection procedure is unreliable, but because the error
populations differ. This is the threat that matters most for the research question (what if the real errors
differ from those used for selection?), and it can be measured only where real errors exist.

## 4. What could not be investigated

- Real errors in *financial* tables (no qualified public source).
- REIN's twelve injected datasets (blocked by access and licence).
- Raha (few-label track) on the same Flights/Beers splits in this run (environment not reinstalled in this
  container; the earlier result P 0.88 / R 0.68 / F1 0.77 on Flights stands, `method_compatibility.md`).
- LUCARIO's original code (no licence) – the numbers above are for the partial re-implementation.
