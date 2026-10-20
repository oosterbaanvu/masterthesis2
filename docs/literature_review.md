# Literature review

Status: draft for supervisor review, 2026-10-19. Bibliographic data is in [`references.bib`](references.bib); every
entry has a `note` that states how it was verified. Verification markers used below:

- **[V-full]** relevant full-text passages read; **[V-abs]** official abstract read; **[V-meta]** only
  metadata/title verified (content claim must be checked before citing); **UNVERIFIED** could not be confirmed.
- Statements about *code* (marked **[code]**) were checked by reading the published repositories at the
  commit hashes given in `docs/method_compatibility.md`. Statements marked **[ours]** are our own
  measurements in this repository.

The review is organised around the questions in the project brief rather than per paper.

---

## 1. Conventional data-quality controls in practice

**Declarative data unit tests and constraint suggestion.** Deequ (Schelter et al., PVLDB 11(12), 2018)
[V-abs] expresses data quality as declarative constraints ("unit tests for data") executed at scale, adds
constraint *suggestion* from profiles and anomaly detection on time series of quality metrics. TFDV
(Breck/Polyzotis et al., MLSys 2019) [V-meta] validates ML input data against an inferred schema. dbt's
generic tests (`not_null`, `unique`, `accepted_values`, `relationships`) and custom SQL tests are the
practitioner equivalent; they are the control family the industry contact described (schema, mandatory
fields, business rules, referential integrity, thresholds, reconciliation).

**Learned validation rules.** Auto-Validate (Song & He, SIGMOD 2021) [V-meta], Auto-Validate-by-History
(Tu et al., KDD 2023) [V-abs] and Auto-Test (Chen et al., SIGMOD 2025) [V-abs] learn validation
constraints from data lakes or pipeline history; Auto-Test learns semantic-domain constraints that
functional dependencies cannot express. Redyuk et al. (EDBT 2021) [V-full] and GATE (Shankar et al., CIKM
2023) [V-abs] learn to accept or reject whole *batches* from batch statistics and report that learned
validators match or beat hand-tuned Deequ/TFDV baselines. These works compare learned validation **instead
of** rules, mostly at batch level; none measures the value of a learned *cell-level* detector **on top
of** an existing rule suite.

**Financial institutions.** BCBS 239 (Basel Committee, 2013) [V-meta; principle wording via a secondary
source, must be quoted from the BIS PDF] requires accurate, reconciled and validated risk data; it is a
supervisory standard, not law. Central banks have reported ML-based plausibility checks as a complement to
rule-based validation:

- ECB Statistics Paper 41 (Romano et al., 2021) [V-full] searched for *new* plausibility checks on
  supervisory data and explicitly excluded variables already covered by EBA validation rules; a first run
  without the exclusion rediscovered the rules. Evaluation was by expert review of top-ranked findings.
- Bank of Italy (Zambuto 2021 [V-abs]; Cusano et al., Quality & Quantity 2022 [V-meta]; Continanza et al.
  2023 [V-abs]) used quantile regression forests and stacked models, and revision histories as a source
  of real error labels.
- Bank of Thailand (Yodpinyanee et al., IFC Bulletin 66, 2026) [V-full] describes anomaly detection as a
  "second line of defense" after format/range/consistency rules and measures recall with each detector
  limited to flagging 10% of records, on analyst-defined anomaly themes.

These are the closest domain analogues to our question. They are case studies with expert or
analyst-defined labels; none runs controlled experiments that vary error type and mechanism and measures
the *incremental, budgeted* recall over the rule suite.

## 2. Cell-level error detection methods

