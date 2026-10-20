# Detector and benchmark research (primary sources)

Status: 2026-10-20. Research scratch for the MSc thesis (not a repository document).
Markers: **[V-full]** relevant full text read; **[V-abs]** abstract/metadata only; **[code]** read in the
repository at the commit given; **[ours]** small probe executed in this session (scratch only, not part of
the thesis pipeline); **UNVERIFIED** = could not be confirmed (URL checked is given). Licence notes are
statements of what the files say, not legal advice.

Download/clone locations (untrusted data, read only): papers `(session scratch) pdf/`, repositories
`(session scratch) repos/`, single raw files `(session scratch) src/`.

HEAD commits (via `git ls-remote`, 2026-10-20):

| Repository | HEAD commit | Last commit date |
|---|---|---|
| se-jaeger/conformal-data-cleaning | fd8a2126c9626099f3d45511fd05d30af8de6b64 | (same as used in repo) |
| se-jaeger/conformal-inference (tag `cleaning-paper`) | e25cb5938808360033201afc2ae567e5de3ad6c0 | – |
| mooselab/Detect-Cell-level-Data-Anomalies-With-LUCARIO | 3664bfa830b7b13f8a08cc7dd960c871c56aaeeb | 2025-10-24 |
| mooselab/Discover-Data-Quality-With-RIOLU | df3f7dc7673fda3f02d147fdf4c539a2bf3cc4d5 | 2024-08-08 |
| cpitclaudel/dBoost | a47cb564e900c3e5220413f810e810b00046d561 | 2015-12-03 |
| mohamedyd/rein-benchmark | b8a0727fdeb6d295eb88c702a344093a1d9096d1 | 2024-07-24 |
| ZJU-Data-Governance-and-Services-Team/ZeroED | 2b84266e1d8b2014d36643d343429d9a20bd769e | 2025-02-28 |
| WelkinNi/ZeroED (named in ZeroED README) | 49678b8470180ab17e9c40bcedd2c00ac49de6ff | – |
| BigDaMa/raha | 7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c | (as pinned in repo) |
| qixuchen/AutoTest | 4acf65cf37a506206bf2888dbd45f17e58dce2e2 | 2026-04-23 |
| viviancircle/TableEG | ea889b80ef5ccb7ef68f760a867aef26b835d82f | 2025-03-06 |
| dbunibas/BART | 354f503f401d5360e9a6957f4edd096d3dc413f6 | 2023-05-10 |

---

## DETECTORS

### 1. CDC – Conformal Data Cleaning

- **Paper:** Jäger, S. & Biessmann, F. "From Data Imputation to Data Cleaning – Automated Cleaning of Tabular
  Data Improves Downstream Predictive Performance", AISTATS 2024, PMLR 238:3394–3402,
  https://proceedings.mlr.press/v238/jager24a.html (no DOI; PDF read) **[V-full]**.
- **Repository:** https://github.com/se-jaeger/conformal-data-cleaning @ fd8a2126 **[code]**.
- **Licence (LICENSE read):** MIT, "Copyright (c) 2024 Sebastian Jäger". Dependency
  se-jaeger/conformal-inference: Apache-2.0 (LICENSE read). JENGA (schelterlabs/jenga): no LICENSE file at
  main/master via raw (404) – **UNVERIFIED**. AutoGluon 0.8.2: Apache-2.0 (PyPI metadata).
- **Designed error types:** four JENGA corruptions – swapping values between columns, random scaling,
  Gaussian noise, shifts of categorical value distributions – at 1/5/10/30/50% per column, mixed; values
  sampled completely at random (paper §4.1).
- **Reference data:** "trained on clean training data"; one AutoGluon model per column plus a calibration
  set (~1,000 points, following Angelopoulos & Bates). **Labels / external knowledge:** none.
- **Output:** cell level; the original returns a flag (value outside the conformal set/interval) and a
  cleaned value; no score is exposed (our re-implementation adds conformal p-values).
- **Dependencies:** `pyproject.toml`: python `^3.9,<3.10`, autogluon `^0.8.2` [all], scikit-learn `<1.3.0`,
  pyod, conformal-inference and jenga pinned to git tag `cleaning-paper`. AutoGluon 0.8.2 itself requires
  Python >=3.8,<3.11 (PyPI).
- **Runnable:** yes – executed in this repository (method_compatibility.md, `cdc_original`) [ours, earlier].
- **Reported compute:** no runtime figures found in the PDF text (experiments on Kubernetes with Helm;
  50 HPO trials per model in the README commands). **UNVERIFIED** beyond that.
- **Limitations stated in paper (§6.4):** benchmarked on 16 OpenML datasets with 5–15 columns and about
  4,800–89,000 rows *without missing values*; assumes high-quality training data; not transferable to
  text/image data. Relevant to UCI Credit/Bank: the strict `<` set rule and rare-label calibration effects
  are already documented in method_compatibility.md (no new information here).

