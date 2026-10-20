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
- **Evidence:** same-batch comparison (`results/qualification/cdc_fidelity.json`): ×10 on BILL_AMT1 recall 0.45 (re-impl.) vs 0.55 (original);
  PAY_0 untouched-cell flag rate 0.0% vs 9.6%, explained by the original's strict `<` set rule (reproduced:
  `strict_original` gives 20.2% untouched flags); original heuristic typing turns LIMIT_BAL and AGE into
  categoricals. At c = 0.999 with ~1000 calibration rows the categorical thresholds equal the calibration
  maximum: flag recall on PAY_0 swaps 0.00 for all five calibration seeds while ranking AUC is stable
  (0.81–0.89; `results/qualification/cdc_seed_variance.json`).
- **Consequence:** evaluate primarily at a fixed review budget (ranking), report own-threshold flags as
  secondary.
- **Update 2026-10-20 (qualification, dev data only):**
  - Ranking score changed to a normalised-residual conformal p-value (|y − median| / interval width): the CQR
    edge distance is inverted for zero-inflated, multimodal amounts (PAY_AMT1 ×10 AUC 0.18 → 0.98; mean over 17
    numeric cases 0.61 → 0.75). Flags still use CQR as in the original.
  - Tie-breaker below the p-value resolution added (many cells share the minimal p-value 1/(n_cal+1)).
  - Rare-label finding corrected: under Mondrian calibration with too few calibration examples, genuine rare
    labels are alerted at ≈1/(n+1) (69% for `marital = unknown`), not "never flagged".
  - Open: calibration size (≥ 1/(1−c) per label) or a lower confidence for flags; decide before freezing.

### D-16 · Stored detector scores and recomputation — final
- **Decision:** a run stores, per scenario, all flags, the target column and the top-k_max cells among cells
  *not* alerted by the full baseline and by the deterministic baseline; analyses recompute budgeted gains only
  for budgets ≤ the stored maximum and verify equality with the pipeline's own metrics (self-check).
- **Evidence:** the first version ranked over all cells (including baseline-alerted ones); recomputed gains at
  k = 50 were biased upwards (0.070 vs. 0.030). Caught by comparison and fixed; demos rerun.

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

### D-16 · BAF as an optional Kaggle dataset — provisional (licence)
- **Decision:** BAF Base is acquired through the official Kaggle client (`kaggle` optional extra,
  `scripts/download_baf.py`) into `data/raw/baf/`, hash-pinned on the extracted CSV and marked
  `optional: true`: default downloads and verification skip it, and no other component depends on it.
  This does not change D-03: BAF has no role until its licence is confirmed and it passes qualification.
- **Evidence:** download and validation on 2026-10-20 (`data/manifests/baf.acquisition.json`,
  `baf.validation.json`).
- **Risk:** licence NC-ND (datasheet) vs NC-SA (Kaggle) unresolved; under ND, injected copies may not be
  shared. Kaggle may re-compress the zip, so only the CSV hash is pinned.

### D-17 · Working branch for the comprehensive pilot — final
- **Decision:** `claude/exciting-ritchie-w1e31t` already contained the default branch
  `claude/eager-davinci-u8fn78` plus one commit (BAF/Kaggle), so it is the newest relevant code; the pilot is
  developed on it (the session's designated branch). Nothing is merged into the default branch.
- **Evidence:** `git log origin/claude/eager-davinci-u8fn78..HEAD` = 1 commit, reverse = 0.

### D-18 · Additional cell-level candidates — provisional
- **Decision:** qualify dBoost (re-implemented clean-room; GPL original run only as a child process for
  fidelity), LUCARIO's numerical/categorical constraints (partial clean-room re-implementation; the replication
  code has no licence and the paper text could not be read), and REIN's SD/IQR detectors (textbook rules; REIN
  code is "All Rights Reserved"). ZeroED is blocked (no licence, missing module, LLM requirement). Raha stays a
  separate few-label track.
- **Evidence:** `docs/detector_comparison.md`, `docs/sources/detector_benchmark_research_notes.md`; dBoost
  re-implementation agrees 100 % cell-by-cell with the original on Credit samples.
- **Risk:** LUCARIO-core is partial and unvalidated against the original; claims about LUCARIO are therefore
  limited to "LUCARIO-style numerical/categorical constraints".

### D-19 · Metrics for binary detectors — final
- **Decision:** no ranking score is constructed for binary-only methods. At a fixed review budget they are
  evaluated by the *expected* incremental recall of reviewing their extra flags in random order
  (hits × min(1, k / n_extra_flags)); scored methods additionally get ranked dR@k. Selection utility = ranked
  dR@k for scored, flag dR@k for binary methods.

