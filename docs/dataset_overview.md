# Dataset overview and reproducible acquisition

Status: 2026-10-20. The historical pilot verified seven datasets (GMSC remained blocked). The published
benchmark extension below additionally downloaded and verified Rayyan, Restaurant and optional Cars in the
current cloud environment; full audit: [`published_benchmark_datasets.md`](published_benchmark_datasets.md).
The subsequent dirty-only service evaluation is in [`real_error_benchmark_report.md`](real_error_benchmark_report.md):
all three sources run, but the synthetic missingness variants show zero detector increment over completeness
controls and Rayyan labels remain uncertain. The rows below retain acquisition-stage suitability notes.
The status listing below records the earlier pilot container, not current-machine availability.
Licence notes record what the sources state;
they are **not legal advice** and must be confirmed by the supervisor / responsible officer before
publication. Detailed qualification evidence: `docs/dataset_qualification.md`.

## Commands (new environment)

```bash
uv sync --frozen --extra dev                 # pinned environment
python scripts/download_datasets.py          # 8 required public datasets: UCI (2), Raha (5), Restaurant (1)
python scripts/download_datasets.py jung_cars # optional numeric-format / missing-value benchmark
python scripts/dataset_status.py             # what is present / verified; writes data/local_manifest.json (git-ignored)
dqf datasets status                          # same, via the CLI
# optional, only with a Kaggle account and after accepting the dataset terms on kaggle.com:
uv sync --frozen --extra dev --extra kaggle
export KAGGLE_API_TOKEN=...                  # never commit it; ~/.kaggle/access_token also works
python scripts/download_baf.py --report data/manifests/baf.validation.json
```

Status output in this container (2026-10-20):

```
dataset              status    files  optional shape                                    authentication
uci_credit           VERIFIED  1/1    no       30000 rows x 25 cols                     none (public URL)
uci_bank_marketing   VERIFIED  3/3    no       41188 rows x 21 cols                     none (public URL)
raha_flights         VERIFIED  2/2    no       dirty (2376, 7), clean (2376, 7)         none (public URL)
raha_tax             VERIFIED  2/2    no       dirty (200000, 15), clean (200000, 15)   none (public URL)
raha_beers           VERIFIED  2/2    no       dirty (2410, 11), clean (2410, 11)       none (public URL)
raha_hospital        VERIFIED  2/2    no       dirty (1000, 20), clean (1000, 20)       none (public URL)
baf                  VERIFIED  1/1    yes      1000000 rows x 32 cols                   Kaggle account + API token
    credentials: KAGGLE_API_TOKEN environment variable
```

Guarantees (tested in `tests/test_acquisition.py`, `tests/test_dataset_status.py`, `tests/test_repo_hygiene.py`):
pinned hashes for archives *and* extracted members; truncated or mismatching downloads leave no file; raw files
are read-only; optional datasets never block the pipeline; credentials are reported by *source* only, never by
value; no raw data, secrets or large files are tracked in git.

## Overview

