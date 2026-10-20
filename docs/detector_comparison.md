# Detector research and comparison matrix (pilot candidates)

Status: 2026-10-20. Sources were read in this session from primary material (papers, official repositories at
the commits listed, LICENSE files); research notes with every URL checked are in
`docs/sources/detector_benchmark_research_notes.md`. Markers: **[lit]** from the paper or repository,
**[code]** read in the repository at the given commit, **[ours]** measured in this repository
(`scripts/qualify_pilot_detectors.py` → `results/qualification/pilot_detector_qualification.json`, pilot runs
→ `results/pilot/`). Licence statements are not legal advice.

## 1. Requirements per method

| Method | Designed for (error types) | Learns from | Labels / external knowledge | Output | Score? | Dependencies / licence | Runnable here | Limits on our data |
|---|---|---|---|---|---|---|---|---|
| **CDC** – Jäger & Biessmann, AISTATS 2024 (PMLR 238:3394–3402); se-jaeger/conformal-data-cleaning @fd8a2126 | JENGA corruptions (swaps between columns, scaling, Gaussian noise, categorical shift), injected completely at random [lit] | clean(ish) historical data; one model per column + ~1,000 calibration rows | none | cell | original: flags only; our re-implementation adds conformal p-values (ranking) | original: Python 3.9, AutoGluon 0.8.2, MIT (+ conformal-inference Apache-2.0) [code] | original in `envs/cdc_aistats` (flags), re-implementation `cdc_hgb` in the main env | rare labels below 1/(1−c) calibration examples; strict `<` set rule of the original; documented in `method_compatibility.md` |
| **dBoost** – Pit-Claudel, Mariet, Harding & Madden, MIT-CSAIL-TR-2016-002; cpitclaudel/dBoost @a47cb564 | outliers in heterogeneous tuples after automatic *tuple expansion* (dates, bits, mod/div, string signatures) [lit, code] | the data it analyses (default) or a separate training file (`--train-with`) | user-chosen model parameters (no labels); Raha/REIN tune 34 configurations, REIN selects by F1 **against the ground truth** (oracle) [code] | cell (fields of a tuple) | **no – binary** | pure Python 3; **GPL-3.0** [code]; mixture model broken on scikit-learn ≥ 0.20 | original via child process (`envs/dboost`, GPL runner, not imported); clean-room re-implementation `dboost` (**100 % cell agreement** with the original on Credit samples, all three models) [ours] | first-row typing; rows that do not parse are silently dropped (type-changing errors invisible); the original **crashes** on Bank Marketing float columns (one-pass variance → `math domain error`) [ours]; bit/date features of amounts produce very high alert rates |
| **LUCARIO** – Qin, Li & Merlo, *Inf. Softw. Technol.* 192 (2026) 108035, DOI 10.1016/j.infsof.2026.108035 (OA CC BY 4.0; full text not retrievable here) | pattern (regex) anomalies and categorical / numerical outliers, unsupervised, cell level [lit: abstract] | the batch under test (transductive) | none | cell | **no – binary** | replication repo mooselab/Detect-Cell-level-Data-Anomalies-With-LUCARIO @3664bfa8 has **no licence** → not copied, not executed | partial clean-room re-implementation `lucario_core` (numerical median ± 3·MAD with the 5 % switch-off rule, categorical frequency-jump rule, type rule; **no** regex patterns) – **provisional** | numeric check switches itself off for skewed/zero-inflated amounts (> 5 % outside the range); built and evaluated on string-heavy Raha/Baran data |
| **REIN SD / IQR outlier detectors** – Abdelaal, Hammacher & Schöning, EDBT 2023 (arXiv 2302.04702) | univariate outliers per numeric attribute [lit] | the dirty dataset (transductive) | none | cell | no – binary | REIN code "Software AG – All Rights Reserved", no licence → **not reused**; textbook rules re-implemented (`sd_outlier` n = 3, `iqr_outlier` k = 1.5) | yes | numeric columns only; overlap with the statistical baseline (envelope on reference data) by construction |
| **Isolation Forest** – Liu, Ting & Zhou, ICDM 2008, DOI 10.1109/ICDM.2008.17 | global (joint) outliers | historical data | none | **record** | yes (path length) | scikit-learn, BSD-3 | yes (`iforest_row`) | record level only: compared on a separate record track |
| **Raha** – Mahdavi et al., SIGMOD 2019; BigDaMa/raha 1.26 | configuration-free ensemble of OD/PV/RV/KB strategies | the batch under test | **20 labelled tuples** from the batch (simulated from ground truth) | cell | no – binary | Apache-2.0; Python 3.9 env | yes (earlier qualification) | needs labels from the batch → different information regime; not informative at 1–2 % single-column errors (0 erroneous cells labelled) |
| **ZeroED** – Ni et al., ICDE 2025, DOI 10.1109/ICDE65448.2025.00234 (arXiv 2504.05345) | typos, pattern violations, outliers, rule violations via LLM-generated criteria + label propagation | the batch | **LLM** (Qwen2.5-72B on 3×A40, or an API), fastText model | cell | internal MLP probabilities, not exposed | **no licence**; `main.py` imports a missing module `measure` [code] | **blocked** | sends data to an LLM (confidentiality); not runnable as published |