### D-20 · Pilot partitions — provisional (supervisor review)
- **Decision:** the split-seed-1 test partition (20 %) is a reserved hold-out that the pilot never reads. The
  remaining design pool is re-split per pilot seed (11–15) into reference 50 % / selection 25 % / test 25 %
  (group-aware); Bank Marketing additionally gets one temporal split by `_period` (reference = periods 1–3,
  selection 4–9, test 10–26 within the pool).
- **Why:** the brief asks for separate reference / selection / test data and several independent splits;
  CLAUDE.md reserves test partitions and new split seeds for the confirmatory study. The nested design pool
  satisfies the first without consuming the seed-1 hold-out. Pilot seeds 11–15 are *nested re-splits of the
  design pool*, not confirmatory split seeds.
- **Risk:** confirmatory split seeds 2–5 over the full data will overlap the design pool; the confirmatory
  study should evaluate on the seed-1 hold-out (or a fresh seed scheme decided with supervisors).

### D-21 · Injection strategies — provisional
- **Decision:** strategy A (ECAR) and B (rotation over ECAR + contextual + realistic batch-block mechanisms)
  share cases, rates, rows and scenario counts; a held-out family of cases and mechanism settings is used by
  neither (`docs/injection_strategies.md`).

### D-22 · Detector configurations — final for the pilot
- **Decision:** published defaults / suggested values only, fixed before any pilot result
  (`docs/detector_comparison.md` §3). No tuning on pilot results.

### D-23 · Decision rule — provisional
- **Decision:** ADOPT if the lower 95 % cluster-bootstrap bound (over error cases) of the selected detector's
  utility on the selection scenarios ≥ 0.05; DO_NOT_ADOPT if the upper bound < 0.05; otherwise
  INSUFFICIENT_EVIDENCE. The same rule on the test sets gives the "target decision" for agreement.

### D-24 · Untouched-data alerts — final
- **Decision:** alerts on untouched cells are reported as alert burden per 1,000 rows; precision w.r.t. injected
  cells is labelled a lower bound and never called false-positive rate.

### D-25 · BAF excluded from the pilot — provisional (licence)
- **Decision:** BAF acquisition is verified (Kaggle token available on 2026-10-20) but BAF is excluded from all
  pilot results: contradictory non-commercial licences (NC-SA vs NC-ND), commercial internship context,
  CTGAN-synthetic data without DQ labels (`docs/dataset_overview.md`).

### D-26 · Two operating modes for scored detectors — provisional (qualification-informed)
- **Decision:** a detector that publishes a ranking contributes two candidates to selection: its top-k ranked
  cells (`cdc`) and its own flags reviewed within the budget (`cdc[flags]`). Binary methods have the flag mode
  only. Decided after the qualification round (pilot seed 11, selection partition), where CDC's own flags
  outperformed its ranking at k = 25 against the rules-only baseline (0.034 vs 0.019); no test-set result was
  looked at. Both are legitimate uses of the same output, so neither mode is privileged.

### D-27 · Ranking score for dBoost's Gaussian model — provisional
- **Decision:** dBoost (Gaussian model) returns its own test statistic max_f |x_f − μ_f| / σ_f as a score; thresholding
  at t reproduces the published flags exactly (`test_gaussian_score_reproduces_the_published_flag_exactly`).
  Ranking by it is an extension of the published method, made because the brief's priority addendum asks for
  scored label-free detectors; the histogram models stay binary. LUCARIO-core stays binary (no single statistic
  across its constraint types).

### D-28 · Primary analysis — final for the pilot (priority addendum, 2026-10-20)
- **Decision:** primary = financial tables (UCI Credit, Bank Marketing random splits, Bank Marketing consecutive
  deliveries; GMSC blocked), detectors CDC, dBoost-Gaussian (typed) and dBoost-Gaussian (text mode), ranked dR@k.
  Raha, ZeroED, Isolation Forest, BAF, LUCARIO-core, dBoost histogram, SD, IQR and the injection-strategy comparison
  are secondary; external benchmarks are qualified and reported only.
- **Main question:** increment over each baseline, and baseline effect vs detector spread.
- The first full run (binary dBoost, 5 finished replications) was superseded by a complete rerun with identical
  scenarios; four Bank replications of the rerun were killed by the memory limit (four parallel processes) and
  re-run; no result was selected on outcome.