### 2. LUCARIO (and predecessor RIOLU)

- **Paper:** Qin, Q., Li, H., Merlo, E. "Unsupervised, robust, and lightweight detection of data pattern
  anomalies and outliers", Information and Software Technology 192 (2026) 108035,
  DOI 10.1016/j.infsof.2026.108035 (Crossref: issued 2026-04; VoR licence `creativecommons.org/licenses/by/4.0`,
  start 2026-01-13). SSRN preprint DOI 10.2139/ssrn.5261048 (2025). **[V-abs]**: structured abstract
  reconstructed from OpenAlex (`api.openalex.org/works/doi:10.1016/j.infsof.2026.108035`).
- **Open access:** the published article is Gold/hybrid OA under **CC BY 4.0** (Crossref, OpenAlex,
  Semantic Scholar, Unpaywall all agree), but the full text could not be fetched here: ScienceDirect 403
  (curl and WebFetch), Elsevier text-mining API requires a key (401), PolyPublie record
  https://publications.polymtl.ca/71729/ has `full_text_status = none`; no arXiv version (arXiv API search
  "LUCARIO" and title: no hit). **Action:** download the CC BY PDF via a normal browser/institution.
- **Abstract facts [V-abs]:** fully unsupervised, statistic-based, cell-level; anomalies split into
  pattern violations and outliers (categorical and numerical); "three detection approaches based on
  heuristics and statistical theories"; six open-source datasets plus one industrial dataset (CompanyX);
  average F1 0.49, "up to 40% improvement over the best baseline tool".
- **Repository found:** https://github.com/mooselab/Detect-Cell-level-Data-Anomalies-With-LUCARIO
  @ 3664bfa8 (found via GitHub repository search of `user:mooselab`). **No LICENSE file** anywhere in the
  tree (`git ls-files`; raw LICENSE/LICENSE.md/LICENSE.txt 404) → default copyright, no reuse grant.
  README: Python >=3.8, pandas 1.5.3, numpy 1.24.3, scikit-learn 1.3.2, matplotlib 3.7.5.
- **Benchmarks in the replication code [code]:** `beers, flights, hospital, HOSP-10K, HOSP-100K, movies_1`
  (Raha/Baran family); baselines dBoost, Deequ, TFDV, FlashProfile, Auto-Test, GPT-5 and Llama3 (README).
  No numeric financial data.
- **Algorithm as implemented [code; read, not executed]** (`constraint_inference.py`,
  `anomaly_detection.py`, `detectors/{range,pattern,utils}.py`):
  - Null tokens `'', NULL, None, N/A, NaN` are removed before inference and flagged at detection time.
  - *Type constraint:* fraction of values parseable by `float`; if the binary entropy of
    (numeric, string) ≥ 0.5 → "Mixed" (no type check), else majority type; cells of the other type flagged.
  - *Numerical constraint:* `[median − k·MAD, median + k·MAD]` with **k = 3** (`multiplier`), MAD = median
    absolute deviation (unscaled). At detection time, **if more than 1 − r_cov = 5% of the column's cells
    violate the range, the numerical constraint is dropped** for that column (and the JSON rewritten).
  - *Categorical constraint:* value counts sorted ascending, a dummy count 1 prepended; the cut is the
    largest successive ratio `f[i+1]/f[i]`; categories above the cut are accepted if they cover
    > r_cov = 0.95; if the top value alone covers > 0.95 only it is accepted; otherwise no constraint.
  - *Pattern constraint:* token templates (alphanumeric runs separated by special characters), the same
    frequency-jump cut with coverage 0.95, then regexes with character classes `[0-9]`, `[A-Z]`, `[a-z]` and
    length constraints (300 lines in `pattern.py`; not fully traced).
  - A cell is flagged if any of type/categorical/numerical/pattern is violated → **binary cell flag, no score**.
  - Constraints are inferred from the *dirty file under test itself* (transductive), but are stored as JSON
    and could be fitted on a reference partition and applied to new batches; the 5% drop rule still
    depends on the batch under test.
- **Consequences for UCI Credit / Bank Marketing [ours, clean-room simulation of the rule, not their code]:**
  median ± 3·MAD leaves 15.2% of a lognormal(9,1) column and 16.3% of a 20%-zero-inflated amount column
  outside the range, and a PAY-like code column with >50% zeros has MAD = 0 (37% outside) → all three
  exceed 5%, so LUCARIO's numerical check would be **switched off** for BILL_AMT/PAY_AMT/PAY_x-type columns.
  For low-cardinality codes the categorical rule applies; documented-but-rare codes (EDUCATION 0/5/6,
  MARRIAGE 0, `marital = unknown`) would probably be outside the accepted set (provisional – depends on the
  ratio cut). Scale errors that change the digit count might be caught by pattern length constraints
  (UNKNOWN, not traced).