RIOLU (ICSE 2025, MIT) is the pattern-inference predecessor of LUCARIO for string columns; not applicable to our
typed numeric/code columns (document only). Baran, HoloClean, NADEEF, KATARA, Picket, ED2 need constraints,
knowledge bases or labels and were not qualified.

## 2. Which comparisons are fair

| Track | Candidates | Same information? | Metric |
|---|---|---|---|
| **Cell track, reference-trained** | `cdc`, `dboost_gaussian`, `dboost_gaussian_text`, `dboost_histogram` | yes: same reference partition, no labels, same contract | ranked dR@k for CDC; budget-capped flag dR@k for binary methods; flag precision/recall/burden for all |
| **Cell track, batch-learned (transductive)** | `dboost_gaussian_batch`, `lucario_core`, `sd_outlier`, `iqr_outlier` | they use the *unlabelled batch under test*, which is available in practice; difference recorded as `fit_scope = batch` | as above |
| **Record track** | `iforest`, CDC aggregated to records (`cdc@row`) | reference partition | record recall, record dR@k (records per 1,000 rows) |
| **Few-label track** | Raha | uses 20 labelled tuples of the batch | reported separately (earlier qualification), never ranked against the others |

Rules applied throughout: no candidate sees injected test errors, clean versions or test scenarios; record-level
and cell-level scores are never compared; **no ranking score is constructed for binary methods** – they are
evaluated with their own flags, and at a fixed review budget with the *expected* yield of reviewing their extra
flags in random order (`dR_flags@k = hits × min(1, k / n_extra_flags) / n_injected`), which is valid for every
method. The selection utility is the ranked dR@k when the method publishes a ranking and the flag dR@k otherwise.

## 3. Configurations (fixed before the pilot, decision D-22)

Published defaults or suggested values only: CDC as frozen in the earlier qualification (c = 0.999, HGB 100
iterations, normalised-residual ranking); dBoost `--gaussian 3` and `--histogram 0.8 0.2` (help-text suggested
values) with `--statistical 0.5` (the analyzer setting Raha and REIN use); dBoost in typed mode and in the
text mode that Raha/REIN effectively use (CSV with header → every field a string); LUCARIO k = 3 MAD, coverage
0.95; SD n = 3; IQR k = 1.5. No configuration was tuned on pilot results. A configuration grid (e.g. Raha's 34
dBoost settings) is a possible extension: selecting among more configurations on synthetic scenarios increases
the risk of a winner's curse, which is exactly what selection regret measures.

## 4. Measured qualification (pilot seed 11, reference vs untouched selection partition) [ours]

See `results/qualification/pilot_detector_qualification.json`; summarised in
`docs/comprehensive_pilot_report.md` §3 (compatibility, runtime, memory, alert rates, dBoost fidelity).
