# Results

- `qualification/` (committed): small outputs of the qualification phase – injection validation per
  scenario variant (`injection_validation_<dataset>.csv`), the Flights and Tax probes (`*_probe.json`),
  the CDC fidelity and seed-variance summaries (`cdc_*.json`) and the compatibility matrix
  (`compatibility_matrix.csv`).
- `runs/` (git-ignored): full run directories written by `dqf run` – stacked batch, dbt artefacts and
  DuckDB file, control alerts, detector scores, injection log, manifest. Regenerate with the commands in
  the repository README.
- `real_error_benchmark/` (committed): aggregate results of nine dirty-only service scans on published
  pairs, compatibility/label/workload tables and the frozen configuration/code fingerprints. No raw
  record values are included. Reproduce with `python scripts/evaluate_real_error_benchmarks.py`;
  see `docs/real_error_benchmark_report.md`. Predictions and full findings stay in ignored `runs/`.
- `thesis_integrated/` (committed): exploratory shared-total-budget results, paired selector/design
  comparisons, conditional case uncertainty, workload, scenario failures and run/output fingerprints.
  This is a new estimand; do not pool these numbers with the earlier additive-budget pilot. Reproduce
  with `scripts/run_thesis_study.py`, `analyse_thesis_study.py` and `validate_thesis_transfer.py`; see
  `docs/thesis_scale_pilot_report.md`. Figures are in `docs/figures/thesis/`; raw cells remain ignored.

Everything in this folder is qualification or feasibility evidence; none of it is a confirmatory result.
