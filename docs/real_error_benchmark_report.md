# Published dirty/clean benchmark evaluation

Date: 2026-10-20. **Exploratory service evaluation completed; no confirmatory study or production claim.**
Branch: `codex/dataset-extension-rayyan-restaurant-cars`. The research question in `research_design.md`
is unchanged. Machine-readable results: [`results/real_error_benchmark/`](../results/real_error_benchmark/).

## 1. Main result

The existing service can ingest all three dirty sources, execute generated dbt/SQL tests and historical
statistical controls, run compatible cell detectors, and produce findings with explanations. Nine scans
completed without detector failures. **Neither ML nor the other cell detectors added a single labelled
missing-value detection beyond the conventional controls in Restaurant or Cars**, at any of the fixed
10/25/50-extra-reviews-per-1,000-row budgets. This is a meaningful ceiling result: these released variants
mostly exercise missingness already covered by `not_null`, not subtle substantive errors.

Rayyan does not support an accuracy claim without adjudication. Its reference contains ambiguous date,
encoding, sentinel and pagination changes. We measured workload and overlap with these candidates, but
did not call the 948 source differences 948 proven errors. These datasets do not establish the usefulness
of ML additions for independently verified, substantive real errors.

## 2. Sources, feature scope and label policy

No new errors were injected and no source file was modified. All six SHA-256 pins passed before/after the
runs. Sources, full hashes and licensing caveats are in `published_benchmark_datasets.md` and the
`data/manifests/{raha_rayyan,jung_restaurant,jung_cars}.acquisition.json` manifests.

| Source | Contract / evaluated attributes | Reference interpretation |
|---|---|---|
| Rayyan, 1,000 × 11 | Ten bibliographic fields; `id` retained only as row identity | All changed, non-equivalent references are **uncertain corrections**, not adjudicated positives. A reference that remains missing is unknown, not a negative. |
| Restaurant, 864 × 6 | Five business fields; `class` excluded from both predictors and scored cells | Of 155 source differences, 30 concern the entity/group annotation `class`. The remaining 125 are published synthetic `?` missing-value labels, evaluated only on batch rows. |
| Cars, 406 × 9 | Seven numeric attributes plus categorical `Origin`; `Car` excluded as a model identifier | The full source has 110 synthetic `?` missing values and 710 numerically equivalent format differences. Numeric equivalence is not an error label. |

The frozen `conservative_v1` evaluator separates `missing`, `formatting`, `value_candidate`, `uncertain`,
`reference_missing` and `agreement`. Finite Decimal equivalence is applied only to declared numeric
attributes; NFC/whitespace equivalence identifies representation changes. Dates are not guessed.
`value_candidate` means a changed value under a synthetic published reference, not independent human
confirmation. **No substantive-value positives occurred in these evaluated batches.**

For Restaurant/Cars, reference-relative recall/precision use missing/value-candidate labels. Uncertain or
reference-missing cells are excluded from the precision denominator but their reviews still consume
capacity and are reported. Formatting and reference-agreeing cells do not count as missing-value hits.
Reference agreement does not prove absence of an unannotated source defect; these are reference-relative
metrics, not verified false-positive rates. Rayyan's error recall/precision are undefined and left blank.

## 3. Dirty-only contracts, splits and leakage prevention

The new source contracts are in `config/contracts/`. Missing tokens are opt-in per column: `?`/empty
strings become NULL in Restaurant/Cars, empty strings in Rayyan. Raw files and identifier strings remain
unchanged. Unknown numeric strings fail ingestion rather than silently becoming missing values.

- Rayyan: provisional required bibliographic fields, Unicode replacement-character checks and
  dirty-history length/language controls. A guessed canonical-date rule is explicitly disabled.
- Restaurant: provisional listing completeness and conservative phone-character checks, plus
  dirty-history city/cuisine frequencies and text-length envelopes. Telephone numbers are identifiers.
- Cars: completeness, nonnegative measurements, integral counts/year codes, historical numerical
  envelopes and region frequencies. No observed clean minima/maxima or repaired values configure rules.

All statistical bounds and detector models learn from **dirty historical rows**, which may contain errors.
Quantiles (0.0005/0.9995), category share (0.005), model parameters and budgets were fixed before these
service outcomes were evaluated. No clean training rows, selected clean subsets, clean calibration values
or clean-derived lookup dictionaries are provided to a service run.

`config/benchmarks/published_errors.yaml` fixes seeds 11/22/33, a 60% historical share of the available
groups, review seed 0 and the primary budget 25/1,000 rows. Dirty-only grouping unions equal normalized
article titles, restaurant names/known dirty classes, or car model names. Missing class `?` never joins
unrelated records. Restaurant class is used **only for grouping**, never as a detector feature.