- **Reimplementable?** The numeric and categorical rules are short and fully specified in the code (above),
  so a clean-room reimplementation is technically easy. Because the code carries no licence, implement
  from the CC BY paper text (once obtained) or from a written specification, cite the paper, and do not
  copy code. Whether the *paper* documents exactly the same rules (k = 3, 5% drop rule) is **UNVERIFIED**.
- **RIOLU (predecessor):** Qin, Li, Merlo, Lamothe, "Automated, Unsupervised, and Auto-parameterized
  Inference of Data Patterns and Anomaly Detection", ICSE 2025 (arXiv 2412.05240; DOI
  10.1109/ICSE55347.2025.00078 per references.bib) **[V-abs]**. Repo mooselab/Discover-Data-Quality-With-RIOLU
  @ df3f7dc7, **LICENSE: MIT, "Copyright (c) 2024 Cinnamon Pie"** (read). Detects **pattern (regex/format)
  violations in string columns**: column sampling → coverage-rate (r_cov) estimation (Auto-RIOLU
  unsupervised; Guided-RIOLU estimates r_cov from the cleaned version) → constrained template generation
  → pattern generation/selection. Evaluated on FlashProfile DOMAINS (profiling) and modified Hospital
  (1k/10k/100k), Flights, Movies (anomaly detection; ground truth −1 null / 1 anomaly / 0 normal).
  Not an outlier detector for numeric/categorical values.

### 3. dBoost

- **Paper:** Pit-Claudel, C., Mariet, Z., Harding, R., Madden, S. "Outlier Detection in Heterogeneous Datasets
  using Automatic Tuple Expansion", MIT-CSAIL-TR-2016-002, 2016-02-08, http://hdl.handle.net/1721.1/101150
  (DSpace PDF download returned HTTP 429 here; the ICDE-format LaTeX source and `paper/icde/paper.pdf` in the
  repository were read instead – equivalence with the TR **UNVERIFIED**).
- **Repository:** https://github.com/cpitclaudel/dBoost @ a47cb564 (2015-12-03). **LICENSE: GPL-3.0**
  (full GNU GPL v3 text, read). Copies with the same LICENSE are vendored in Raha (`raha/tools/dBoost`),
  REIN (`cleaners/dBoost`) and ZeroED. GPL-3.0 means a derivative of the code must stay GPL; a clean-room
  reimplementation from the description below avoids this.
- **Python:** pure Python 3, no third-party dependency for gaussian/histogram/partitioned models.
  **[ours]** `dboost-stdin.py` ran on Python 3.13.16 with `--gaussian`, `--histogram`,
  `--discretestats … --partitionedhistogram …`. `--mixture` fails: imports matplotlib and uses
  `sklearn.mixture.GMM`, which scikit-learn removed in 0.20 (2018) → needs an old stack or a port.
- **Pipeline [code]:** read tuples → *tuple expansion* → *analyzer* pass (statistics + correlation hints)
  → *model* fit → per-tuple discrepancies. `--train-with FILE` fits on a separate file (reference/test
  separation is supported); otherwise train = test (transductive).
