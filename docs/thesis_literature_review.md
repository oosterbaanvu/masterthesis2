# Literature-driven qualification for the integrated MSc pilot

Date: 2026-10-21. This extends, rather than replaces, `literature_review.md`, `references.bib`,
`detector_comparison.md` and `sources/detector_benchmark_research_notes.md`. Those documents record
which papers were read in full, abstract only or metadata only. No new full-paper access is implied
by reusing an existing verified reference. Current repository/licence checks are saved in
`results/thesis_integrated/literature_sources.json`.

## Research question and closest work

How reliably can controlled error injection guide the selection of cell-level error detectors that
add detection value beyond conventional data-quality checks? The question concerns a *decision*,
not a claim that one detector wins on every error population.

CDC (Jäger & Biessmann, AISTATS 2024, PMLR 238:3394–3402) predicts a field from other attributes and
uses conformal calibration. It demonstrates detection/cleaning under generated corruption, but does
not by itself establish the reliability of selecting an addition to an existing rule suite under
source/family/mechanism shift. Our HGB implementation changes the base learner and adds ranking;
it is not the original AutoGluon implementation.

dBoost (Pit-Claudel et al., MIT-CSAIL-TR-2016-002, 2016) learns distributions over expanded tuple
features. This is a substantively different statistical model from CDC, but is not another deep
predictive learner. Its original native outputs are binary; the repository's Gaussian statistic
ranking is an explicitly documented extension. Typed/text modes are configurations of **one** method.

REIN (Abdelaal, Hammacher & Schöning, EDBT 2023, DOI 10.48786/edbt.2023.43; arXiv 2302.04702) studies
cleaners and downstream ML with different data, error and supervision conditions. Raha (Mahdavi et al.,
SIGMOD 2019, DOI 10.1145/3299869.3324956) learns from actively labelled tuples; its accuracy cannot be
treated as a no-label competitor's accuracy. Jung et al., *Towards Realistic Error Models for Tabular
Data* (JDIQ, DOI 10.1145/3774914), motivates distinct placement mechanisms. Plausible error type and
placement mechanism remain separate experimental factors.

Synthetic-anomaly-based model selection is already studied: SWSA (arXiv 2310.10461; abstract-qualified
in the existing review) and AutoAnoEval (Findings EACL 2026; existing review) are close conceptual
antecedents. Unsupervised model-selection studies, ADBench, MetaOD and the algorithm-selection literature
already address rankings, no universal winner and regret. We do **not** claim invention of simulation
selection, robust optimization, conformal cleaning or ECAR/EAR/ENAR. Exact bibliographic records and
verification status remain in `references.bib`.

The defensible candidate contribution is an empirical evaluation of *incremental cell-review utility
and selector reliability conditional on a conventional rule suite*, with a shared total alert budget,
no-addition/abstention options, explicit information tracks and carefully qualified published references.
It becomes an MSc contribution only if the experiment exposes meaningful, reproducible decision
failures or conditions, not merely if a favoured method obtains a positive score. A systematic novelty
check against selective editing and anomaly-model selection remains necessary before a priority claim.

## Qualification matrix

