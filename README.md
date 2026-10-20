# Financial Data Quality Evaluation Framework (MSc AI thesis)

A reproducible tool and research foundation for one question a data engineer faces when onboarding a
structured financial source:

> *Given the conventional data-quality controls we already run (dbt/SQL rules and statistical
> thresholds), which plausible errors do they miss, and does a learned cell-level detector add enough
> detection – at an acceptable alert burden – to justify adding it?*

MSc Artificial Intelligence thesis, University of Groningen; graduation internship at Avanade in a
Rabobank-related data-engineering context. **Public and synthetic data only** – no bank data is used,
and nothing here estimates real error rates of any bank source.

Status (2026-10-20): **comprehensive feasibility pilot completed** (design-pool data only; all results
provisional). Seven datasets acquire and verify reproducibly (Give Me Some Credit is integrated but blocked
until the Kaggle competition rules are accepted). CDC and a clean-room dBoost (100 % agreement with the
original) are the primary scored, label-free cell detectors; LUCARIO-core, SD/IQR and Isolation Forest are
secondary. 14 replications on UCI Credit and Bank Marketing (random splits and consecutive deliveries) were run.
An operational `dqf scan` turns offline evidence into ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE for a new
batch. Verdict: **conditional GO** for a confirmatory study on selection reliability under error-population
shift. Start with [`docs/comprehensive_pilot_report.md`](docs/comprehensive_pilot_report.md); the foundation phase
is in [`docs/feasibility_report.md`](docs/feasibility_report.md).

Dataset extension (2026-10-20): Rayyan, Restaurant and optional Cars are now registered with pinned public
sources, contracts and dirty-only `dqf scan` evaluations. Nine exploratory scans found zero incremental
missing-value recall over conventional completeness controls; Rayyan references remain uncertain.
See [`docs/real_error_benchmark_report.md`](docs/real_error_benchmark_report.md) for results and limits,
and [`docs/published_benchmark_datasets.md`](docs/published_benchmark_datasets.md) for acquisition provenance.

## What it does

```
contract (YAML) → generated dbt tests → executed on DuckDB, failing rows stored as evidence
reference partition → fitted statistical bounds + learned detector (CDC per cell, Isolation Forest per record)
evaluation partition → copies with controlled errors (operation × ECAR/EAR/ENAR mechanism × seed)
→ which injected errors do the controls catch / miss, what does the detector add within a review budget,
  how many extra alerts on untouched data → auditable report + decision (adopt / do not adopt / insufficient evidence)
```

## Quick start

Requires Python 3.12 (tab_err 0.2.1 does not support 3.13) and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --extra dev            # pinned environment (.venv)
source .venv/bin/activate

python scripts/download_datasets.py     # download from UCI / pinned GitHub commits, verify SHA-256, make read-only
python scripts/verify_datasets.py       # re-verify hashes and shapes at any time
python scripts/download_datasets.py raha_rayyan jung_restaurant jung_cars  # Cars is optional
python scripts/qualify_published_pairs.py --output data/local_pair_audit.json
python scripts/evaluate_real_error_benchmarks.py  # dirty-only scans first, references afterward; no injection

dqf controls generate                   # contracts -> dbt/models/generated (committed; a test checks drift)
dqf controls check uci_credit           # run all dbt controls on the untouched table

python scripts/validate_injection.py uci_credit          # validate every scenario of the catalog (dev partition)
dqf run config/experiments/demo_uci_credit.yaml --report reports/demo_uci_credit.md
dqf run config/experiments/demo_uci_bank_marketing.yaml --report reports/demo_uci_bank_marketing.md

dqf report results/runs/<run_dir> --out reports/x.md     # re-render a report from a finished run

python scripts/qualify_detectors.py                      # detector fidelity, seed variance, compatibility matrix
python scripts/compare_rank_scores.py                    # CDC ranking-score comparison (dev data)
python scripts/probe_flights_typed.py                    # R2 probe: CDC on real Flights errors
python scripts/probe_tax_bart.py                         # out-of-generator probe on BART errors (Tax)
python scripts/analyse_decision_sensitivity.py results/runs/<run_dir>   # decisions vs baseline/budget/mechanism