- **Typing [code]:** the first CSV row is auto-converted (`int`, then `float`, else `str`) and fixes the
  type of every column; later rows that fail conversion are **discarded** with a stderr message ("invalid
  types"), and since row indices are counted over yielded rows, **later indices shift**. With a header row
  every column becomes `str`. Raha and REIN write the CSV **with header=True**, so in those frameworks dBoost
  treats all columns as strings **[code]**; **[ours]** on a synthetic 2,000-row credit-like CSV the header
  version reduced `--gaussian 3` flags from 59 to 7 rows and caught only the ×1000 amount (through the
  `length` feature), not the code/limit errors.
- **Tuple-expansion rules (`features/__init__.py`) [code]:**
  - `str`: upper/lower/title case (3 bools), `isdigit`, length, Unicode-category signature, digits → `<num>`
    template ("strp"), HTML5 e-mail check, e-mail domain, identity, empty/whitespace.
  - `int`: identity, nil (None), `time.gmtime(x)` → year, month, mday, hour, min, sec, wday, yday
    (8 features, i.e. every integer is also read as a Unix timestamp), is-weekend, bits 0–5, divisible by 3
    and by 5, `x mod 10`.
  - `float`: identity, the same 8 date features of `int(x)`, fractional part.
  - Rules can be disabled with `-d rule_name`; `--floats-only` parses numbers as floats.
- **Analyzers [code]:** `--statistical ε`: per numeric expanded feature (bools count as numbers) running
  sum, sum², min, max, count; Pearson r for all pairs of numeric expanded features; pairs with |r| > ε
  become *hints* (expanded "field 0"). `--discretestats max_buckets fundep_size`: all sub-tuples of
  `fundep_size` expanded features whose joint histogram stays ≤ `max_buckets` distinct values become hints.
- **Gaussian model (`--gaussian t`, help: "Suggested value: 3") [code]:** μ = mean, σ = population SD
  (√(E[x²] − μ²)) of every numeric expanded feature, taken from the statistical analyzer (so
  `--statistical` is required). A feature value is a discrepancy if |x − μ| > t·σ; σ = 0 flags any deviation;
  non-numeric features and hints are skipped. Univariate; the hints are not used.
- **Histogram model (`--histogram peak_s outlier_s`, "Suggested values: 0.8 0.2") [code]:** one value
  counter per expanded feature and per hint (joint tuple); a counter is discarded as soon as it exceeds
  16 distinct values (`MAX_HIST_SIZE`). A kept histogram with d distinct values is *peaked* if the
  k = max(1, min(3, ⌊d/2⌋)) largest counts sum to > peak_s × total; non-peaked histograms are dropped.
  A value is a discrepancy if its count < outlier_s × n (n = non-null count of that feature) – i.e. *every*
  class below the fraction is flagged, not only rare ones. Single-feature checks run first; hint
  histograms are checked only if the row has no other discrepancy.
- **Partitioned histogram (`--partitionedhistogram jmp peak_s outlier_s`, help text "TODO") [code]:**
  operates only on hints (normally from `--discretestats`); first element = key, rest = value; one counter
  per key. A key's histogram is used if it has 2–16 distinct values, the largest ratio between successive
  sorted counts exceeds `jmp`, and the counts above that jump sum to > peak_s × total. Flag if
  count(value | key) < outlier_s × size(key).
- **Mixture (`--mixture n threshold`, "Suggested values: 2, 0.3") [code]:** one GMM (n components) per
  hint pair; probability = w_c · (1 − erf(d/√2)) for the most responsible component c, d = distance with
  diagonal covariance; flag if < threshold. Broken on current scikit-learn (see above).
- **Output [code, ours]:** upstream CLI prints offending rows with ANSI-underlined fields; `-v` adds
  "Value 'v' (field) doesn't match feature 'name'", `-vv` model details, `--minimal` only row indices.
  The Raha/REIN fork writes `<input>-dboost_output.csv` with (row, column) pairs (row 0 = header).
  → **cell-level binary flags, no score**. A score would have to be derived in a reimplementation
  (e.g. max |x−μ|/σ over a field's features).
- **Parameters used by Raha [code, `raha/detection.py`]:** `-F , --statistical 0.5` plus 34 configurations:
  histogram with peak_s, outlier_s ∈ {0.1, 0.3, 0.5, 0.7, 0.9} (25) and gaussian with
  t ∈ {1.0, 1.3, 1.5, 1.7, 2.0, 2.3, 2.5, 2.7, 3.0} (9); each run is a feature ("strategy") for Raha.
- **Parameters used by REIN [code, `rein/detectors.py` l.1090–1160]:** the same `-F , --statistical 0.5`
  and the same 34-configuration grid (shuffled); **the configuration with the highest F1 against the ground
  truth is kept** (oracle selection – the paper calls it "random search"). Presets in
  `datasets_dictionary.py`: adult `histogram 0.1 0.7`, beers `histogram 0.9 0.3`; datasets with an empty
  preset list would index `config[0]` of an empty list (IndexError; code reading, not executed).
- **Compute:** not measured here beyond the 2,000-row probe (seconds). ZeroED and REIN describe dBoost as
  fast. **Limitations for our data:** expansion features of integers (timestamp, bits, mod 10) are
  meaningless for amounts/codes and add burden; histogram flags whole minority classes; types collapse to
  strings when a header is present; row discard/index shift on type errors; no score.

### 4. REIN

- **Paper:** Abdelaal, M., Hammacher, C., Schöning, H. "REIN: A Comprehensive Benchmark Framework for Data
  Cleaning Methods in ML Pipelines", EDBT 2023, pp. 499–511, DOI 10.48786/edbt.2023.43 (per references.bib;
  OpenProceedings), arXiv 2302.04702 (PDF read) **[V-full, Tables 1 and 4]**. The repo README cites PVLDB –
  wrong, as already noted in references.bib.
- **Repository:** https://github.com/mohamedyd/rein-benchmark @ b8a0727f. **No top-level LICENSE**; 16
  Python files under `rein/` and `scripts/` carry the header "Software AG / All Rights Reserved". Bundled
  third-party cleaners keep their own licences (dBoost GPL-3.0, FAHES, Picket, ED2, HoloClean, ZeroER,
  error-generator). → code cannot be reused; citing results is fine.
- **Detection methods (Table 1; "Cat. I" = non-learning, "II" = ML-supported):** KATARA (pattern
  violations; knowledge base), NADEEF (rule violations; FDs, patterns), FAHES (disguised missing values),
  HoloClean (denial constraints), dBoost (outliers; hyperparameters), OpenRefine (inconsistencies;
  clusters), IF / SD / IQR outlier detectors, MV detector, key collision and ZeroER (duplicates),
  CleanLab (mislabels), Min-K and Max Entropy (holistic ensembles), Metadata-driven, Raha, ED2 (labels),
  Picket (self-supervised). All except the duplicate detectors (row pairs) and CleanLab (labels) output
  erroneous *cells*; SD/IQR/IF are applied per attribute in REIN's `outlierdetector`.
- **Datasets (Table 4):** Beers 2,410×11 (MVs, rule violations, typos), Citation 5,005×2 (duplicates,
  mislabels), Adult 45,223×15 (rule violations, outliers; error rate 0.58), Breast Cancer 700×12, Smart
  Factory 23,645×19, Nasa 1,504×6, Bikes 17,378×16, Soil Moisture 679×129, 3D Printer 50×12, Mercedes
  4,210×378, Water 527×38, HAR 70,000×4, Power 1,456×24, Soccer 180,228×44.
- **Error origin:** only Beers and Citation have real errors with a clean version ("we collected two
  datasets… that satisfy these conditions"); for the others errors were **injected** with BART (denial
  constraints → rule violations, outliers, nulls, duplicates, mislabels) and the `error-generator` library
  (keyboard typos, implicit MVs, Gaussian noise, value swapping); FDs from the FDX profiler. The dataset
  dictionary notes "actual errors generated manually" for 3D Printer and "Actual errors detected manually"
  for Citation. Clean version = the original public dataset.
- **Data availability/licence:** not in the Git repository (no `datasets/` files tracked); README points to
  ResearchGate https://www.researchgate.net/publication/382496079_Datasets_of_REIN_Benchmark → HTTP 403
  here. No data licence stated. Original sources (UCI etc.) have their own licences. **UNVERIFIED/BLOCKED**.
- **Compute (paper):** Ubuntu 16.04, 32 × 2.60 GHz cores, 264 GB RAM; ten repetitions.

### 5. ZeroED

- **Paper:** Ni, W., Zhang, K., Miao, X., Zhao, X., Wu, Y., Wang, Y., Yin, J. "ZeroED: Hybrid Zero-Shot Error
  Detection Through Large Language Model Reasoning", ICDE 2025, pp. 3126–3139, DOI
  10.1109/ICDE65448.2025.00234 (Crossref) – **venue verified**; arXiv 2504.05345 (PDF read in part) **[V-full,
  §IV-A, Table II, Table V, §IV-C]**.
- **Repository:** paper → https://github.com/ZJU-Data-Governance-and-Services-Team/ZeroED @ 2b84266e; README
  says `git clone https://github.com/WelkinNi/ZeroED.git` (HEAD 49678b84). **No LICENSE** in either
  (raw 404; `git ls-files`: only the vendored `raha-master/LICENSE.md`, Apache-2.0, and dBoost GPL).
- **Runnable status [code]:** Python 3.10 (conda, README); no requirements file; `main.py` imports
  `from measure import measure_detect`, but no `measure.py` exists in the repository (also `measure_Sep9`
  in two scripts) → **not runnable as published** without reconstructing that module. Needs the fastText
  model `cc.en.300.bin` (~7 GB, downloaded separately; size UNVERIFIED) and an OpenAI-compatible endpoint
  (`utility.py`: model_name, base_url, api_key).
- **Method:** features per cell (error-reason-aware binary criteria generated by the LLM as Python
  functions, fastText embeddings, pattern/frequency statistics, correlated attributes by NMI) → LLM labels
  ~5% of cells selected by clustering (in-context, two-step reasoning) → label propagation within clusters
  + LLM-generated error augmentation with verification → 2-layer MLP classifier on all cells.
  **Output:** cell-level binary prediction (MLP probabilities exist internally; not exposed as a score in
  the README – UNVERIFIED).
- **LLM requirements:** default Qwen2.5-72B served with vLLM; also Llama3.1-8b/70b, Qwen2.5-7b; GPT-4o-mini
  via API only to assess runtime and token cost; temperature 0, max 4,096 output tokens, batches of 20
  tuples. Hardware: Intel Xeon Gold 6326, 3 × A40 GPUs, 512 GB RAM.
- **Cost:** the paper reports token cost only relatively ("up to 90% token cost reduction" vs. FM-ED;
  Fig. 8); no absolute USD/token numbers found in the text.
- **Datasets (Table II):** Hospital 1,000×20, Flights 2,376×7, Beers 2,410×11, Rayyan 1,000×11, Billionaire
  2,615×22 (errors injected with public code), Movies 7,390×17, Tax 200,000×22 (BART). Baselines needing
  labels got 2 labelled tuples. Data files are in the repo (`data/*_clean.csv`, `*_error-01.csv`).
- **Relevance:** LLM-labelled, transductive; needs GPUs or a paid API; sends data to an LLM – conflicts with
  the confidentiality setting of the use case unless run locally.

### 6. Raha and Baran

- Mahdavi et al., "Raha: A Configuration-Free Error Detection System", SIGMOD 2019, pp. 865–882, DOI
  10.1145/3299869.3324956; Mahdavi & Abedjan, "Baran: Effective Error Correction via a Unified Context
  Representation and Transfer Learning", PVLDB 13(11), 2020, DOI 10.14778/3407790.3407801 (references.bib).
- **Licence:** `LICENSE.md` = Apache License 2.0 (read); `setup.py` `license="Apache 2.0"`, version 1.26;
  PyPI `raha` 1.26, Apache 2.0, no `requires_python`.
- **Supervision:** `LABELING_BUDGET = 20` labelled tuples (user marks erroneous cells), clustering-based
  sampling, label propagation ("homogeneity"), GBC classifier per column; optional `HISTORICAL_DATASETS`.
  Base strategies: OD (dBoost, 34 configs), PVD (character-presence patterns), RVD (pairwise attribute
  FD-like checks), KBVD (KATARA-style knowledge base in `supplementaries/knowledge-base`, ~2,000 relation
  files). Baran: same 20-tuple budget for corrections; optional pre-trained value models from Wikipedia
  revision histories.
- **Output:** dict of detected cells (binary); Baran: dict of corrected values. No scores.

### 7. Isolation Forest

- Liu, F. T., Ting, K. M., Zhou, Z.-H. "Isolation Forest", 2008 Eighth IEEE International Conference on Data
  Mining (ICDM), pp. 413–422, DOI 10.1109/ICDM.2008.17 (Crossref) – confirmed.

---

## BENCHMARKS

### a. Raha/Baran dirty–clean datasets (new information only)

- The same family is now the common benchmark of *all* recent unsupervised/LLM detectors checked here:
  LUCARIO (beers, flights, hospital, HOSP-10K, HOSP-100K, movies_1), RIOLU (hosp 1k/10k/100k, flights,
  movies), ZeroED (hospital, flights, beers, rayyan, movies, billionaire, tax), Auto-Test (adults, beers,
  flights, food, hospital, movies, rayyan, soccer, tax) – published numbers on them are comparable only
  if the same dirty/clean files and label definition are used (LUCARIO and RIOLU use *modified*
  versions with their own ground truth files).
- ZeroED's own provenance statements: Beers cleaned manually; Movies from the Magellan repository, cleaned
  with duplicate-tuple labels; Rayyan cleaned by its original owners; Tax synthetic from BART;
  Billionaire errors injected by the authors.
- ZeroED's error-type rule (T: edit distance ≤ 3; PV: format unseen in clean data; O: errors with < 1%
  frequency) shows that "outliers" in these benchmarks are rare *strings*, not numeric value errors.