| Method | Supervision | Output | Key assumption / requirement | Code status |
|---|---|---|---|---|
| Rule/constraint-based (NADEEF, HoloClean's DCs; Rekatsinas et al., PVLDB 2017 [V-abs]) | rules | cells in violations | correct, complete constraints; REIN shows HoloClean F1 drops from 0.51 to 0.12 when going from 17 to 7 rules [V-full, REIN] | various |
| dBoost (Pit-Claudel et al., MIT TR 2016) [V-meta] | none | cells | statistical models of expanded tuples | inside Raha |
| Raha (Mahdavi et al., SIGMOD 2019) [V-abs] | ~20 labelled tuples | cells | errors visible to a library of configured base detectors; labelled tuples must contain errors | BigDaMa/raha 1.26, Python 3.9–3.10 [code] |
| HoloDetect (Heidari et al., SIGMOD 2019) [V-abs] | few labels + learned augmentation | cells | augmentation policy learned from labelled errors | — |
| ED2 (Neutatz et al., CIKM 2019) [V-abs] | active learning | cells | label budget | — |
| Picket (Liu et al., VLDB J. 2022) [V-abs] | self-supervised | cells/rows | corruption at training/test time | — |
| **Conformal Data Cleaning (CDC)** (Jäger & Biessmann, AISTATS 2024, PMLR 238:3394–3402) [V-abs, code] | none, but **clean training data** | cells | per-column predictive model + split conformal sets/intervals; ~1000 calibration rows | se-jaeger/conformal-data-cleaning, Python 3.9, AutoGluon 0.8.2 [code] |
| SAGED (Abdelaal et al., EDBT 2024) [V-meta] | few labels + historical datasets | cells | meta-learning from similar historical datasets | mohamedyd/SAGED, no licence file [code] |
| ZeroED (Ni et al., ICDE 2025; arXiv 2504.05345) [V-meta] | LLM reasoning + classifier | cells | LLM access | — |
| LUCARIO (Qin, Li, Merlo, IST 2026) [V-meta; abstract via snippet] | none | cells (pattern/outlier) | inferred cell-level constraints; reported to beat Deequ, TFDV, Auto-Test | not inspected |

Two findings from this literature shape the design:

1. **No single detector dominates and detector families match error types.** Abedjan et al. (PVLDB 9(12),
   2016) [V-full] ran eight tools on five real datasets: outlier tools caught shifted values, rule tools
   caught inconsistencies, transformation tools caught formatting errors; the union of all tools raised
   recall at a large precision cost (e.g. 97% recall at 24% precision on one dataset). They also report
   each tool's contribution to the combined recall, an early *marginal-value* analysis, and warn that tools
   "are much more effective on the synthetic BlackOak data" than on real data, recommending that future
   work "should not use synthetic faults".
2. **Benchmarks reward the error population, not only the method.** REIN (Abdelaal et al., EDBT 2023)
   [V-full] found learned/ensemble detectors usually better than non-learning ones, but inconsistently
   across datasets; rule-based detectors depend strongly on rule quality.

CDC is the most suitable learned candidate for the financial use case because it trains on a validated
history (reference partition) and scores a new batch, which matches recurring loads. Its paper evaluates
only completely-at-random errors (JENGA default sampling, [code]) and has no rule-based or statistical
baseline. Raha fits a different setting (transductive, user labels).

## 3. Error generation and error mechanisms

**Error generators.** BART (Arocena et al., PVLDB 9(2), 2015) [V-abs] generates constraint-aware errors with
control over detectability; JENGA (Schelter, Rukat & Biessmann, EDBT 2021) [V-meta] introduced
CAR/AR/NAR-style row sampling for corruptions; tab_err (calgo-lab; PyPI 0.2.1, 2025-12-17) [code]
implements the error model of Jung et al.

**ECAR / EAR / ENAR.** Jung, Jäger, Chandler & Biessmann, "Towards Realistic Error Models for Tabular
Data", ACM JDIQ 17(4), article 28, 2025, DOI 10.1145/3774914 [V-abs; **full text not readable from this
environment, so the formal definitions are UNVERIFIED**]. The abstract extends Rubin's missing-data theory
to general tabular errors, decouples error sampling (mechanism) from error type and "demonstrate[s] the
impact of realistic error models on data cleaning benchmarks". Verbal definitions by the same authors:
ECAR – errors independent of the data; EAR – errors in one column depend on the values of another column;
ENAR – errors depend on the value itself (tab_err documentation; CURED Table 1) [V-full for these
documents]. CURED's §2.4 describes ENAR as depending on "unobserved other data", which is inconsistent
with its own Table 1. **Action for the student:** obtain the open-access PDF via institutional access and
quote §3 verbatim before the definitions are used in the thesis.

**How tab_err implements the mechanisms** [code; ours]. ECAR samples uniformly. EAR sorts the eligible rows
by the conditioning column and corrupts **one contiguous block** of the sorted order at a uniformly random
start; ENAR does the same on the column's own values. The dependence is therefore a "hard window", and which
value region is hit is a random function of the seed. Our validation (docs/error_injection_validation.md)
adds two consequences not documented upstream: ties in a low-cardinality conditioning column are broken by
(approximately) file order, and the error mask counts cells whose value did not change.

**Mechanism detection.** MechDetect (Jung et al., arXiv 2512.04138, DSIS 2025) [V-full] infers from an error
mask whether errors are MCAR/MAR/MNAR-like with classifier-based tests; CURED (Chandler et al., arXiv
2607.20140, 2026) [V-full] reports ENAR as the hardest mechanism to identify and – in a small demo – CDC's
true-positive rate as essentially unchanged across ECAR/EAR/ENAR (≈0.65 each at confidence 0.999). CURED
lists using MechDetect inside a cleaning pipeline as future work, i.e. mechanism-aware cleaning is open.

**Realistic synthetic errors.** TableEG (Liu et al., arXiv 2507.10934, venue UNVERIFIED) [V-full, partly]
claims LLM-generated errors yield detector metrics close to those on real errors. AutoAnoEval (Yoon et al.,
Findings EACL 2026) [V-full, experiments] and SWSA (Fung et al., arXiv 2310.10461) [V-abs] use synthetic
anomalies for *model selection* and measure agreement with real-label rankings; a mixture of ADBench's four
statistical anomaly types performed poorly as pseudo-validation. These are the closest works to our
"reliability of decisions" question, but they concern row-level anomaly detection and are not conditional
on an existing rule suite.

## 4. Evaluation methodology

