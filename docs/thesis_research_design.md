# Integrated exploratory MSc research design

Date: 2026-10-21. This is a new exploratory study on a new branch, not an execution of the reserved
confirmatory protocol in `research_design.md`. Existing experiment folders and conclusions are retained.
The executable specification is `config/thesis/study.yaml` plus the three source configurations.

## Question, hypotheses and scope

**How reliably can controlled error injection guide the selection of cell-level error detectors that
add detection value beyond conventional data-quality checks?** The question is unchanged by outcomes.

- H1: incremental utility varies with error family and baseline strength more than a single overall
  detector ranking suggests.
- H2: placement dependence (ECAR/EAR/ENAR) changes utility and can change a selector's choice.
- H3: a mechanism-diverse simulation design transfers better than ECAR-only selection; this can fail.
- H4: a case-uncertainty/family-guarded selector reduces target regret compared with mean selection;
  its conservatism may instead miss gains, so superiority is not assumed.
- H5: published-reference validation can disagree with synthetic selection; applicability and label
  reliability may prevent a meaningful transfer claim altogether.

The intended empirical package is substantial exploration, not a completed thesis. Supervisor agreement,
independently qualified labels, broader method replication and the reserved evaluation remain separate.

## Data and information tracks

Controlled sources: UCI Credit (30,000 rows, 23 model attributes), Bank Marketing (41,188 rows,
20 model attributes, derived actual delivery periods) and newly acquired white Wine Quality (4,898 rows,
11 chemical measurements). Wine's sensory `quality` prediction target is excluded. Its public primary
source is UCI 186, DOI 10.24432/C56S3T; archive and member hashes are pinned in `config/datasets.yaml`.
The source documentation is downloaded read-only with the measurements. No DQ gold labels exist for
these unmodified tables; injected changes alone provide exact by-construction labels.

Published track: reuse the completed, frozen dirty-only Rayyan/Restaurant/Cars scans, verify every
prediction artifact and re-evaluate the **new cost policy** without injection or refitting. The earlier
audit and results were already visible, so this is not pristine external confirmation. Restaurant/Cars
are published tab_err synthetic missingness variants, not out-of-generator natural errors. Rayyan is
uncertain. Flights has partial/imputed cross-source truth; Beers is predominantly standardization; Tax
is BART-generated and dominated by numerical/ZIP representation artefacts. Earlier qualification of
those three sources is retained as historical context, not pooled as equal-information new results.

Primary candidates are three configurations from two families (CDC-HGB, typed/text dBoost); secondary
IQR uses historical data too. No labels, clean target values, supervised detector outputs, LLM knowledge
or clean-valued lookup tables enter this common training track. Separate literature tracks are explicit
in `thesis_literature_review.md`. No paid API or purchased compute is permitted or used.

## Splits, leakage and compute

The existing exact-duplicate-aware split at seed 1 reserves its `test` partition. `pilot_split` first
excludes that holdout, then makes historical/reference, simulation-selection and exploratory-target
partitions in a 50/25/25 ratio. Calling the last partition `test` in machine outputs does **not** make
it the confirmatory holdout. The study reads no confirmatory target labels and does not score its rows.

Three existing exploratory seeds (11/12/13) are used for each source. Random design pools are capped
at 9,000 rows for bounded compute. Bank additionally uses the first two already documented delivery
sets: history periods 1–2, selection 3, target 4; then history 3–4, selection 5–6, target 8–9. These
follow actual recorded order; no temporal split is invented for Wine or Credit. Temporal selector
training uses only its own earlier selection period, not random simulations from future bank periods.

Eleven full replications are planned: three per source plus two temporal Bank replications. All four
candidate configurations execute complete scenario sets without `--max-scenarios`. The existing
runner fits each reference method once and re-scores changed rows, which is exact for the selected
row-independent reference methods. LUCARIO-core is **not** added to this optimization: its adaptive
batch-level constraint dropping would violate that independence assumption.

Maximum two local processes, two OpenMP/BLAS threads per worker; no GPU or paid infrastructure.
The driver enforces native thread counts through `threadpoolctl` after import/fork as well as environment
variables; each completion records the effective native pools. The initial attempt was stopped after
an import-order thread-limit fault, archived, and restarted with unchanged scientific settings. See
`results/thesis_integrated/execution_notes.json`; that attempt is excluded from final aggregates.
`frozen_inputs.json` hashes code, contracts, configuration, generated dbt and lockfile before execution.
Each completed run hashes its output files in `complete.json`. Resume accepts only matching inputs
and intact outputs, never overwrites a different completed study. Raw values and exact injection
positions/originals are retained locally in ignored `injection_log.parquet` using Python repr strings.

## Error populations

Rates 1% and 2% are primary. Missing values/invalid codes are sanity scenarios, reported separately
from substantive families. Existing cases cover scaling/unit mistakes, valid categorical swaps/remaps,
reference-plausible numerical substitutions, column/period shifts, keying and rounding. Applicable
families vary by source; Wine has no non-target categorical code or actual chronology, so those
conditions are unsupported, not fabricated.
Each scenario changes one target column: the nominal rate is a fraction of batch rows/target-column
cells, not of every cell in the wide table. Actual by-construction prevalence over all attributes is
therefore smaller and differs with feature width; `intended` and `realised` retain the exact counts.