- Nothing changes the earlier verdicts (Flights only for Raha-type; Tax only as out-of-generator probe).

### b. REIN datasets

- See §4 for sizes and origins. Numeric-heavy tables (Nasa 6 num., Smart Factory 19 num., Bikes 16 num.,
  Breast Cancer 12 num., Water 38, Power 24, Soil Moisture 129, Mercedes 370+8, HAR 3+1) contain
  **injected** outliers/Gaussian noise/MVs (BART + error-generator) that CDC- and dBoost-type detectors
  are designed for; Adult 7 num. + 8 cat. is the closest to Bank Marketing in shape.
- Reference reliability: clean = original public data; labels by construction (cell diff) – reliable
  for "what was injected", but it is a *third* synthetic generator, not real errors.
- Two detectors comparable: yes in principle (CDC and dBoost/IF on the same dirty file with a clean
  reference split by rows); selection/test separation possible by row split. **But** files are only on
  ResearchGate (403), no data licence, and REIN's own dBoost numbers are oracle-tuned. → at most a
  separate out-of-generator track, after manual download and licence check.

### c. Auto-Test (Chen, He, Wong, Cui, Ge, Zhang, Zhang, Chaudhuri)

- "Auto-Test: Learning Semantic-Domain Constraints for Unsupervised Error Detection in Tables", PACMMOD
  3(3), pp. 1–27, 2025 (SIGMOD 2025), DOI 10.1145/3725396; arXiv 2504.10762 (PDF read in part)
  **[V-full §6.1]**. A SIGMOD 2025 reproducibility report exists: DOI 10.1145/3785021.3788000 (Crossref
  metadata only).