| Candidate / reference | Output and contribution | Permitted information | Data/error scope | Code, licence and compute | Fixed cell-budget decision |
|---|---|---|---|---|---|
| CDC, AISTATS 2024 | Per-cell predictive nonconformity | Unlabelled, presumed high-quality history + calibration; no error labels | Numeric/low-cardinality codes; unpredictable text/rare classes problematic | MIT original; AutoGluon 0.8.2/Python 3.9 isolated. Existing HGB reimplementation qualified, CPU | Primary HGB configuration; ranking extension explicit; not original-model fidelity claim |
| dBoost, TR 2016 | Expanded-field distribution anomalies | Same unlabelled historical rows; no clean test values | Mixed text/numbers; typing and parse failures materially affect coverage | Original GPL-3.0, clean-room adapter already qualified; CPU, fast | Primary Gaussian typed and text configurations, counted as one method family |
| LUCARIO, IST 192 (2026) 108035, DOI 10.1016/j.infsof.2026.108035 | Cell pattern/type/range/category constraints | Native transductive dirty table, no labels | Text patterns, numeric/category outliers | Full paper previously inaccessible; repository has no top-level licence. Full pattern method not reproduced | Existing **partial/provisional** LUCARIO-core only as separately labelled historical secondary evidence; no faithful-full claim |
| Picket, VLDB J. 31 (2022) 927–955, DOI 10.1007/s00778-021-00699-w | Self-supervised attribute reconstruction; training filtering and inference victim detection | Training-time self-supervision; inference pipeline uses artificial corruption, downstream class/victim information | Tabular corruption during learning/inference; published operational filters protect records/predictions | Official `sis-ethz/Picket` MIT, commit in source snapshot. README: PyTorch 1.0.1, pandas 0.23.4, sklearn 0.22.1, gensim 3.8.1, isolated old environment | Per-attribute internal losses are not automatically a qualified cell-error budget interface. No faithful adapter/fidelity test established; excluded, not assigned zero |
| HoloDetect, SIGMOD 2019, DOI 10.1145/3299869.3319888 | Few-shot cell classifier with learned augmentation | Labelled seed errors/augmentation; different supervision from primary track | Missing, typo, constraint/representation errors | `abmohajeri/holodetect` found; no repository licence declared; spaCy-era dependencies | Separate few-label track; not silently label-free |
| Raha, SIGMOD 2019 | Cell classifier, strategy features, active labelling | Common experiments use 20 labelled tuples, external strategy knowledge | Dirty/clean text benchmarks and cross-attribute patterns | Apache-2.0; existing isolated adapter, CPU but many strategy configurations | Separate few-label track; do not give labels to it then compare as equal information |
| ZeroED, ICDE 2025, DOI 10.1109/ICDE65448.2025.00234 | LLM criteria/labels + representation classifier | LLM labels, external semantics/fastText; GPU/API stack | Mixed benchmark cell errors | Repository no top-level licence; earlier missing module, ~7 GB fastText, large model/GPU. No paid calls used | Separate LLM/external-knowledge track, not executed here |
| RIOLU, ICSE 2025, DOI 10.1109/ICSE55347.2025.00078 | Learned/inferred string templates | Auto mode unlabelled; guided mode uses cleaned examples | Text format/pattern violations, not broad numeric value errors | MIT repository; prior source review in research notes | Potential format-only follow-up; not another qualified numerical learned detector |
| SD/IQR | Univariate numerical thresholds | Historical rows in this study | Present numerical extremes, not missing/category/text errors | Existing textbook adapters, CPU | IQR reference mode is a binary secondary control; fixed random tie ordering, no fabricated ranking |
| Isolation Forest | Record score | Unlabelled historical rows | Multivariate record anomalies | Existing sklearn adapter | Record-level track only; no projection of a row flag into cell accuracy |
| ED2 / SAGED | Active learning / meta-selection | Error annotations / labelled historical datasets | Cell detection and cross-dataset knowledge | Existing review; not newly reproduced | Information conditions differ; document as related work, not equal-information primary candidates |

## Checks performed for this task

GitHub metadata, README files and the Picket filter implementation were read without copying source into
the project. Picket's `filtersTrain.py` uses reconstruction/filtering machinery; `filtersTest.py`
constructs victim/safe training labels around downstream correctness and artificial noise. Exposing its
internal attribute losses as a new label-free detector would be a methodological adaptation needing
its own validation. We do not label such an adaptation a reproduced published cell detector.

The current LUCARIO repository root lists inference/detection code and datasets but no licence. Its
published article's OA licence does not automatically license repository source. HoloDetect's README
contains only legacy dependency instructions; licence metadata is absent. Absence of metadata is not
a legal conclusion, but it is insufficient reproducibility evidence to copy that code. No verification,
TLS or package-signature checks were disabled, and no paid models or external compute were used.

## Chosen comparison and limitation

The primary track has **three configurations from two method families**: CDC-HGB, dBoost-Gaussian typed
and dBoost-Gaussian text. All receive the same historical rows and source-contract features without
error labels. IQR-reference is a distinct binary secondary baseline. We did not qualify 3–4 independent
learned cell detectors or two independent expressive learned systems under equal information.
That limitation narrows the claim to these implementations; it is preferable to inflating the method
count with dBoost variants, an incomplete LUCARIO or record-level Picket outputs. Further full-method
qualification is a condition for a broader confirmatory comparison, not unfinished work disguised as
a positive empirical result.
