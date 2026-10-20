# Working agreements for this repository

MSc AI thesis + engineering artefact on evaluating conventional data-quality controls and the incremental
value of learned cell-level detectors (public financial data only). Read `README.md` and
`docs/feasibility_report.md` first; decisions and their status are in `docs/decision_log.md`.

## Environment
- Main env: Python 3.12 via `uv sync --frozen --extra dev` (tab_err 0.2.1 needs Python < 3.13).
- Original detectors run in isolated Python 3.9 envs under `envs/` through subprocess adapters
  (`src/dq_framework/detectors/subprocess_adapter.py`). Never install AutoGluon/Raha into the main env.
- Set `OMP_NUM_THREADS` when running several scoring jobs in parallel (HistGradientBoosting oversubscribes).
- Raha must run with a private `TMPDIR` (it writes fixed-name temp files); the adapter does this.

## Rules of the research
- Raw data under `data/raw/` is immutable and never committed; acquire with `scripts/download_datasets.py`
  (hash-pinned). Never fabricate or substitute a dataset.
- Prediction targets (`default payment next month`, `y`, fraud labels) are not data-quality labels.
- Alerts on untouched data are *burden*, not verified false positives.
- Rules come from documentation and untouched data, with status verified / provisional / unsupported, and
  are never derived from injected test errors. Edit `config/contracts/*.yaml`, then `dqf controls generate`
  (a test fails if generated dbt files drift).
- Only cells whose value actually changed count as injected errors. Do not use tab_err's raw error mask as
  ground truth; do not use tab_err `CategorySwap` (frequency) or `AddDelta` defaults (see
  `docs/error_injection_validation.md`).
- Qualification and design work uses the `dev` partition of split seed 1. Test partitions and new split
  seeds are reserved for the frozen confirmatory protocol (`docs/research_design.md`).
- Report every scenario, failure and null result. Mark claims as verified / provisional / unknown.

## Checks before committing
```bash
ruff check src scripts tests
python -m pytest -q
```
