# Decision log

Format: decision · alternatives · evidence · trade-offs · open risks · status (**final** = not expected to
change without new evidence; **provisional** = to be confirmed with supervisors or by the confirmatory
protocol). Earlier exploratory decisions (pilots 1–4, `oosterbaanvu/masterthesis3`) are referenced, not
copied.

---

### D-01 · Personal and organisational information in the repository — final
- **Decision:** the industry contact is referred to by role ("industry contact in a Rabobank-related data
  department"), not by name. Described practices are presented as one department's practice, not as bank
  policy. No bank data, client names or recipes are stored.
- **Evidence:** project brief; organisation guidelines on confidentiality.
- **Risk:** none.

### D-02 · Runtime and dependency isolation — final
- **Decision:** main environment Python 3.12 with pinned lockfile (`uv.lock`; tab_err 0.2.1 requires
  Python < 3.13; dbt Core 1.12.6 + dbt-duckdb 1.11.0; DuckDB 1.5). Original detectors run in isolated
  Python 3.9 environments (`envs/cdc_aistats`, `envs/raha`) and exchange Parquet/CSV + JSON with the
  framework through subprocess adapters.
- **Alternatives:** one environment (impossible: AutoGluon 0.8.2 and Raha pin old numpy/pandas/sklearn);
  Docker images (heavier; can be added later for CI of the isolated envs).
- **Evidence:** both isolated envs installed and executed (`method_compatibility.md`).
- **Note:** dbt Core v1 is used deliberately (Apache-2.0, local, DuckDB adapter); dbt's newer v2/Fusion engine
  was not evaluated.

### D-03 · Dataset roles — provisional (supervisor review)
- **Decision:** UCI Credit = R1 primary; UCI Bank Marketing (`bank-additional-full`) = R1 secondary and
  configuration-only onboarding demo (replaces BAF); Flights = R2 only for transductive detectors; Tax =
  R3 and out-of-generator probe; BAF remains BLOCKED; Stock, SEC amendments, AddressTable = not selected.
- **Alternatives:** BAF (blocked: login + NC licence); German Credit (1,000 rows, too small); TableEG,
  AuditBench, SGCD, SEC-FinTables (rejected in pilots).
- **Evidence:** `dataset_qualification.md`.
- **Trade-off:** Bank Marketing is marketing rather than transaction data, but it is financial-domain,
  openly licensed, and has real monthly delivery periods.
- **Risk:** two datasets limit dataset-level generalisation; decisions across datasets are compared
  qualitatively.

### D-04 · Contract-first conventional controls with evidence status — final
- **Decision:** every rule lives in a versioned YAML contract with `status` verified / provisional /
  unsupported and an evidence sentence; dbt models/tests are generated from the contract and committed; a
  test fails if they drift. Unsupported rules are recorded but not executed.
- **Examples:** EDUCATION documented domain (345 untouched violations) and `BILL_AMT1 ≤ 1.5 × LIMIT_BAL`
  (undocumented multiplier) are `unsupported`; Bank `pdays = 999 ⇒ previous = 0` contradicted by 4,110 rows.
- **Why:** prevents straw-man baselines and post-hoc rule tuning; makes the baseline auditable.

### D-05 · Statistical controls fitted on reference data only — provisional
- **Decision:** univariate quantile envelopes (0.05%/99.95%), ratio and month-over-month envelopes, payment
  vs. statement envelopes and rare-category checks, all fitted on the reference partition and executed as
  dbt tests that read the fitted bounds from a DuckDB table.
- **Trade-off:** thresholds are fixed a priori (≈0.1% expected alert rate per check) rather than tuned; a
  stronger and a weaker baseline variant should be reported as sensitivity.

### D-06 · Injection: operations separated from mechanisms; only real changes count — final
- **Decision:** see `error_injection_validation.md`. tab_err is used for WrongUnit (non-zero cells only),
  MissingValue, Outlier, its mechanisms, and – as the explicitly named `code_remap` – CategorySwap.
  Per-cell category swaps, sign flips, digit transpositions, period shifts, rounding and plausible
  substitutions are small custom injectors with tests.
- **Evidence:** tab_err mask includes unchanged cells; CategorySwap maps per category under pandas 2.3;
  frequency weighing not reproducible; AddDelta default immaterial (all reproduced in
  `tests/test_tab_err_behaviour.py`).
- **Upstream:** worth reporting to the tab_err maintainers (not done; external action requires the user's
  consent).

### D-07 · Mechanism families: tab_err window + soft dose-controlled — provisional
- **Decision:** keep both. Soft mechanisms sample with probability ∝ exp(strength · centred rank) (or a
  segment indicator); strength 0 = ECAR. EAR conditioning columns are real attributes with a stated
  rationale; no synthetic `source_system`.
- **Evidence:** tab_err window position makes scenario difficulty a seed effect (share outside envelope
  0.01–0.51 across three seeds under tab_err EAR); tie-order artefact on binary conditioning columns.
- **Open:** choose the strength grid with a power analysis.

### D-08 · Learned detector 1: CDC — provisional
- **Decision:** primary implementation = re-implementation with scikit-learn HistGradientBoosting
  (`cdc_hgb`), contract-based typing, inclusive conformal sets, per-column calibration split, conformal
  p-values for ranking. The original implementation (AutoGluon 0.8.2, RF+XT, without FASTAI) is kept as a
  fidelity reference.
- **Evidence:** same-batch comparison: ×10 on BILL_AMT1 recall 0.48 (re-impl.) vs 0.55 (original);
  PAY_0 untouched-cell flag rate 0.0% vs 9.6%, explained by the original's strict `<` set rule (reproduced:
  `strict_original` gives 12.4% untouched flags); original heuristic typing turns LIMIT_BAL and AGE into
  categoricals. At c = 0.999 with ~1000 calibration rows the categorical thresholds equal the calibration
  maximum: flag recall on PAY_0 swaps 0.00–0.09 across five seeds while ranking AUC is stable (0.88–0.93).