The existing seed-1 `make_split(..., test)` holdout is excluded, and exclusion expands to entire groups
touching it. Thus no recognized group crosses history, batch or holdout. Approximate identifiers are not
a complete entity-resolution guarantee. There is no fabricated delivery chronology.

| Source | History rows, seeds 11 / 22 / 33 | Batch rows | Reserved rows | Batch positive labels | Batch formatting / uncertain labels |
|---|---|---|---|---|---|
| Rayyan | 448 / 478 / 478 | 352 / 322 / 322 | 200 | None adjudicated | 336 / 300 / 305 uncertain; another 584 / 508 / 526 reference-missing cells |
| Restaurant | 362 / 391 / 386 | 290 / 261 / 266 | 212 | 49 / 29 / 43 missing | 0 formatting; 1 / 0 / 1 reference-missing cells |
| Cars | 157 / 179 / 176 | 118 / 96 / 99 | 131 | 27 / 28 / 21 missing | 209 / 157 / 164 numerical-format differences |

All nine scan configs, row assignments and source/code/config fingerprints were saved before scoring.
All nine scans finished **before** the evaluator opened reference values. The evaluator checks the frozen
plan, code/configuration fingerprints and prediction-artifact hashes; it never fits models or thresholds.
Only eligible batch rows are assigned evaluation labels. The frozen plan hash is
`ef2e1c091efef34ba71677e042640c17d4678a13331c4b4b42b358a569cd059f`.

A full repeat reproduced all 408 metric rows and aggregate label counts exactly. Between the runs,
only status-table presentation and an obsolete dBoost metadata description were corrected; contracts,
grouping, label policy, model parameters and budgets were unchanged. The final fingerprint above records
the corrected code. The repeat is a reproducibility check, not another set of independent replications.

This is a computational freeze, not formal preregistration. Earlier acquisition work already audited
the complete pairs; that prior exposure is disclosed. The three overlapping resamples of one published
variant per source are **not three independent datasets or error-generation replications**. No
bootstrap confidence interval or confirmatory significance is manufactured from them.

## 4. Detector compatibility

| Existing method | Rayyan | Restaurant | Cars |
|---|---|---|---|
| CDC-HGB reimplementation | Incompatible: 447–478 distinct article-title categories in history | Incompatible: 335–354 distinct business-name categories | Runs, **conditional**; only 32 calibration rows and rare region labels |
| dBoost Gaussian, text expansion | Runs | Runs | Runs, including missing numeric fields represented as empty text |
| dBoost Gaussian, inferred types | Same text-only feature scope; not redundantly run | Same text-only scope; not redundantly run | Runs conditionally; skips 22 / 18 / 16 batch rows with unparseable numeric/missing values |
| LUCARIO-core | Runs as a provisional partial implementation | Runs as a provisional partial implementation | Runs as a provisional partial implementation |
| SD / IQR | Not applicable: no numeric contract targets | Not applicable: no numeric contract targets | Run on numeric attributes only; missing numeric targets are not outlier-scored |

CDC confidence remains 0.999, max_iter 100, model seed 0, normalized-residual ranking. The 32-row
calibration configuration permits a computational small-table check, **not a 99.9% coverage claim**.
Its conformal resolution is too coarse and historical errors compromise its clean-reference assumption.
No high-cardinality text field was silently dropped just to make CDC run on Rayyan/Restaurant. Cars'
model identifier is explicitly excluded in its contract, so its applicability is to that numeric/code view.

dBoost uses the existing clean-room implementation, Gaussian threshold 3. Ranking its maximum expanded
feature deviation is the repository's documented extension (D-27), not a new claim about the original
binary method. Native flags are evaluated separately. Text mode is important: inferred-type dBoost
silently losing missing-value rows would otherwise overstate its coverage. Its skipped rows remain in
the evaluator's target denominator.

LUCARIO-core is the existing partial, provisional implementation without regex-pattern constraints;
these are not results for full LUCARIO. All methods here fit on history for an information-matched
comparison. Original CDC/AutoGluon and supervised Raha are not newly qualified: they require different
environments/information (including labelled tuples for Raha). Isolation Forest remains row-level and
is not substituted for a cell-level detector.

## 5. Fixed-budget comparison

Two cost models are reported separately:

1. **Equal total budget:** each standalone policy receives `round(25 × batch_rows / 1000)` unique
   cells: Rayyan 9/8/8, Restaurant 7/7/7, Cars 3/2/2. Scored methods rank finite scores; controls and
   binary methods hash-order their flags with the fixed label-blind tie seed. They cannot fill unused
   capacity with fabricated scores. Native flags are also reported without a budget cap.