- **Benchmarks:** ST-Bench = 1,200 columns randomly sampled from real spreadsheets (.xlsx crawled from the
  web), 47 (3.9%) with real errors; RT-Bench = 1,200 columns from relational tables in BI models (.pbix
  crawled from the web), 40 (3.3%) with errors. "Each column is carefully labelled and cross-checked by
  human-labellers" – **manual labels**; fields `ground_truth` (unambiguous errors),
  `ground_truth_debatable`, `dist_val` (distinct values), `dist_val_count` (benchmarks/benchmark_readme.md).
- **Unit = single column of distinct values**: no rows, no other columns, no frequencies. **[ours, quick
  parse]** ST-Bench: 56/1,200 columns are >90% numeric, 2 of them dirty; the RT-Bench CSV is padded to
  1,048,575 rows (Excel artefact), 40 dirty columns. Errors are semantic-domain violations (misspelt
  months, country in a state column, text in a date column).
- **Availability/licence:** benchmark CSVs in the GitHub repo; training corpora and models on Google
  Drive. **No LICENSE file** in the repo (raw 404, `git ls-files`: only vendored sherlock/doduo licences);
  the paper text is CC BY 4.0, which does not cover code or data. Crawled third-party content – data
  redistribution rights UNVERIFIED. Offline training 120–200 h on 64 cores (README).
