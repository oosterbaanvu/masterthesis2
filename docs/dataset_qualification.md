# Dataset qualification

Status: 2026-10-20. Measurements marked **[ours]** were produced in this repository
(`scripts/download_datasets.py`, `scripts/verify_datasets.py`, `scripts/validate_injection.py`,
`scripts/probe_*.py`, `dqf controls check`); items marked **[probe]** come from a bounded dataset search done
in this session (scratch inspection, not part of the repository pipeline); **UNVERIFIED** means not confirmed.
Licence statements are recorded as found; they are **not legal advice** and need confirmation by the
supervisor or the responsible officer.

Research roles:

- **R1 – controlled financial experiments** (injected errors; labels by construction)
- **R2 – independent existing-error evaluation** (published dirty/clean pairs)
- **R3 – engineering / scalability demonstration**

## 1. Summary

| Dataset | Acquired | Role | Verdict | Main reason |
|---|---|---|---|---|
| UCI Default of Credit Card Clients | yes, hash-pinned | R1 primary | **QUALIFIED** | Financial, regular, CC BY 4.0, 30k rows, documented semantics (with known gaps), passes contract, dbt, injection and detector gates |
| UCI Bank Marketing (bank-additional-full) | yes, hash-pinned | R1 secondary, R3 | **QUALIFIED** | Financial domain, CC BY 4.0, 41k rows, categorical-rich, documented cross-field semantics, 26 monthly delivery periods (temporal split possible) |
| Raha Flights | yes, hash-pinned (commit 7be1334b) | R2 for transductive detectors (Raha) | **CONDITIONAL** | Real errors, but inter-source conflicts: CDC is at chance level on it under a leakage-free split; ~7% of error labels rest on imputed truth |
| Raha Tax | yes, hash-pinned | R3; out-of-generator probe | **CONDITIONAL** | 97.6% of published "errors" are formatting artefacts; ~2,000 substantive BART errors usable after typing |
| Raha Beers | yes, hash-pinned | – | **NOT SELECTED** | Errors are almost all formatting/representation |
| Raha Hospital | yes, hash-pinned | sanity only | **NOT SELECTED** | 508/509 errors are synthetic 'x' substitutions |
| Feedzai BAF Base | no | – | **BLOCKED** | Kaggle login required; licence NC-ND (datasheet) vs NC-SA (Kaggle) unresolved; fraud label ≠ DQ label |
| Li et al. Stock (deep-web) | probe only | R2 exploratory | **NOT SELECTED** | Financial and real, but truth = 5-site majority vote; error rate 33%→11% depending on tolerance rule |
| SEC Financial Statement Data Sets (amendments) | no | future work | **NOT SELECTED** | Real issuer corrections possible but not packaged; legitimate restatements, alignment and sparsity problems |
| AddressTable (Clean Me If You Can, 2026) | probe sample only | possible R2/R3 | **NOT SELECTED (now)** | Real errors at scale but string-only, standardisation-dominated, 7.3 GB, licence ambiguity |
| CleanML Company/University/Credit; ZeroED Billionaire; TableEG Credit/Marketing | probe / earlier pilots | – | **REJECTED** | Trivial or no ground truth; synthetic; or labels are imputations (earlier pilot) |

**Key negative result.** No public *financial* dirty/clean benchmark with real errors and independently
verified cell-level corrections was found (bounded, literature-driven search; consistent with the earlier
pilots). This is a limitation to state in the thesis, not a gap to fill with a weak benchmark.

**Common evaluation basis across the primary financial datasets.** Both R1 datasets are processed by the
same contract → dbt → injection → detector → evaluation path with the same metrics, split logic and
scenario catalog structure (verified by the two demo runs in `reports/`). Their error catalogs differ
because their semantics differ (amounts and status codes vs. client/contact codes and macro indicators);
comparisons across datasets are therefore made on *decisions and directions of effects*, not on raw
recall levels.

## 2. Acquisition and integrity (all automatic datasets)

`python scripts/download_datasets.py && python scripts/verify_datasets.py` – downloads from the
authoritative URL, checks the pinned SHA-256 of the archive **and** of every extracted member (also from
nested zips), writes files read-only, records a manifest in `data/manifests/`, and verifies shape. A
truncated download or hash mismatch aborts without leaving a partial file (tested in
`tests/test_acquisition.py`). Status on 2026-10-19 **[ours]**: all six automatic datasets VERIFIED; BAF
BLOCKED (manual).

The UCI Credit archive hash (`56c885f8…727602`) equals the archive used in the earlier pilot repository,
so the earlier results refer to the same bytes **[ours]**.

## 3. UCI Default of Credit Card Clients (R1 primary)

