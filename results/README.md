# Results

- `qualification/` (committed): small outputs of the qualification phase – injection validation per
  scenario variant (`injection_validation_<dataset>.csv`), the Flights and Tax probes (`*_probe.json`),
  the CDC fidelity and seed-variance summaries (`cdc_*.json`) and the compatibility matrix
  (`compatibility_matrix.csv`).
- `runs/` (git-ignored): full run directories written by `dqf run` – stacked batch, dbt artefacts and
  DuckDB file, control alerts, detector scores, injection log, manifest. Regenerate with the commands in
  the repository README.

Everything in this folder is qualification or feasibility evidence; none of it is a confirmatory result.