- **Fit:** CDC (needs other columns of the same row) and dBoost (needs rows) cannot run meaningfully;
  only single-column pattern/domain detectors (LUCARIO/RIOLU, Auto-Test). Not a financial value-error
  benchmark.

### d. AddressTable / "Clean Me If You Can" (Ahmadi, Bernhard, Abdelmaksoud, Zecchini, Rabl, Abedjan)

- arXiv 2606.31983 v2 (2026-07-01) **[V-full §4]**; repo https://github.com/D2IP-TUB/Clean-Me-If-You-Can.
- **New:** repo LICENSE = **MIT** for code (read, "Copyright (c) 2026 Fatemeh Ahmadi, …"); README:
  "Ground-truth data derived from OpenStreetMap is licensed under ODbL 1.0"; data on Zenodo
  https://zenodo.org/records/20841898 (earlier probe: CC BY 4.0 on Zenodo) → code MIT, ground truth ODbL
  (share-alike obligations for derived databases).
- **Labelling:** ground truth = Nominatim geocoder response per dirty record, then validation and
  normalisation scripts (libpostal parsing, Unicode canonicalisation, locality fixes); Nominatim matched
  96.5% of dirty addresses with high confidence; a random 1k sample agreed 99.1% with the Google Address
  Validation API (agreement between two geocoders, not manual verification of the labels).
- Earlier verdict unchanged: string-only, standardisation-dominated → not for CDC/dBoost value errors.

### e. TableEG Credit

- **Primary source:** Liu, X., Chen, J., Hu, B., Sun, Y., Chen, X., Song, S., Tong, Y. "Towards Practical
  Benchmarking of Data Cleaning Techniques: On Generating Authentic Errors via Large Language Models",
  arXiv 2507.10934 v3 (2026-03-09); paper text licence CC BY-NC-ND 4.0; venue **UNVERIFIED**. Repo
  https://github.com/viviancircle/TableEG @ ea889b80 – **no LICENSE**; datasets and LoRA weights only on
  Google Drive (not fetched). TableEG = LLaMA-3.1-8B LoRA fine-tuned to generate/detect/correct errors.
- **Credit in TableEG Table 1:** 150,000 rows × 10 attributes, Finance, error rate 2.33%, types M
  (missing) and O (outliers); "credit records with attributes such as income, age, and number of
  dependents… missing values in financial attributes and numerical outliers due to extreme income values".
- **Provenance:** this matches Kaggle "Give Me Some Credit" (150,000 rows, 10 features + target – from
  memory, Kaggle page not checked, UNVERIFIED), the
  `Credit` dataset of CleanML (Li et al., ICDE 2021; `schema/dataset.py`: error_types outliers,
  missing_values, label `SeriousDlqin2yrs`), which TableEG cites [32]. The identification is a
  **provisional inference** (TableEG does not name the source in the text read).
- **Error labels:** the dirty file contains the *original* missing values and extreme incomes; the
  "clean" version must have been produced by some cleaning (imputation/outlier repair) – how is not
  stated in the paper text read; the TableEG README describes `dirty.csv` as "the corrupted version of
  the dataset with injected errors". Earlier pilot in this project: labels are imputations
  (dataset_qualification.md). → labels are **not** verified corrections; not LLM-generated for the source
  set, but derived values. UNVERIFIED in detail (Drive not accessed).
- **Connection with UCI Credit (Yeh & Lien, Taiwan, 30,000 × 24):** none found – different population,
  size and attributes; **no data leakage** risk for our UCI Credit experiments. Indirect risk only if
  TableEG's fine-tuned generator were used to create errors for UCI Credit (it was trained on Credit/
  Marketing error patterns; "Marketing" in TableEG is an 8,993 × 14 household-income survey, not UCI Bank
  Marketing).