- **Source:** https://archive.ics.uci.edu/dataset/350, DOI 10.24432/C55S3H; Yeh & Lien (2009), Expert
  Systems with Applications 36(2). Static archive
  `https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip`.
- **Licence:** CC BY 4.0 – page text quoted in the probe: "This dataset is licensed under a Creative
  Commons Attribution 4.0 International (CC BY 4.0) license…" **[probe]**.
- **Shape [ours]:** 30,000 × 25, all integer, no nulls; ID unique 1..30,000; 70 rows belong to exact
  duplicate groups when ID is ignored (35 pairs) – kept in one partition by the group-aware split.
- **Semantics vs data [ours]:** documented domains are contradicted by the published data: EDUCATION
  0/5/6 (345 rows), MARRIAGE 0 (54 rows), PAY_x −2 and 0 (the majority of PAY cells); BILL_AMT negative in
  2–2.3% of rows (credit balances); LIMIT_BAL not a multiple of 10,000 in 3 rows. These are treated as
  *unknown status*, never as clean ground truth, and drive rule statuses in
  `config/contracts/uci_credit.yaml` (documented domain → `unsupported`; observed domain → `provisional`).
- **Conventional controls on the untouched table [ours, `dqf controls check uci_credit`]:** 81 dbt tests;
  deterministic rules pass except the provisional granularity rule (3 rows); statistical controls alert
  ~0.1% per check by construction (≈47 implicated cells per 1,000 rows over all checks).
- **Injection eligibility [ours]:** 366 scenario variants validated (real change, no side effects,
  reproducible, semantically correct, intended = realised count). Note: ×10 on BILL_AMT1 leaves 83% of
  injected values inside the reference 0.05–99.95% envelope; many realistic errors are *not* trivially
  out of range.
- **Detector fit:** CDC CONDITIONAL (with ~1,000 calibration rows most categorical labels are below the 999
  examples that c = 0.999 needs, so flags on categorical columns are unreliable; ranking works); Isolation Forest PASS
  (row level). See `method_compatibility.md`.
- **Risks:** no time axis between rows (random splits only); a single 2005 snapshot; heavy-tailed amounts.
  Bias risk: scale errors favour statistical controls, code errors favour domain rules – the catalog
  therefore mixes error families and reports them separately.

## 4. UCI Bank Marketing, `bank-additional-full.csv` (R1 secondary, R3)

- **Source:** https://archive.ics.uci.edu/dataset/222, DOI 10.24432/C5K306; Moro, Cortez & Rita (2014),
  Decision Support Systems 62. Static archive `…/static/public/222/bank+marketing.zip` with nested zips;
  members pinned individually.
- **Licence:** CC BY 4.0 (UCI page) **[probe]**; names file: "publicly available for research", citation
  requested.
- **Shape [ours]:** 41,188 × 21; 10 categorical, 10 numeric analysed columns (target `y` excluded);
  24 rows in exact duplicate groups; `unknown` is the documented missing code; `pdays = 999` sentinel.
- **Temporal structure [ours]:** the file is ordered by date (May 2008–Nov 2010) without a year column.
  The monthly indicator `cons.price.idx` forms **26 contiguous runs**, and `cons.price.idx → month` and
  `cons.price.idx → cons.conf.idx` are exact functions in the data. We derive `_period` (1..26) as a
  delivery-batch identifier (documented in the contract; not used as a detector feature). This gives the
  "onboard a new monthly delivery" scenario that BAF was meant to provide.
- **Documented cross-field semantics [ours]:** `(previous = 0) ⇔ (poutcome = 'nonexistent')` and
  `pdays < 999 ⇒ previous > 0` hold with 0 violations (enforced, `verified`); the literal reading
  "999 = not previously contacted" is contradicted by 4,110 rows with `previous > 0` (recorded as
  `unsupported`, not enforced).
- **Injection [ours]:** 216 scenario variants validated. Note the EAR artefact of tab_err on the binary
  `contact` column (`error_injection_validation.md` §4).
- **Risks:** `duration` leaks the target (irrelevant for detection, documented); the later periods are
  small (128–770 rows), so temporal test batches are unbalanced; near-perfect FDs of the macro columns
  favour constraint-based checks on injected violations there (reported per column).

## 5. Raha Flights (R2, conditional)

- **Source:** BigDaMa/raha commit `7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c` (files unchanged since 2019);
  origin Li, Dong, Lyons, Meng & Srivastava, "Truth Finding on the Deep Web", PVLDB 6(2), 2012: 38 sources,
  100 flights, gold standard from the airlines' own websites. Repository licence Apache-2.0; no separate
  data licence (research use customary; UNVERIFIED).
- **Measured [ours]:** 2,376 × 7, aligned on `tuple_id`; 4,920 differing cells (29.6%) in the four time
  columns, 1,904 rows. Error rate per source ranges from 0% to 100% (e.g. `CO` 0/19 rows, `flytecomm`
  84.5% of cells) – a *real* attribute-dependent (EAR-like) error mechanism, conditioned on `src`.