For every case/rate, simple simulation uses three ECAR injections; diverse simulation uses the same
three-scenario budget rotating ECAR, contextual EAR and value-dependent ENAR at strength 4. These
settings affect *placement*, not the error operation. Injection seeds, selected positions, intended
and realized counts are recorded. Placement strengths/directions/conditioning attributes shift to
strength 8 in held-out cases, and a target rate-2% analysis selects using only rate-1% simulations.
The existing generator excludes EAR when its conditioning attribute is the corrupted attribute itself;
that would be ENAR. It rotates over the remaining applicable mechanisms instead. Equal scenario counts
therefore do not imply an artificially complete or balanced mechanism factorial for every case.

Unchanged selected cells do not count as errors. Zero-change scenarios and exceptions are failures
with a stated reason, not zero-performing detectors. The inherited materiality criterion for
`plausible_substitution` is 0.2 × max(|value|,1); this absolute floor can make small-unit chemistry
columns unsupported. It is not retuned to improve detector results.

## Baselines, total budget and metrics

A = existing deterministic source-contract dbt/SQL checks. B = A plus historical statistical
envelopes/rare-category controls. Wine adds completeness, nonnegativity, pH screening and free ≤ total
sulfur checks; rule status/evidence is explicit, mostly provisional. No rule is selected from injected
target labels or clean reference repairs.

Budgets are **10, 25 and 50 unique total cells per 1,000 rows**, k = round(budget × rows/1000).
Baseline-only reviews k baseline flags. Augmentation reserves ceil(k/2) baseline flags, then novel
detector candidates excluding all baseline flags, returning unused capacity to baseline alerts.
There is no free baseline credit: a detector may displace a useful baseline review and have negative
incremental utility. Uniform seeded cell priorities (seed 0) order baseline/binary alerts and break
score ties. Finite genuine detector scores rank candidates; no binary score is invented.
The fixed 50/50 allocation is one explicit operational policy, not an optimized or universally optimal
fusion rule. Baseline random ordering ignores severity, so conclusions are conditional on this policy.

Primary utility = R(augmented shared queue) − R(baseline-only queue), with both queues costing at most k.
Also report baseline/standalone/augmented recall, injection-relative precision lower bound, native
flags/workload, new and displaced injected detections, detector overlap, all-scored-cell average
precision and scored-positive coverage. PR curves are illustrative first-test-case-per-family traces
chosen by fixed generation order, averaged for display; AP is computed from actual scores. Untouched
alerts are never labelled verified false positives. Old extra-ML-budget metrics are retained for
backward compatibility but are not substituted for this new estimand.

## Selection algorithms fixed before outcome analysis

Eligible candidates are the three primary configurations. Incompatible/failed methods are absent,
not assigned zero utility. NO_ADDITION has utility zero. Ties follow sorted method identity.

**Naive:** average utility within each error case over dependent seeds/rates/mechanisms, then mean over
cases. Choose the highest mean if positive, otherwise NO_ADDITION.

**Robust:** use the same case means; require at least three cases. Bootstrap cases 1,000 times with
seed 0. A candidate is eligible only if its 10th-percentile mean exceeds 0.005 recall and its worst
observed family mean is at least −0.01. Select the highest eligible lower bound. If all means are
nonpositive, return NO_ADDITION; otherwise abstain with INSUFFICIENT_EVIDENCE and take no addition.
These are provisional decision parameters, not a newly validated optimal robust-selection method.

Outcomes: matched ECAR/mixed conditions; held-out column×operation cases and direction/strength;
leave-one-whole-family-out selector training; rate/strength shift; leave-one-entire-source-out selection;
and later genuine bank delivery periods. The existing configuration's `test_heldout` is a held-out
*case* set, not necessarily a new family; the explicit leave-family-out analysis supplies the latter.
Report choice agreement, tolerance-0.005 agreement, regret against the target's best eligible method
including NO_ADDITION, target additional detections and withdrawal rates. Target labels calculate
outcomes and the oracle only; `choose()` receives selection rows exclusively.

## Uncertainty and limitations fixed in advance

Injection seeds and resplits reuse source records, so they are dependent. Collapse those observations
within error case before any bootstrap; conditional case-bootstrap intervals describe case-mix
sensitivity within a source, not population confidence over three datasets. Pair selectors on the
same target conditions. Show descriptive differences and negative results without treating thousands
of scenarios as thousands of independent data sources. Source transfer has only three domains and
cannot establish universal generalization.

Mechanism diversity and family exclusion are analysed separately, alongside baseline changes. A
balanced full factorial is impossible where semantics differ; report absent cells and realised
injection rates. Full LUCARIO/Picket qualification is not achieved by renaming a partial adaptation.
Published reference uncertainty may make selector transfer unidentifiable; do not replace an
unscorable benchmark with a favourable synthetic score.

CDC's earlier Cars snapshot used 32 calibration rows, whereas this controlled study fixes 512.
Those tiny published histories cannot meet the latter's training/calibration requirement. Therefore
that snapshot is descriptive secondary evidence, not a configuration-matched selector-transfer test.
Published transfer restricts eligibility to the matching dBoost variants; it does not replace an
incompatible CDC result with zero or silently change its parameters.