| Dataset (key) | Source and scientific reference | Licence / restrictions | Availability | Version and SHA-256 (analysed file) | Rows × cols | Controlled injection | Independent error validation | Engineering demo | Ground truth | Known quality issues | Detector suitability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UCI Default of Credit Card Clients (`uci_credit`) | UCI ML Repository id 350, DOI 10.24432/C55S3H; Yeh & Lien, *Expert Syst. Appl.* 36(2), 2009 | CC BY 4.0 (UCI page) — attribution | public, static archive | UCI static zip `56c885f8…727602`; `.xls` `30c6be3a…700933` | 30,000 × 25 (23 analysed + ID + target) | **yes (primary)** | no (no error labels) | yes | none; injected errors only (labels by construction) | undocumented codes EDUCATION 0/5/6, MARRIAGE 0, PAY −2/0; 35 duplicate pairs; negative bills; target excluded | CDC CONDITIONAL (rare labels), dBoost PASS (binary, high burden), LUCARIO-core PASS (provisional), SD/IQR PASS (numeric only), IF PASS (row) |
| UCI Bank Marketing, bank-additional-full (`uci_bank_marketing`) | UCI id 222, DOI 10.24432/C5K306; Moro, Cortez & Rita, *Decis. Support Syst.* 62, 2014 | CC BY 4.0 (UCI page); names file asks for citation | public, nested zip | zip `e0bf5f5d…efbeb4`; csv `74adfc57…afb4d8` | 41,188 × 21 (20 analysed + target) | **yes (secondary)** + temporal split by derived `_period` (26 months) | no | **yes** (monthly deliveries) | none; injected errors only | `unknown` = documented missing code; `pdays = 999` sentinel contradicted by 4,110 rows; `duration` leaks target; small late periods | CDC CONDITIONAL (`marital = unknown`), dBoost PASS (original crashes on float columns, see method doc), others PASS |
| Raha Flights (`raha_flights`) | BigDaMa/raha @7be1334b; data from Li, Dong, Lyons, Meng & Srivastava, *PVLDB* 6(2), 2012 | repository Apache-2.0; no separate data licence (UNVERIFIED) | raw GitHub, pinned commit | dirty `1b5c1afa…ecd46`, clean `0acfcfd8…dfdf3b` | 2,376 × 7 | no | **conditional**: real inter-source conflicts, ~7 % imputed truth | no | real errors vs. airline websites (gold standard), partly imputed | 29.6 % of cells differ; missing/representation errors dominate | Raha PASS (transductive, labels); CDC INCOMPATIBLE (chance-level, cross-row conflicts) |
| Raha Tax (`raha_tax`) | BigDaMa/raha copy of BART-generated synthetic tax data (Baran, PVLDB 2020) | repository Apache-2.0 | raw GitHub | dirty `8dd3429e…b973`, clean `20129092…87b0` | 200,000 × 15 | no | **weak**: synthetic BART errors, 97.6 % formatting artefacts | yes (scale) | synthetic (BART), cell diff after removing artefacts | 118,253 formatting differences (`0.0` vs `0`, dropped leading zeros) | CDC/dBoost reach a ceiling on BART errors (weak evidence) |
| Raha Beers (`raha_beers`) | BigDaMa/raha copy; manually cleaned craft-beer listings (Mahdavi et al., SIGMOD 2019) | repository Apache-2.0 | raw GitHub | dirty `7110bf49…0f68`, clean `373227df…93de` | 2,410 × 11 | no | not for value errors: almost all representation/format | no | manual cleaning | units in values (`12.0 oz`, `%`), `N/A` | string/pattern detectors only |
| Raha Hospital (`raha_hospital`) | BigDaMa/raha copy | repository Apache-2.0 | raw GitHub | dirty `dbc5575b…25ac`, clean `ea3ee449…248b4b` | 1,000 × 20 | no | no: 508/509 errors synthetic `x` substitutions | sanity only | synthetic | — | typo/pattern detectors only |
| Give Me Some Credit, training file (`gmsc`) — **optional, BLOCKED** | Kaggle competition `GiveMeSomeCredit` (2011), https://www.kaggle.com/competitions/GiveMeSomeCredit | **unresolved**: Kaggle competition rules (must be accepted per account); no open data licence shown by the API | Kaggle login **and accepted competition rules**; the API lists `cs-training.csv` (7,564,965 bytes) but returns HTTP 403 on download for the current account (2026-10-20) | not yet pinned (`pin_pending: true`; first download reports the hash to pin) | 150,000 × 12 expected (index, target, 10 attributes) – UNVERIFIED until download | intended (R1, third financial table) | no | no | none | known from the CleanML copy (not used): MonthlyIncome missing in 19.8 %, NumberOfDependents 2.6 %; extreme DebtRatio / utilisation values | not evaluated (no data) |
| Feedzai BAF Base (`baf`) — **optional** | Kaggle `sgpjesus/bank-account-fraud-dataset-neurips-2022`; Jesus et al., NeurIPS Datasets & Benchmarks 2022 (arXiv 2211.13358) | **unresolved and restrictive**: Kaggle metadata CC BY-NC-SA 4.0 (re-checked 2026-10-20 via API); publisher datasheet (A44) CC BY-NC-ND 4.0; non-commercial in both | Kaggle login + accepted terms; `KAGGLE_API_TOKEN` | `Base.csv` `7bf10a37…f9b809` (extracted file; Kaggle zip not stable) | 1,000,000 × 32 | technically yes, **not used** | no (CTGAN-generated synthetic data, fraud label ≠ DQ label) | possible (scale, monthly `month`) | none | negative sentinels for missing values (71 % in `prev_address_months_count`) | not evaluated |
| Raha Rayyan (`raha_rayyan`) | BigDaMa/raha @7be1334b; Mahdavi et al., SIGMOD 2019 | repository Apache-2.0; upstream data terms unconfirmed | public, downloaded and verified | dirty `7e25e6db…1d174`, clean `23159f43…4673f` | 1,000 × 11 | not run | conditional: reference/date/encoding adjudication needed | acquisition only | published owner-corrected reference, not independently adjudicated | 948 candidate cell differences, including 722 dates and 70 empty-to-`-1` sentinel changes | not evaluated; text-heavy |
| Jung Restaurant (`jung_restaurant`) | calgo-lab/error-paper @b8950a91, restaurant_3_1; Jung et al., DOI 10.1145/3774914 | no top-level data licence; upstream rights unconfirmed | public, downloaded and verified | dirty `13285f24…91760`, clean `4273d92f…1d953` | 864 × 6 | published variant only | synthetic `tab_err`, not a natural-error holdout | acquisition only | 155 dirty `?` candidates; 30 affect the entity label `class` | missing values in city/phone/type/class; exclude class from detector features | not evaluated |
| Jung Cars (`jung_cars`) — **optional** | calgo-lab/error-paper @b8950a91, cars_3_1; Jung et al. | no top-level data licence; upstream rights unconfirmed | public, downloaded and verified | dirty `c803f870…9ff7`, clean `29d0feff…553b` | 406 × 9 | published variant only | synthetic missing values; numeric-format caveat | format stress test only | 820 raw differences, 710 numeric equivalents, 110 missing-value candidates | raw-string labels inflate numerical errors | not evaluated |

