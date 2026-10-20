# Financial Data Quality Evaluation Framework (MSc AI thesis)

A reproducible tool and research foundation for one question a data engineer faces when onboarding a
structured financial source:

> *Given the conventional data-quality controls we already run (dbt/SQL rules and statistical
> thresholds), which plausible errors do they miss, and does a learned cell-level detector add enough
> detection – at an acceptable alert burden – to justify adding it?*

MSc Artificial Intelligence thesis, University of Groningen; graduation internship at Avanade in a
Rabobank-related data-engineering context. **Public and synthetic data only** – no bank data is used,
and nothing here estimates real error rates of any bank source.

Status (2026-10-20): **foundation and qualification phase.** Literature, datasets, detectors and error
injection are qualified; an end-to-end feasibility demonstration runs on two financial datasets. The
confirmatory experiments have **not** been run. Start with [`docs/feasibility_report.md`](docs/feasibility_report.md).

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
data/raw/ (ignored)             immutable downloads;  data/manifests/  acquisition manifests (committed)
dbt/                            dbt Core project: generic evidence tests (macros/), generated models/tests
src/dq_framework/               acquisition, contracts, profiling, controls, injection, detectors, evaluation, reporting, pipeline, cli
envs/                           isolated environments + runners for the original CDC and Raha implementations
scripts/                        download / verify / validate_injection / qualification probes
tests/                          pytest suite (CI runs without datasets)
reports/                        feasibility demo reports (Markdown)
results/qualification/          small qualification outputs (CSV/JSON); results/runs/ is ignored
docs/                           research documentation (see below)
```

## Documentation

| Document | Content |
|---|---|
| [`docs/feasibility_report.md`](docs/feasibility_report.md) | What was done, what passed/failed, final assessment |
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
Licence notes are not legal advice.