- **Consequence:** evaluate primarily at a fixed review budget (ranking), report own-threshold flags as
  secondary.

### D-09 · Raha excluded from the controlled comparison — final for the controlled study
- **Decision:** Raha is used only on Flights (real errors).
- **Evidence:** Flights F1 0.769 (environment works); on UCI Credit with 5% errors in one column the 20
  labelled tuples contained **0** erroneous cells in both scenarios → no detections; at 20% only 2
  labelled error cells and recall 0.03. Also: different supervision (labels from the batch under test)
  and transductive setting; fixed TMPDIR collision bug in the adapter (concurrent Raha jobs overwrote each
  other's temp files).

### D-10 · Learned detector 2: Isolation Forest at record level — provisional
- **Decision:** add a row-level Isolation Forest (joint outlierness; different inductive bias from CDC),
  evaluated only with record-level metrics; nothing is mapped down to cells.
- **Alternatives:** autoencoder (higher implementation and tuning risk), Raha (D-09), PyOD ECOD per column
  (univariate, overlaps with statistical controls).

### D-11 · Evaluation metrics and decision rule — provisional
- **Decision:** primary metric ΔR@k: share of injected cells found by the top-k learned-detector cells per
  1,000 rows that the baseline did not already implicate; secondary: recall of baseline tiers, own-flag
  increment, extra alerts on untouched cells (reported as *burden*, never as false positives), AUC on the
  target column, record-level variants. Decision: ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE from the
  bootstrap CI of ΔR@10 vs. a minimum gain (0.05) and a burden cap.
- **Open:** gain threshold and budget should be set with the industry contact (review capacity) before the
  confirmatory run; error rate per scenario 1% in demos (5% caps ΔR@10 at 0.2).

### D-12 · Partition discipline — final
- **Decision:** all qualification and design choices so far used split seed 1, `dev` partition. Test
  partitions are reserved for the confirmatory protocol; confirmatory runs use new split seeds.

### D-13 · Research direction — provisional (supervisor review)
- **Decision:** keep the original idea (reliability of adoption decisions) as the main question, with the
  incremental-value measurement as its core and the mutation-analysis view as framing of the artefact;
  decisions are taken against the baseline and validated on held-out conditions.
- **Evidence:** `research_gap.md`, `research_directions.md`, demo results.

### D-14 · Bank Marketing temporal structure — final
- **Decision:** derive `_period` (26 contiguous runs of the monthly indicator) as delivery batch; use for
  temporal splits and batch-level EAR scenarios; never as a detector feature.

### D-15 · External validity claims — provisional
- **Decision:** no claim of synthetic-to-real transfer for CDC. Flights cannot test CDC (chance-level AUC
  under a leakage-free split; errors are inter-source conflicts). An out-of-generator check on BART errors
  in Tax is reported as a bounded validity check (`method_compatibility.md` §5).