**Give Me Some Credit — what is needed.** Log in on kaggle.com with the account behind `KAGGLE_API_TOKEN`,
accept the rules at https://www.kaggle.com/competitions/GiveMeSomeCredit/rules, then run
`python scripts/download_datasets.py gmsc`; pin the reported SHA-256 in `config/datasets.yaml`, write
`config/contracts/gmsc.yaml` from the competition's data dictionary and the untouched data, and run
`python scripts/run_pilot.py config/pilot/pilot_gmsc.yaml` (to be created from the Credit config). Copies of
GMSC in third-party repositories (CleanML, TableEG) are **not** used as a substitute (CLAUDE.md: never substitute a
dataset). The GMSC data dictionary could not be obtained from a primary source either.

**TableEG Credit provenance** (`docs/sources/tableeg_gmsc_provenance.md`): TableEG's `dirty.csv` equals CleanML's
`Credit/raw/raw.csv` cell for cell (VERIFIED); CleanML states the source is Kaggle GiveMeSomeCredit (VERIFIED as a
statement), and schema, row count and missing-value counts match GMSC (PROBABLE; no byte comparison with the
Kaggle original possible). TableEG's `clean.csv` is CleanML's **HoloClean output** (missing-value imputation and
outlier repair; e.g. 17,435 imputed incomes all equal 88.44), so its labels are algorithmic repairs, not verified
corrections, contrary to the paper's "manually annotated" description. Verdict: TableEG Credit is a derivative of
GMSC with **imputed, not independent, ground truth** — rejected as a validation benchmark; no link to UCI Credit.

Not registered (qualified or rejected without download; details in `dataset_qualification.md` and
`docs/independent_validation.md`): REIN benchmark datasets (no data licence, ResearchGate-only), Auto-Test ST/RT-Bench
(single-column value lists), AddressTable / Clean Me If You Can (string addresses, ODbL ground truth), TableEG
Credit (see above), Li et al. Stock, SEC amendments.

## Why BAF is acquired but not used

The acquisition path works (official Kaggle client, hash-pinned, read-only, never committed), but the licence
conditions are contradictory (NC-SA vs NC-ND) and in both cases *non-commercial*. The thesis is carried out in
an internship at a commercial consultancy; whether that counts as non-commercial research has to be decided by
the university / Avanade, not by this pilot. The data are CTGAN-synthetic and carry no data-quality labels, so
BAF would add a third controlled-injection table but no independent ground truth. Bank Marketing already
provides the monthly-delivery role. **Decision D-25: BAF stays optional and is excluded from all pilot results.**

## Repository hygiene check (2026-10-20, [ours])

- Tracked files scanned for token patterns (GitHub, Kaggle `KGAT_`, OpenAI, AWS, private keys, legacy
  `kaggle.json`): none, in the working tree and in the full git history (`git log -p --all`). The check is
  repeated by `tests/test_repo_hygiene.py` on every test run.
- No file under `data/raw/` and no `.parquet/.duckdb/.xls/.zip` file is tracked; the largest tracked file is
  `uv.lock` (200 kB).
- Committed data-derived content is limited to aggregate statistics (row counts, rates, per-scenario metrics)
  of CC BY 4.0 / Apache-2.0 sources; `data/manifests/baf.validation.json` contains only column names and
  aggregate counts of BAF (no records).
- No personal data from non-public sources and no Rabobank / Avanade data is present.