2. **Increment over existing controls:** all unique baseline alerts are an already-incurred cost;
   one detector adds at most k cells absent from that baseline. Both deterministic and full
   (deterministic + statistical) baselines are evaluated. Baseline cost is explicitly retained in
   `metrics.csv`; an additive result is not an equal-total-cost comparison.

Means below are unweighted descriptive averages over the three resamples, not estimates over
independent sources. Precision is against the restricted published-reference labels, in percent.

| Source | Policy | Native reference recall | Standalone recall @25 | Standalone precision @25 | Extra recall beyond deterministic / full @25 |
|---|---|---:|---:|---:|---:|
| Restaurant | Deterministic controls | 100.0% | 18.23% | 100.00% | — |
| Restaurant | Full controls | 100.0% | 5.42% | 33.33% | — |
| Restaurant | dBoost text | 100.0% | 14.48% | 80.95% | 0 / 0 |
| Restaurant | LUCARIO-core | 100.0% | 15.13% | 80.95% | 0 / 0 |
| Cars | Deterministic controls | 100.0% | 9.26% | 100.00% | — |
| Cars | Full controls | 100.0% | 6.79% | 77.78% | — |
| Cars | CDC-HGB | 0.0% | 0.00% | 0.00% | 0 / 0 |
| Cars | dBoost text | 100.0% | 9.26% | 100.00% | 0 / 0 |
| Cars | dBoost inferred types | 16.01% | 6.83% | 72.22% | 0 / 0 |
| Cars | LUCARIO-core | 100.0% | 6.44% | 72.22% | 0 / 0 |
| Cars | SD / IQR | 0.0% | 0.00% | 0.00% | 0 / 0 |

The complete 408 metric rows include all seeds, native operation and the fixed 10/25/50 sensitivity
budgets. Extra reference-error recall is zero for every applicable Restaurant/Cars method at **all**
three budgets. CDC does not flag missing targets; SD/IQR test present numeric extremes. They were not
retuned after that negative result. dBoost text and LUCARIO can rediscover missing values, but cannot
add any after `not_null` has already detected them.

Full controls have the same native missing-value recall as deterministic controls but more unrelated
alerts. Their lower capped recall reflects the predeclared uniform queue ordering, not worse detection.
Prioritizing explicit missing-value alerts would change the queue result; that policy was not selected
after observing these scores. It is an engineering follow-up, not evidence for an ML advantage.

## 6. Workload, findings and explanations

| Source | Deterministic native alerts / 1k rows | Full controls | dBoost text | LUCARIO-core | Interpretation |
|---|---:|---:|---:|---:|---|
| Rayyan | 627.0 | 672.3 | 780.3 | 2,825.9 | Dominated by optional/reference-missing fields and uncertain repairs; operational workload is high |
| Restaurant | 149.6 | 352.0 | 200.1 | 185.9 | Explicit missingness is useful; statistical novelty adds substantial reference-agreeing workload |
| Cars | 244.2 | 310.0 | 250.4 | 284.6 | Missing tokens are directly actionable; numerical novelty and representation effects need review |

Rayyan native candidate-difference recall is only a localization diagnostic: deterministic controls
overlap 7.42% of raw changed cells, dBoost text 10.00%, LUCARIO-core 11.15%. These are **not error-recall
estimates**. The primary extra budget selected no changed Rayyan candidate. At the predeclared 50/1,000
sensitivity budget, some uncertain candidates are selected (at most 1.49% raw candidate recall in an
individual added queue); they are not promoted to verified errors. Many selected cells
were missing in both versions, for which the reference cannot adjudicate whether an alert is useful.

All nine service scans produced nonempty findings with rule/detector provenance and nonempty explanations:
**4,234 findings, all 4,234 explained** (1,056 rule findings and 3,178 detector findings). Counts include
separate sources for the same cell and all native flags, not 4,234 reviewed or distinct errors. The
`review_selected` flag identifies the per-detector capped extra queue; merely displaying a native flag
does not make it a budgeted detection.

Rule explanations state the observed NULL/value and required condition or historical bound; CDC gives
its predicted median/interval or category probability; dBoost flagged cells identify the expanded
feature/bound; LUCARIO/SD/IQR name their constraints. Unflagged score-ranked suggestions explicitly say
they are review candidates, not native flags. These explanations establish technical provenance, not
human usefulness or causality. No user study or independent manual adjudication was performed.

Restaurant and Cars therefore produce actionable missing-token findings. Rayyan produces inspectable
encoding/completeness candidates but its high workload and ambiguous reference prevent a usefulness
claim. Every applicable service recommendation is **INSUFFICIENT_EVIDENCE** because no suitable
source-specific, independent selection-reliability evidence exists. Financial pilot evidence is not
borrowed to manufacture ADOPT on another domain.