### f. BART (Arocena, Glavic, Mecca, Miller, Papotti, Santoro)

- "Messing Up with BART: Error Generation for Evaluating Data-Cleaning Algorithms", PVLDB 9(2):36–47, 2015,
  DOI 10.14778/2850578.2850579 (PDF read, vldb.org) **[V-full §1, §7–8]**; paper text CC BY-NC-ND 4.0.
- **Repository:** https://github.com/dbunibas/BART @ 354f503f (2023-05-10), tag `1.0`. **LICENSE: MIT,
  "Copyright (c) 2015 dbunibas"** (read).
- **Requirements:** Java (NetBeans/Ant projects, `javac.source=1.7`), PostgreSQL ≤ 11 ("Starting from
  version 12, PostgreSQL removed support for OID generator") or H2; tasks configured in XML (`./run.sh
  <egtask.xml>`); a GUI installer under releases. Java is available in this container (`/usr/bin/java`);
  not executed.
- **Error types:** constraint-induced (detectable) errors for denial constraints (FDs, CFDs, ordering
  constraints, master-data), with control of detectability (exactly-one/at-least-one) and estimated
  repairability; plus random errors: typos (operators TypoActiveDomain/AddString/AppendString/Random/
  RemoveString/SwitchValue), duplicated values, bogus/null values ('999', '***'), outliers
  (`OutlierValueSelector`), partial-order errors.
- **Benchmarks in the paper:** Employees, Customers, Tax (synthetic, Fan et al.), Bus and Hospital
  (real-world scenarios used in repair papers); the repository ships only `employees`, `customers` and
  `similarity` resources; Tax/Hospital dirty files circulate via Raha/Baran (see dataset_qualification.md).
- **Fit for numeric financial tables:** BART's strength is DC violations in FD-rich tables; UCI Credit and
  Bank Marketing have few exact FDs (Bank: macro-indicator FDs only). Its outlier and typo operators
  would be a second, independent generator for an *out-of-generator* robustness check of our tab_err
  scenarios, at the cost of a Java + PostgreSQL 11 setup. Errors are synthetic by construction.

---

## Recommendation per item

| Item | Recommendation | One-line reason |
|---|---|---|
| CDC (original + re-implementation) | **USE** | Unsupervised, reference-trained, cell-level; MIT; runs (Py 3.9 env); already qualified with documented conditions |
| LUCARIO | **USE AS SEPARATE TRACK** (clean-room reimplementation) | Simple, fully specified rules (median±3·MAD with 5% drop, frequency-jump categories, regex) but no code licence and paper full text unread; numeric check will mostly switch itself off on credit amounts |
| RIOLU | **DOCUMENT ONLY** | MIT, but pattern detector for string columns; our financial tables are integer/categorical codes |
| dBoost | **USE** (clean-room reimplementation of gaussian + histogram; GPL code only as fidelity reference) | Classic unsupervised cell-level baseline in Raha/REIN/ZeroED; algorithm fully specified above; `--train-with` allows reference/test separation; no score and header/typing pitfalls must be handled |
| REIN (framework) | **DOCUMENT ONLY** | "All Rights Reserved" code, oracle-tuned dBoost; useful as related-work evidence |
| ZeroED | **BLOCKED** | No licence, `measure.py` missing, needs 72B LLM on GPUs or external API (confidentiality), transductive |
| Raha / Baran | **USE AS SEPARATE TRACK** | Apache-2.0, runs; needs 20 labelled tuples – different supervision, only informative on Flights-type data |
| Isolation Forest | **USE** | Row-level reference baseline; citation confirmed (ICDM 2008, DOI 10.1109/ICDM.2008.17) |
| a. Raha/Baran datasets | **USE AS SEPARATE TRACK** (as already decided) | Real/BART errors but non-financial; shared benchmark of LUCARIO/RIOLU/ZeroED/Auto-Test |
| b. REIN datasets | **BLOCKED** (possible later separate track) | Mostly injected errors; files only on ResearchGate (403); no data licence |
| c. Auto-Test ST/RT-Bench | **DOCUMENT ONLY** | Manually labelled real errors, but single-column distinct-value lists; no licence; CDC/dBoost not applicable |
| d. AddressTable (Clean Me If You Can) | **DOCUMENT ONLY** | Code MIT, GT ODbL; geocoder-derived truth; string standardisation, not value errors |
| e. TableEG Credit | **DOCUMENT ONLY** (rejected as benchmark) | = Give Me Some Credit via CleanML (provisional); labels are cleaned/imputed values, not verified; no link to UCI Credit, no leakage |
| f. BART | **DOCUMENT ONLY** (optional out-of-generator track) | MIT, but Java 7 + PostgreSQL ≤11; strongest for FD/DC errors that our tables barely have |