python -m pytest -q                     # unit + dbt integration tests (+ data tests when data is present)
```

### Comprehensive pilot (2026-10-20)

```bash
python scripts/dataset_status.py                          # or: dqf datasets status  (present / verified; local manifest)
bash envs/dboost/install.sh                               # optional: original dBoost (GPL) for fidelity checks only
python scripts/qualify_pilot_detectors.py                 # compatibility, runtime, memory, dBoost fidelity
OMP_NUM_THREADS=1 python scripts/run_pilot.py config/pilot/pilot_uci_credit.yaml          # 5 pilot splits
OMP_NUM_THREADS=1 python scripts/run_pilot.py config/pilot/pilot_uci_bank_marketing.yaml  # 5 random + 4 delivery sets
python scripts/analyse_pilot.py                           # -> results/pilot/*.csv, docs/figures/pilot_*.png
python scripts/primary_analysis.py                        # primary analysis, go/no-go, sample size
python scripts/render_pilot_tables.py > /tmp/tables.md    # the report's tables, regenerated from the CSVs
python scripts/independent_validation.py                  # BART (Tax) and real-error (Flights, Beers) checks
dqf scan config/scans/scan_bank_marketing_period13.yaml   # operational scan of a new monthly delivery
dqf scan config/scans/scan_uci_credit_new_clients.yaml
dqf scan config/scans/scan_bank_marketing_rules_only.yaml
dqf feedback results/runs/scans/<scan>                    # after annotating feedback.csv
```

One replication takes 6–17 min on 4 CPUs (330–400 scenarios, 8 detector configurations, one dbt run). The full
pilot (14 replications) ran in about 1.5 h; use at most three parallel processes on 15 GB (a Bank replication
peaks at ~5 GB). `uv sync --extra figures` adds matplotlib
for the figures.

Set `OMP_NUM_THREADS` when running several scoring jobs at the same time.

Isolated environments for the *original* detector implementations (only needed for fidelity checks):

```bash
bash envs/cdc_aistats/install.sh                         # Python 3.9, AutoGluon 0.8.2, original CDC code
uv venv --python 3.9 envs/raha/.venv && VIRTUAL_ENV=envs/raha/.venv uv pip install -r envs/raha/requirements.txt
```

BAF (Feedzai, Base variant) is an **optional** dataset, downloaded through the official Kaggle client and
never needed by the rest of the framework. Its licence is unresolved (non-commercial; ND vs SA), see
`docs/dataset_qualification.md`:

```bash
uv sync --frozen --extra dev --extra kaggle   # or: pip install kaggle
export KAGGLE_API_TOKEN=...                   # kaggle.com > Settings > API; or ~/.kaggle/kaggle.json
python scripts/download_baf.py --report data/manifests/baf.validation.json
```

## Repository layout

```
config/datasets.yaml            dataset registry: sources, pinned hashes, roles, licences
config/contracts/               source contracts: columns, semantics, rules with evidence status
config/experiments/             scenario catalog and run configurations
config/pilot/, config/scans/    pilot designs (strategies, held-out family, detectors) and operational scan configs
data/raw/ (ignored)             immutable downloads;  data/manifests/  acquisition manifests (committed)
dbt/                            dbt Core project: generic evidence tests (macros/), generated models/tests
src/dq_framework/               acquisition (+status), contracts, profiling, controls, injection, detectors (cdc, dboost,
                                univariate/LUCARIO-core, iforest, subprocess adapters), evaluation, pilot, service (scan), cli
envs/                           isolated environments + runners for the original CDC, Raha and dBoost (GPL, child process)
scripts/                        download / verify / validate_injection / qualification probes
tests/                          pytest suite (CI runs without datasets)
reports/                        feasibility demo reports (Markdown)
results/qualification/          small qualification outputs (CSV/JSON); results/pilot/ pilot summaries; results/runs/ is ignored
docs/                           research documentation (see below)
```

## Documentation

| Document | Content |
|---|---|
| [`docs/comprehensive_pilot_report.md`](docs/comprehensive_pilot_report.md) | **Pilot results and answers to the ten decisive questions** |
| [`docs/post_pilot_research_directions.md`](docs/post_pilot_research_directions.md) | Defensible research directions after the pilot |
| [`docs/dataset_overview.md`](docs/dataset_overview.md) | Per-dataset source, licence, hash, roles, ground truth, suitability |
| [`docs/published_benchmark_datasets.md`](docs/published_benchmark_datasets.md) | Verified Rayyan/Restaurant/Cars acquisition, label audit and service follow-up plan |
| [`docs/real_error_benchmark_report.md`](docs/real_error_benchmark_report.md) | Actual service evaluation on published pairs, fixed-budget results, label limits and MSc suitability |
| [`docs/detector_comparison.md`](docs/detector_comparison.md) | Detector requirements, licences, fair comparison tracks |
| [`docs/injection_strategies.md`](docs/injection_strategies.md) | Error type / mechanism / rate; strategies A and B; held-out family |
| [`docs/operational_demo.md`](docs/operational_demo.md) | `dqf scan`: analysing a new batch, findings, recommendation, feedback |
| [`docs/feasibility_report.md`](docs/feasibility_report.md) | Foundation phase: what was done, what passed/failed |
| [`docs/literature_review.md`](docs/literature_review.md), [`docs/references.bib`](docs/references.bib) | Verified literature |
| [`docs/research_gap.md`](docs/research_gap.md), [`docs/research_directions.md`](docs/research_directions.md) | Novelty assessment, directions, recommended research question |
| [`docs/research_design.md`](docs/research_design.md) | Proposed confirmatory protocol |
| [`docs/dataset_qualification.md`](docs/dataset_qualification.md) | Dataset evidence and roles |
| [`docs/method_compatibility.md`](docs/method_compatibility.md) | Detector requirements and compatibility matrix |
| [`docs/error_injection_validation.md`](docs/error_injection_validation.md) | tab_err analysis and injection validation |
| [`docs/practical_use_case.md`](docs/practical_use_case.md) | Engineering use case |
| [`docs/decision_log.md`](docs/decision_log.md), [`docs/next_steps.md`](docs/next_steps.md) | Decisions and plan |

## Data and licences

Raw third-party data is never committed. UCI datasets are CC BY 4.0 (cite Yeh 2009; Moro et al. 2014);
Raha benchmark files come from BigDaMa/raha (Apache-2.0 repository, no separate data licence stated).
BAF is optional and excluded from the pilot (contradictory non-commercial licences). dBoost's original code
(GPL-3.0) is never copied or imported: it is fetched by `envs/dboost/install.sh` and run as a child process;
the framework's `dboost` detector is a clean-room re-implementation. LUCARIO's and REIN's code carry no
reuse licence and were not copied. Licence notes are not legal advice.