- **Label caveat [probe]:** against the original gold-standard file, 14 of 400 flight×attribute truth
  values are empty and were filled with the *scheduled* time in Raha's clean.csv, affecting 353 cells
  (~7% of the errors).
- **After typing the times to minutes [ours, `scripts/probe_flights_typed.py`]:** 2,312 errors are
  missing values in the dirty file (caught by `not_null`), 90 are unparseable strings (caught by format
  checks), 322 are representation-only (same time, different notation) and **2,196 are real value
  conflicts**.
- **Detector compatibility [ours]:** Raha **PASS** (P = 0.883, R = 0.681, F1 = 0.769, one seed, 20 labelled
  tuples). CDC on the typed table with a leakage-free split by flight: **AUC ≈ 0.5 on real value
  errors** (chance), because the errors are disagreements *between* rows for the same flight while CDC
  models dependencies *within* a row and cannot know unseen flights. A split that puts the same flight in
  reference and test would leak the clean truth. (Probe re-run with the final ranking score: AUC 0.47–0.55;
  0.18 for `sched_dep_time`, which has only 3 value errors in the test flights.) **Verdict:** valid R2 benchmark for transductive,
  redundancy-exploiting detectors; **not** a valid external test of CDC.

## 6. Raha Tax (R3; out-of-generator probe)

- **Origin:** BART-generated synthetic tax records (Baran, PVLDB 2020: "Tax is a synthetic dataset from the
  BART repository"); 200,000 × 15.
- **Measured [ours]:** 121,219 differing cells (4.04%), of which **118,253 (97.6%) are formatting
  artefacts** of the clean file: `rate` '0.0' vs '0' (87,342) and ZIP codes whose leading zero was dropped
  in clean.csv (30,911; e.g. dirty `01907` – the correct Swampscott, MA code – vs clean `1907`). After
  removing these and doubled apostrophes, **2,000 substantive generator errors** remain in round blocks of
  200/400/600 (state, zip, marital_status, has_child, exemptions, city).
- **Use:** R3 (200k rows; scalability of dbt + detectors) and an *out-of-generator* check: CDC trained on
  clean rows and scored on BART errors vs. on our injected errors in the same columns
  (`scripts/probe_tax_bart.py`, `results/qualification/tax_bart_probe.json`; see
  `method_compatibility.md` §5 for the outcome).
- **Not** evidence about real errors.

## 7. Other candidates (not selected)

- **Beers [ours]:** 4,362 differences (16.5%), all rows affected; almost entirely representation (units
  "12.0 oz", "%", "N/A", state appended to city). A format/standardisation benchmark, not a value-error
  benchmark.
- **Hospital [ours]:** 509 differences; 508 are 'x' character substitutions (synthetic).
- **Rayyan, Movies [probe]:** small real/format errors in bibliographic and movie data; not needed.
- **Feedzai BAF [probe]:** Kaggle metadata states CC BY-NC-SA 4.0, the publisher datasheet CC BY-NC-ND 4.0;
  download requires login (not bypassed). Both are non-commercial; ND would forbid sharing injected
  copies. Remains BLOCKED; Bank Marketing covers the monthly-batch role.
- **Li et al. Stock [probe]:** the only financial real-conflict candidate; truth is a 5-site majority vote
  with partial coverage and rounding; mismatch rate 33.1% exact, 16.4% at ±1%, 10.6% at ±5%; no licence
  statement. Labels would be rule-defined – exploratory only.
- **SEC Financial Statement Data Sets [probe]:** `prevrpt` + 10-K/A amendments give issuer corrections, but
  many amendments change no numbers, changes can be legitimate restatements, tags/segments change, and
  the long format is sparse. Future work.
- **AddressTable (Ahmadi et al., arXiv 2606.31983) [probe]:** real web-extracted addresses with
  geocoder-derived truth; 48.9% of cells differ in a 100k sample, mostly standardisation; licence
  CC BY 4.0 (Zenodo) vs ODbL (README). Possible later R2/R3 for string-level detectors.

## 8. Role decisions

| Role | Dataset(s) | Notes |
|---|---|---|
| R1 primary | UCI Credit | random group-aware 60/20/20 split per split seed |
| R1 secondary | UCI Bank Marketing | random split (primary) and temporal split by `_period` (robustness) |
| R2 | Raha Flights (Raha only); Tax BART errors (out-of-generator, CDC) | reported as bounded validity checks, never as estimates of real-error performance in finance |
| R3 | Bank Marketing (configuration-only onboarding), Tax (scale) | |

Decisions are logged in `decision_log.md` (D-03, D-14, D-15).
