# Published data-quality benchmarks added to the dataset registry

Status: **acquisition and pair audit verified on 20 October 2026** in the target cloud environment, from
`claude/exciting-ritchie-w1e31t` at `27ce4f67e1535de637d62c95c29878f77d5376ea`. All six CSV downloads match
the bundle's SHA-256 pins and are read-only. Registry registration is idempotent and preserves existing
entries. The acquisition-only work described below has since been extended with source contracts,
actual dirty-only service scans and separate reference evaluation; see
[`real_error_benchmark_report.md`](real_error_benchmark_report.md). Nothing here establishes production validity.

## Purpose

The existing pilot uses UCI Credit and Bank Marketing with synthetic errors. To develop a general data-quality service, it is necessary to use benchmarks where dirty and reference values already exist independently of the service's injection experiments. The literature commonly uses a mixture of naturally occurring errors, curated repairs and generated errors; these groups should remain separate in results. A dirty/clean difference is not automatically an objective mistake; it can represent standardisation, an annotation judgment, an outdated value or a genuine corruption.

Scientific references:

- Mahdavi et al. (2019), *Raha: A Configuration-Free Error Detection System*, ACM SIGMOD, DOI [10.1145/3299869.3324956](https://doi.org/10.1145/3299869.3324956). Original dataset files: [BigDaMa/raha](https://github.com/BigDaMa/raha/tree/master/datasets). This paper reports Rayyan as real data cleaned by its owners and discusses missing values, typographic and formatting errors and attribute-dependency violations.
- Jung, Jäger, Chandler and Biessmann (2025), *Towards Realistic Error Models for Tabular Data*, *ACM Journal of Data and Information Quality*, DOI [10.1145/3774914](https://doi.org/10.1145/3774914). Original experiment files: [calgo-lab/error-paper](https://github.com/calgo-lab/error-paper). The authors use `tab_err` and supply the experimental Restaurant and Cars variants.
- Abdelaal et al. (2023), *REIN: A Comprehensive Benchmark Framework for Data Cleaning Methods in ML Pipelines*, EDBT: [project repository](https://github.com/mohamedyd/rein-benchmark). REIN offers benchmark structure and error generators; its repository is not a guarantee of access to independently validated ground truth.

## Dataset entries

| Key | Domain | Source files | Publication type | Raw pair differences inspected | Appropriate use |
|---|---|---|---|---|---|
| `raha_rayyan` | Bibliographic metadata | 1,000 × 11 | Real bibliographic records; published owner-corrected reference in Raha | 948 changed strings across 774 rows; 722 in `article_jcreated_at` | Conditional existing-error benchmark; dates and reference quality need adjudication |
| `jung_restaurant` | Restaurants/business listings | 864 × 6 | Published synthetic error-model experiment (`restaurant_3_1`) | 155 changed strings across 147 rows, all dirty `?` values | External missing-value replication; uses the same `tab_err` generator family as this framework |
| `jung_cars` | Vehicles, mixed numeric/text | 406 × 9 | Published synthetic error-model experiment (`cars_3_1`) | 820 raw differences across all 406 rows; 710 numeric-format equivalents and 110 dirty `?` values remain | Optional missing-value/format stress test; raw differences are unsuitable numerical-error labels |

The counts come from the downloaded bytes at the pinned commits, compared as literal strings without
NA conversion. Both primary-table declarations and dirty/clean dimensions and headers are checked.
Declared unchanged row anchors (`id`; `name, addr`; `Car, MPG`, respectively) must also match in order.
Anchors are consistency checks on the published row order, not independently established unique keys.
Raw files are **not committed**. Acquisition manifests under `data/manifests/` contain the six full
SHA-256 hashes, byte sizes, source URLs and retrieval times. The aggregate audit is committed at
[`results/qualification/published_pair_audit.json`](../results/qualification/published_pair_audit.json),
without raw example records. The detailed audit with examples is local and git-ignored.

The Raha repository has an Apache-2.0 licence, but upstream dataset-specific terms remain unconfirmed.
The pinned `calgo-lab/error-paper` tree has no top-level data/code licence; licences in vendored detector
directories do not establish redistribution rights for its datasets. Public download availability and
successful verification establish reproducibility, not clearance to redistribute raw files or deploy
commercially. Those rights remain unresolved.

## Observed differences and label limits

- **Rayyan:** `article_jcreated_at` 722, `author_list` 84, `article_jissue` 53,
  `article_pagination` 32, `article_jvolumn` 22, `article_title` 14, `journal_issn` 12 and
  `journal_title` 9. Seventy volume/issue differences replace empty strings with `-1`, a reference
  sentinel rather than a recovered value. Date component reordering, encoding changes and pagination
  converted to date-like references occur. The reference may itself contain conversion artefacts.
  None of these 948 candidates was independently adjudicated as a true error; IDs are excluded from
  detector features in any future evaluation.
- **Restaurant:** all 155 differences replace a reference value with `?`: `type` 54, `phone` 39,
  `city` 32, `class` 30. `name` and `addr` are unchanged. `class` is a restaurant entity/duplicate
  grouping label in this benchmark, not an ordinary business measurement; exclude it from detector
  features and report its corruptions separately. The measured slice is missing-value corruption,
  not evidence of general typo, category-swap or natural-error detection performance.
- **Cars:** candidate missing values occur in `Horsepower` 18, `Origin` 17, `Cylinders` 16,
  `Displacement` 16, `Model` 16, `Weight` 15 and `Acceleration` 12. The 710 numerically equivalent
  strings comprise `Weight` 391, `Horsepower` 222, `Displacement` 96 and `Acceleration` 1.
  Numeric equivalence uses finite `Decimal` values only on explicitly declared numeric columns;
  no global string normalisation changes identifiers. Even the 110 remaining candidates are
  generated labels, not independently observed field errors. Cars remains optional.

## Reproduce in a checkout

From the repository root (Python 3.12 and uv):

```bash
python scripts/register_published_benchmarks.py --dry-run
python scripts/register_published_benchmarks.py
uv sync --frozen --extra dev
source .venv/bin/activate
python scripts/download_datasets.py raha_rayyan jung_restaurant
python scripts/download_datasets.py jung_cars              # optional, format caveat
python scripts/verify_datasets.py raha_rayyan jung_restaurant jung_cars
python scripts/qualify_published_pairs.py raha_rayyan jung_restaurant jung_cars --output data/local_pair_audit.json
python -m pytest -q tests/test_published_pair_audit.py
ruff check src scripts tests
python -m pytest -q -ra
```

In the cloud workspace use `UV_CACHE_DIR=/workspace/.cache/uv` for uv if the default home cache is
read-only. No Kaggle token, API credentials, original detector environment or additional dependencies
are needed for these datasets. Explicitly requesting Cars makes absence, corruption or an invalid pair
fail the audit. Only an absent optional dataset is skipped by the no-argument audit.

The audit checks byte-pinned downloads, row/column alignment, differences per column and numeric
equivalences; it is **not** a detector benchmark or a gold-standard certification. Raw files remain in
`data/raw/<key>/` and are ignored by Git. `data/local_pair_audit.json` is ignored because it contains
example records. A malformed pair, unknown column, mismatching anchor or unpinned file cannot pass.

Executed validation: downloads, verification and pair audit passed for all three datasets; lint passed;
the full suite passed **169 tests**, with **9 skips** (UCI/Kaggle datasets absent, original dBoost
environment absent, and UCI-dependent pilot/scan smoke tests). Existing contract-generation drift tests
and the synthetic dbt integration test passed. The financial pilot and new-source service scans were
not rerun. A repeated download reused all six verified files without changing them.

The committed summary can be regenerated from the local audit without including example records:

```python
import json
from pathlib import Path
from dq_framework.acquisition import load_registry
from dq_framework.datasets import load_pair

report = json.loads(Path("data/local_pair_audit.json").read_text())
summary = {}
for key, result in report.items():
    spec = load_registry()[key]
    entry = {k: v for k, v in result.items() if k != "examples_remaining"}
    entry["source_version"] = spec.raw["version"]
    entry["source_urls"] = [f.url for f in spec.files]
    dirty, clean = load_pair(spec)
    entry["dirty_question_marks_on_changed_cells"] = int(((dirty != clean) & (dirty == "?")).sum().sum())
    summary[key] = entry
Path("results/qualification/published_pair_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
```

## Follow-up plan for the Data Quality Evaluation & Selection Service

This records the plan from the acquisition stage. Contracts, grouped exploratory splits, compatibility
checks, dirty-only service runs and separate evaluation are now implemented in
`real_error_benchmark_report.md`. Independent adjudication, licence clearance and confirmatory
study evidence remain outstanding; the historical audit alone did not supply them.

1. **Review the sources and labels.** Resolve dataset usage terms. For Rayyan, adjudicate date,
   sentinel, encoding and pagination candidates on the design pool; freeze separate corruption,
   canonicalisation and uncertain-label masks. For Restaurant, document the released variant's
   missing marker and exclude `class` from features. Keep this external `tab_err` replication
   separate from the natural-error track and the existing financial pilot.
2. **Define source contracts.** Add reviewed `config/contracts/raha_rayyan.yaml` and
   `jung_restaurant.yaml`, with supported/provisional/unsupported rule status. Preserve raw strings;
   document source-specific missing tokens and typed views. Add stable record IDs, identifier exclusions,
   reviewed date/ISSN/phone rules, and entity grouping for duplicate restaurant listings. Derive rules
   from source documentation and dirty design data, never from clean evaluation values. Generate dbt
   artefacts through the existing contract generator and run its drift/integration checks.
3. **Freeze fair splits and detector compatibility.** Group duplicate publications/restaurants before
   selecting reference, development and held-out batches. Do not imply a chronological delivery model
   when source chronology is unknown. Fit encoders, bounds and thresholds on allowed history only.
   Qualify CDC, dBoost and text/pattern methods for these small text-heavy tables; report incompatibility
   and rare categories. Numeric-only detectors cannot cover all columns. Keep record and cell scores
   separate, and select budgets on development data before opening the holdout.
4. **Keep service input and evaluation reference separate.** The existing registry's `table` points
   to dirty.csv, which can support `load_contract_table` after contracts and source-specific missing
   handling exist. Add scan configs with disjoint dirty-history/batch selections. `dqf scan` must not
   read clean.csv, pair-audit examples or clean test values; enforce this with a test that denies clean
   file access. Only a separate evaluator may join findings to the reference by stable ID and a frozen
   label mask. Existing UCI evidence cannot justify ADOPT for these new domains; use
   INSUFFICIENT_EVIDENCE until source-specific evidence exists.
5. **Evaluate and report.** Compare rules, statistics and compatible detectors at fixed review budgets.
   Report candidate recall and precision only on valid, adjudicated labels, incremental detections,
   alert burden, runtime and uncertainty across grouped resamples. Separate raw-string and
   numeric-semantic outcomes and exclude uncertain references from scored denominators. Run a dirty-only
   service smoke test and an evaluator integration test; only then claim operational integration.

## How this affects the thesis

Do not pool these with the financial pilot's results or treat F1 scores as directly comparable. Rayyan's
bibliographic/date candidates, Restaurant's synthetic missing values and Cars' numerical formatting are
distinct populations. The subsequent service evaluation separates label families and uncertainty, groups
dirty entities and keeps clean references in the evaluator; see `real_error_benchmark_report.md`.

Other existing benchmarks worth qualifying rather than silently adding: Raha Movies (`movies_1`: 7,390 × 17, real source with published references), REIN's Citation/Beers, and the large AddressTable/Clean Me If You Can (2026, geocoder-based references, ODbL data terms). Do not introduce them into a confirmatory study without separate download, licence, label, and detector-compatibility checks.