- **Anomaly-type dependence of rankings.** ADBench (Han et al., NeurIPS 2022 D&B) [V-full]: the performance of
  unsupervised detectors "highly depends on the alignment of its assumptions and the underlying anomaly
  type"; no method wins on all types. Emmott et al. (ODD 2013 [V-meta]; arXiv 1503.01158 [V-full, partly])
  vary benchmark-construction factors and analyse logit(AUC) with mixed-effects models – a template for a
  factorial *error type × mechanism × dataset* analysis. Steinbuss & Böhm (TKDD 2021) [V-abs] generate
  realistic synthetic outliers with controlled characteristics.
- **Label-free model selection is unreliable.** Ma et al. (SIGKDD Explorations 25(1), 2023) [V-abs]: internal
  evaluation strategies are not practically useful; MetaOD (Zhao et al., NeurIPS 2021) [V-meta] uses
  meta-learning.
- **Algorithm-selection vocabulary.** Rice (1976), Kerschke et al. (Evol. Comput. 2019), ASlib (Bischl et al.,
  AIJ 2016) [V-meta]: evaluate a selector by regret against the oracle (virtual best) and by the gap closed
  relative to the single best solver.
- **Statistical comparison.** Demšar (JMLR 2006), Benavoli et al. (JMLR 2016; 2017), Corani et al. (MLJ 2017,
  hierarchical) [V-meta]; Bouthillier et al. (MLSys 2021) [V-abs] show that randomising more sources of
  variation (data split, seeds) changes conclusions. Gulrajani & Lopez-Paz (ICLR 2021) [V-meta]: model
  selection is part of the method; leave-one-domain-out validation is the analogue of our
  leave-one-mechanism-out / leave-one-dataset-out design.
- **Review budgets.** Precision/recall at a fixed number of alerts is standard in fraud detection (Dal Pozzolo
  et al., IEEE TNNLS 2018 [V-meta]; Le Borgne et al., fraud-detection handbook, 2022 [V-full, metrics
  chapter]) and in official statistics' *selective editing* (de Waal, Pannekoek & Scholtus, 2011;
  Pannekoek et al., JOS 2013) [V-meta], where hard edits (rules) are combined with score functions that
  prioritise manual review. This is a close methodological analogue to "rules + ranked learned alerts".

## 5. Synthetic-to-real transfer, label quality and the mutation-testing analogue

- Synthetic faults can inflate measured effectiveness (Abedjan et al. 2016 [V-full]); anomaly benchmarks can
  be trivial or mislabelled (Wu & Keogh, IEEE TKDE 2021 [V-meta]); test-set label errors shift rankings
  (Northcutt et al., NeurIPS D&B 2021 [V-abs]); "real-error" cleaning benchmarks have mixed provenance –
  PClean (AISTATS 2021) [V-full] describes Hospital as having "artificial typos", while TableEG lists it
  as real. Our own measurements confirm such issues for Raha Tax and Flights (docs/dataset_qualification.md).
- **Mutation testing** in software engineering asks the same validity question about injected faults:
  Just et al. (FSE 2014) [V-full] found the coupling effect for 73% of 357 real faults; Papadakis et al.
  (ICSE 2018) [V-abs] showed that mutation-score/real-fault correlations largely reflect test-suite size;
  Gopinath et al. (ISSRE 2014) [V-abs] found real faults rarely equal single mutation operators. We found
  mutation analysis of *schema constraints* (McMinn et al., TOSEM 2015) [V-meta] and of SQL queries (Tuya et
  al., IST 2007) [V-meta], but **no peer-reviewed mutation analysis of dbt / Great Expectations / Deequ data
  test suites** (searched; absence is not proof).

## 6. What is established and what is open

| Claim | Status in the literature |
|---|---|
| Learned detectors find some errors that rules miss | Established qualitatively (Abedjan 2016; ECB SPS 41; Bank of Italy; Bank of Thailand) |
| Error/anomaly type changes detector rankings | Established for row-level anomaly detection (ADBench, Emmott) |
| Realistic error mechanisms change cleaning-benchmark outcomes | Claimed (Jung et al. 2025 abstract); magnitude of rank changes UNVERIFIED |
| Synthetic pseudo-validation can select models if anomalies are realistic | Shown for row-level AD (AutoAnoEval, SWSA) |
| Injected faults are a partially valid proxy for real faults | Established in software testing (Just 2014; Papadakis 2018) |
| Budgeted, cell-level incremental recall of a learned detector *conditional on a realistic rule + statistical suite*, by error type × mechanism | **Not found** |
| Whether mechanism diversity in the evaluation changes *adoption decisions* or their regret | **Not found** |
| Mutation-adequacy of conventional data test suites | **Not found** (peer-reviewed) |
| Public financial dirty/clean benchmark with real, independently corrected cell errors | **Not found** (bounded search, docs/dataset_qualification.md) |

Closest overlapping works: Abedjan et al. 2016 (marginal value of tools on real errors), ECB SPS 41 and the
Bank of Thailand study (ML as complement to validation rules), Jung et al. 2025 / CURED / MechDetect (error
mechanisms with CDC), AutoAnoEval / SWSA (reliability of synthetic-anomaly-based selection), and Just et al.
2014 (validity of injected faults). See `research_gap.md` for how the proposed contribution differs.