dbt executed 10 tests per Rayyan scan, 11 per Restaurant scan and 25 per Cars scan. Test `warn` statuses
are expected data-quality violations with stored evidence, not Python/SQL execution failures. No dbt
error or failed detector execution occurred; six CDC/source combinations were explicitly incompatible.

## 7. Comparability and MSc-study decision

The financial pilot uses controlled injected errors with by-construction labels, mostly numerical/code
features and substantially larger reference/calibration sets. This evaluation uses dirty history and
published dirty batches without new injection; text-heavy domains, reference uncertainty and tiny
budgets/calibration make a pooled F1 or a numerical ranking across the two studies unjustified.
The incremental cost definition is shared with the pilot, but the error populations and label quality
are not. Restaurant/Cars still originate from the **same tab_err generator family** used by this project:
they are external published replications, not independent natural-error validation.

| Dataset / method | Decision for a definitive MSc study |
|---|---|
| Restaurant | Retain as a transparent missing-value sanity/portability benchmark. Not a decisive test of incremental ML value or substantive real errors. Exclude `class` from prediction/scoring. |
| Cars | Optional missingness/representation stress test only. Keep numeric-format labels separate and all skipped dBoost rows visible. Too small and too trivial under `not_null` for a primary detector-selection study. |
| Rayyan | Exploratory only until independent adjudication resolves dates, encodings, sentinels and reference conversions. Do not use strict cell differences as confirmatory gold labels. |
| CDC-HGB | Keep as an existing numerical/code candidate for appropriately supported financial sources; no new evidence of utility here. Incompatible with these text views, weakly calibrated and zero missing-value gain on Cars. |
| dBoost text | Retain as a cell-level comparator/stress detector with explicit workload costs. It runs across these views but shows zero added labelled-error recall beyond completeness controls. No adoption claim. |
| dBoost inferred types | Conditional comparator on parseable numerical data; unsuitable as the sole detector of missing numeric values because it skips affected rows. |
| LUCARIO-core | Provisional secondary baseline only; partial implementation and high Rayyan workload preclude claims about the published full method. |
| SD / IQR | Keep simple numerical baselines where applicable; zero missing-value detection is expected, not evidence that they fail at detecting substantive numerical outliers. |

**Do not change the research question to obtain positive outcomes.** Retain the existing question about
reliability and incremental value under changed error conditions. Before a definitive natural-error
claim, obtain adjudicated substantive errors with compatible information requirements and enough
independent groups/sources; freeze that protocol separately. A well-documented zero increment remains
a valid result. These current benchmarks support feasibility and falsify a blanket claim that ML
necessarily improves completeness controls; they do not settle the main MSc hypothesis.

## 8. Reproduce and validate

From the repository root:

```bash
export UV_CACHE_DIR=/workspace/.cache/uv   # cloud workspace; omit outside this environment if unnecessary
uv sync --frozen --extra dev --python 3.12
source .venv/bin/activate
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 DBT_SEND_ANONYMOUS_USAGE_STATS=false
python scripts/download_datasets.py raha_rayyan jung_restaurant jung_cars
python scripts/verify_datasets.py raha_rayyan jung_restaurant jung_cars
dqf controls generate raha_rayyan jung_restaurant jung_cars
python scripts/evaluate_real_error_benchmarks.py --phase scan
python scripts/evaluate_real_error_benchmarks.py --phase evaluate
# Equivalent two-phase sequence: python scripts/evaluate_real_error_benchmarks.py --phase all

# Independent operational example: only dirty input, no evaluator
dqf scan config/scans/scan_published_jung_restaurant.yaml
# Also available: scan_published_raha_rayyan.yaml and scan_published_jung_cars.yaml

ruff check src scripts tests
python -m pytest -q -ra
```

Raw examples, partition row IDs, complete scores, findings, feedback and dbt artefacts remain under
git-ignored `results/runs/real_error_benchmark/` and `results/runs/scans/`. Committed CSVs contain only
metrics, compatibility, aggregate label counts and service checks; `protocol.json` records fingerprints
and output hashes, without raw record values. Runtimes and some dbt runtime hashes can change on a
rerun; fixed settings, assignments, label counts and ranked selections should reproduce.

Leakage tests run the real service while opening `clean.csv` is forbidden. Other tests cover dirty-only
entity grouping/holdout reservation, numeric-token safety, label ambiguity, finite-score/binary budget
ordering, frozen-input checks, and contract-to-dbt drift. Final validation: **184 passed, 9 skipped**,
with two existing `tab_err` warnings; Ruff passed. Skips comprise four absent UCI/Kaggle datasets,
three original-dBoost fidelity checks and two UCI-dependent pilot/scan tests. All three new-source
dirty-only service integration tests executed and passed.
Optional original-detector environments and absent financial/Kaggle datasets remain separate from this
new benchmark's executed service checks. Licence uncertainty remains unresolved; no raw data is committed.
