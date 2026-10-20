# Operational demonstration: scanning a new batch (`dqf scan`)

Status: 2026-10-20 · implementation `src/dq_framework/service/scan.py` · configs `config/scans/` · tests
`tests/test_scan.py`. The operational workflow is separate from the offline evaluation: it never injects
errors, never reads ground truth and never tunes anything on the batch; it only *consumes* the offline evidence
file written by `scripts/analyse_pilot.py` (`results/pilot/detector_evidence.csv`).

## 1. What a scan does

| Step | Implementation | Output |
|---|---|---|
| 1. connect dataset + contract | `config/contracts/<dataset>.yaml` → generated dbt models/tests | – |
| 2. choose history and new batch | `history` / `batch`: delivery periods, row ranges or a sample; rows of the confirmatory hold-out are excluded by default | row counts in `scan_summary.json` |
| 3. existing controls | dbt Core on DuckDB, statistical bounds fitted on history | `controls/` (dbt artefacts), rule findings |
| 4. learned / literature detectors | fitted on history (`fit_scope = reference`) or on the batch (transductive) | detector findings |
| 5. findings | every finding has `finding_id`, `_row_id`, natural key (`record_key`), `column`, `value`, `source` (`rule:<id>` or `detector:<key>`), `tier`, rule status, `score` (only for methods that publish one) and an `explanation` | `findings.csv` |
| 6. recommendation per detector | `recommend()`: ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE | `scan_summary.json`, `scan_report.md` |
| 7. optional feedback | `feedback.csv` (verdict: confirmed_error / not_an_error / unsure) → `dqf feedback <dir>` | adjudicated precision per source |

Explanations: rules state observed vs expected (e.g. "observed 18.0; expected within reference envelope
[19.0, 81.8]"); CDC states its expectation ("predicted median 2.03; conformal interval [−9.1, 8.7]" or "most
likely 'thu' (p = 1.00); observed value has p = 0.000"); dBoost names the expanded feature and bound
("'length' outside mean ± 3 sd [0.08, 5.19]"); LUCARIO-core names the violated constraint; Isolation Forest
reports a record-level outlier score.

Review budget: scored detectors list finite top-k cells beyond the existing controls (k = budget × rows / 1,000)
plus their own flags; binary detectors list their flags. `review_selected` marks the capped extra queue,
using deterministic label-blind ordering for tied scores/binary flags. No ranking score is invented for
binary methods. Displayed native flags can exceed k and are not all counted as reviewed.

## Published-pair service evaluation

`config/scans/scan_published_{raha_rayyan,jung_restaurant,jung_cars}.yaml` connect dirty-only versions of
the published sources. `group_split` reserves the seed-1 research holdout and expands it to dirty entity
groups before selecting disjoint history and batch sets. Missing tokens are opt-in contract metadata.
Incompatible detectors are recorded and skipped, and the complete cell outputs are persisted for a
separate evaluator. The service never opens a clean pair or borrows financial evidence for a new source.

```bash
dqf scan config/scans/scan_published_jung_restaurant.yaml
python scripts/evaluate_real_error_benchmarks.py --phase all
```

The second command freezes nine dirty-only scans before evaluating published reference values. It injects
no errors. Results and limitations: [`real_error_benchmark_report.md`](real_error_benchmark_report.md).

## 2. Recommendation rule

For the dataset, baseline, budget and split scheme of the scan, the offline evidence gives the detector's
held-out utility (incremental recall over the existing controls on error cases and mechanisms that were not
used for selection) with a bootstrap interval over pilot replications.

- **ADOPT** – lower bound ≥ `min_gain` (0.05) **and** ≥ 3 independent pilot replications **and** the batch is
  not strongly shifted from the evaluation conditions (existing controls' alert rate on this batch ≤ 3× the rate
  on the untouched evaluation partitions) **and**, for binary methods, extra alerts ≤ the cap (50 per 1,000 rows).
- **DO_NOT_ADOPT** – upper bound < `min_gain`, or the burden cap is exceeded on this batch.
- **INSUFFICIENT_EVIDENCE** – everything else, including missing evidence, a single replication (temporal
  split) and shifted batches.

The rule deliberately says nothing about the batch's actual errors: there is no ground truth. A data engineer's
feedback can later turn findings into adjudicated precision, which is the only evidence about this batch.

## 3. Demonstrations run (see `docs/comprehensive_pilot_report.md` §7 for the numbers)

```bash
dqf scan config/scans/scan_bank_marketing_period13.yaml   # history: deliveries 1-9, new batch: delivery 13
dqf scan config/scans/scan_uci_credit_new_clients.yaml    # history: ID <= 15,000, new batch: ID > 25,000
dqf scan config/scans/scan_bank_marketing_rules_only.yaml # rules-only team, non-temporal extract (ADOPT case)
```

Outputs land in `results/runs/scans/<name>/` (git-ignored; copies of the three reports are committed under
`reports/scans/`).

## 4. Limits

- Findings are review candidates. Alerts on a real batch can be genuine source anomalies, legitimate change
  (e.g. new macro-economic regime in later Bank Marketing deliveries) or false alarms; the scan cannot tell.
- The recommendation transfers offline synthetic-error evidence to a real batch. The shift check catches only
  gross distribution change, measured by the existing controls.
- Feedback is optional annotation support, not a research instrument of this thesis.
