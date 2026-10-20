# Apply the published data-quality benchmark update

This is a GitHub-ready *patch bundle*, not raw third-party data. It adds three literature-sourced dirty/clean pairs (Raha Rayyan, Jung Restaurant, optional Jung Cars) to the existing dataset registry, without replacing any code or datasets.

1. Extract this ZIP **into the root of** `oosterbaanvu/masterthesis2` (the newest Claude branch `claude/exciting-ritchie-w1e31t`, or a new branch created from it).
2. Run `python scripts/register_published_benchmarks.py`. This appends entries to `config/datasets.yaml` and checks that it has not overwritten existing records. Running it twice is harmless.
3. Install the repository's environment and run the download, verification, audit and unit-test commands in `docs/published_benchmark_datasets.md`.
4. Review the results, commit `config/datasets.yaml` together with the files in this bundle, and push the branch. Do not commit `data/raw/`, `.env` files or API tokens. Check the new files and CI before merging.
5. If a source download fails or a source licence is unclear, document the failure and do not relabel it as verified. No Kaggle API key is required for these three benchmarks.

Notes:
- Two datasets (`raha_rayyan`, `jung_restaurant`) are default downloads; `jung_cars` is optional because of the numeric-format caveat.
- This update enables reproducible access, pair alignment and label auditing. It **does not** yet add custom data contracts for `dqf scan`, detector benchmarking, or validated domain checks. Those are the next engineering tasks, and should be implemented only after source-specific assumptions are reviewed.
- GitHub connector access in the initiating ChatGPT session was read-only (branch creation returned HTTP 403), so these changes have not been committed to the repository automatically.
