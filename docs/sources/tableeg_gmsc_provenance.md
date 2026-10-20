# Provenance of "TableEG Credit" (2026-10-20)

Question: is TableEG's Credit dataset (Liu et al., arXiv 2507.10934; github.com/viviancircle/TableEG @ ea889b80)
derived from Kaggle "Give Me Some Credit" (GMSC, cs-training.csv)?

**Verdict: PROBABLE (strong).** Each link was checked separately:
- TableEG Credit `dirty.csv` = CleanML `data/Credit/raw/raw.csv`, cell for cell, with a `row_id` column added. **VERIFIED** (0 mismatches).
- TableEG Credit `clean.csv` = CleanML's two HoloClean outputs pieced together. **VERIFIED** (0 mismatches, see §3).
- The CleanML authors say Credit comes from Kaggle GiveMeSomeCredit. **VERIFIED as a statement** (two primary CleanML documents).
- CleanML `raw.csv` = GMSC cs-training.csv without its unnamed index column. **PROBABLE**: the schema, column order,
  row count and missing-value counts all match the GMSC description we were given. We could not compare it byte for byte,
  because the Kaggle original is not reachable (data API returns 401 Unauthenticated, the page is JS-only).
- The TableEG paper and repo never mention Kaggle or GMSC. They cite only CleanML [32] and Raha [34] as data sources.

## 1. TableEG evidence (repo, Drive, paper)
Repo @ ea889b80 (2025-03-06). "Credit" appears only in README.md, and no code or config refers to it:
- README.md:127: "The datasets used in this work contain both **clean** and **real-world erroneous** data, primarily
  sourced from [**CleanML**](https://github.com/chu-data-lab/CleanML) **and** [**Raha**](https://github.com/BigDaMa/raha)."
- README.md:136: `| Credit | 150,000| 10 | Finance | 2.33% | M, O |`
- README.md:53: Drive folder `10LdB9LGgymbI6W8D2936uRF6eFRL24xy`, which holds `source/Credit/{clean.csv, dirty.csv,
  Credit_annotation.csv, Credit_annotation.jsonl}`. Credit does not appear in `test_dataset/exp_1/`, so it is a training source only.

Paper (arXiv 2507.10934v3, 9 Mar 2026, 14 pp.; PDF SHA-256 67989db4…12dc56bd). There are no hits for "Kaggle",
"Give Me Some Credit", "150000" or "HoloClean" in connection with Credit:
- p.5, Table 1: "Credit 150,000 10 Finance 2.33% M, O".
- p.5, §3.3: "The datasets used in this study are primarily sourced from those introduced in [32, 34], which are
  primarily designed for error detection and data cleaning tasks." Here [32] is Li, Rao, Blase, Zhang, Chu, Zhang 2021,
  "Cleanml: A study for evaluating the impact of data cleaning on ml classification tasks", ICDE 2021, 13–24, and
  [34] is Mahdavi et al. 2019, "Raha" (references, p.13).
- p.6: "Credit: A financial dataset containing 150,000 credit records with attributes such as income, age, and number
  of dependents. The dataset is affected by missing values (M) in financial attributes and numerical outliers (O) due
  to extreme income values."
- p.5, Stage 1: "both clean and dirty data from real-world datasets, which are manually annotated to serve as the output
  labels"; p.2: "Leveraging manually labeled error data from our standardized annotation collection". As §3 shows,
  this does not hold for Credit.

## 2. CleanML evidence (repo 92bcb773, 2023-08-23; data zip from README Dropbox link)
- `schema/dataset.py`: `Credit = {"data_dir": "Credit", "error_types": ["outliers", "missing_values"], "label":
  "SeriousDlqin2yrs", "categorical_variables":["SeriousDlqin2yrs"], "ml_task": "classification", "class_imbalance":True}`.
  It also defines `Credit_uniform/major/minor` (variants with injected mislabels).
- Data is not in git. It sits behind the README link `dropbox.com/s/nerfrhbrseev928/CleanML-datasets-2020.zip`, which
  downloads fine (227,636,874 B, SHA-256 d640bdb0…cb053).
- `data/Credit/Readme.txt` (dated 2018-10-15): "Source: https://www.kaggle.com/c/GiveMeSomeCredit/data / Description: This
  dataset contains anonymized credit data and demographics including monthly income, age and number of dependents. /
  Error: This dataset primarily contains missing values and numerical outliers. / ML task: Classification: predict
  whether a client will experience financial distress in the next 2 years".
- `DatasetDescriptions.pdf` (repo root): "Credit: This dataset [3] consists of 150,000 credit records with 10 attributes
  including monthly income, age, then number of dependents, etc. ... only 6.7% records in the minority class ... This
  dataset contains missing values and numerical outliers." Its reference reads "[3] Credit dataset.
  https://www.kaggle.com/c/GiveMeSomeCredit/data. Accessed: June 19, 2020." The TechReport footnote explains the count:
  "We do not count a label as an attribute", so 10 attributes + label = 11 columns.
- `raw/raw.csv` (2018-10-15): **150,000 rows x 11 columns**, SHA-256
  `4bdbe1a7f3ab84f85161b10d866cc98b7bb2dda70c7a9817515aeefb4b704c6e`. There is no trailing newline and no index column.
  The columns, in exact GMSC order without the unnamed index, are SeriousDlqin2yrs, RevolvingUtilizationOfUnsecuredLines,
  age, NumberOfTime30-59DaysPastDueNotWorse, DebtRatio, MonthlyIncome, NumberOfOpenCreditLinesAndLoans,
  NumberOfTimes90DaysLate, NumberRealEstateLoansOrLines, NumberOfTime60-89DaysPastDueNotWorse, NumberOfDependents.
  Profile:
  - MonthlyIncome NaN 29,731 (19.821 %); NumberOfDependents NaN 3,924 (2.616 %). Every NoD-NaN row also has MonthlyIncome NaN.
  - SeriousDlqin2yrs mean 0.0668; age 0–109; RevolvingUtil max 50,708; DebtRatio max 329,664; MonthlyIncome max 3,008,750.
  - NumberOfTimes90DaysLate max 98; 609 duplicate rows.
  - First row `1,0.766126609,45,2,0.802982129,9120,13,0,6,0,2`.

  All of this is consistent with GMSC as described in the task. It is not byte-verified against Kaggle.
- How CleanML makes "clean" versions: there is no ground-truth clean table for Credit. Cleaning is done automatically
  per train/test split (`schema/error_type.py`, `schema/clean_method.py`):
  - missing values: delete, mean/median/mode imputation (`impute_*`), or HoloClean (`MVHoloCleaner` reads
    `raw/Holoclean_mv_clean.csv`);
  - outliers: SD (3 sd), IQR (1.5) or IsolationForest detection followed by mean/median/mode imputation, or HoloClean
    (`raw/Holoclean_outlier_clean.csv`).
  Precomputed files:
  - `raw/Holoclean_mv_clean.csv` (150,000 x 11, SHA-256 af8546ea…e78b717) only fills NaN cells, with 0 changes elsewhere.
  - `raw/Holoclean_outlier_clean.csv` (120,269 x 11, SHA-256 a5d255d4…b7dea97) contains exactly the rows with
    MonthlyIncome present, in order. It changes 5,281 cells across all 10 attributes.

## 3. TableEG Credit files (Drive, obtained via gdown 6.4.2 in a scratch venv)
| file | SHA-256 | shape |
|---|---|---|
| dirty.csv (UTF-8 BOM) | 57006c6b3ab5f2a91c7cd2f166a450f7abda2743f9b2ca8817abbcbe90b60ecd | 150,000 x 12 (row_id 0..149999 + 11 GMSC cols) |
| clean.csv (UTF-8 BOM) | 75f7e05bc41aa6c451ae1aaf3eef0bb99372e811bb01597f8ef35c9cb47971c1 | 150,000 x 12, no NaN |
| Credit_annotation.jsonl | fa600562d1fbf9fbbd28d33243f0a3773adf5b4686454f6b1e070b88f7855779 | 34,938 records |
| Credit_annotation.csv | 9f6ba8a2aabcb8c6eb8999d3d5e59a72b5e1dfeb71a3f2248ec476ffbb13d9da | same content as CSV |

- **dirty.csv vs CleanML raw.csv:** dropping `row_id` leaves 0 differing cells (NaN-aware, rtol 1e-9). The files are
  not byte-identical because of the BOM, the row_id column and the trailing newline. It has the same NaN counts
  (29,731 / 3,924) and the same 0.0668 label mean.
- **clean.csv reconstruction:** for the 29,731 rows with MonthlyIncome NaN, clean.csv equals `Holoclean_mv_clean.csv`
  (0 diffs). For the other 120,269 rows it equals `Holoclean_outlier_clean.csv` (0 diffs). So clean.csv is CleanML's
  HoloClean output, not a curated ground truth. As a result:
  - outlier repair only covers the MonthlyIncome-present rows: clean.csv still has age max 109, DebtRatio max 329,664 and
    RevolvingUtil max 22,198;
  - imputed values are degenerate: 17,435 of the 29,731 MonthlyIncome NaNs become 88.44070676, and NumberOfDependents
    becomes 0 (3,460) or 1 (464).
- **Annotations vs clean≠dirty:** 34,938 annotated cells, all of them changed cells, but 38,936 cells differ between
  dirty and clean.
  - Annotated (error_value and right_value match dirty and clean in 34,938/34,938 cases):
    - missing_value 33,655 (MonthlyIncome 29,731; NumberOfDependents 3,924; that is every NaN cell);
    - outliers 1,283 (DebtRatio 825, ≥1,303; MonthlyIncome 321, ≥50,000; RevolvingUtil 134, ≥904; age 3, 95–103).
  - **Not annotated: 3,998 changed cells** (NumberOfOpenCreditLines 1,302; NumberRealEstateLoans 1,265;
    NumberOfDependents 921; 90DaysLate 163; 30-59 152; 60-89 149; age 46, e.g. age 0→56). The fields `constraint` and
    `tuple_pairs` are always null.
- **README's 2.33 %** = 34,938 / (150,000 x 10 attributes) = 2.329 %. The "10 columns" figure follows CleanML's convention
  of leaving out the label. Counting clean≠dirty instead gives 38,936 / 1.5 M = 2.60 %.

## 4. GMSC data dictionary
Not found anywhere with stated provenance. There is nothing in the CleanML repo or data zip (no .xls, no column
descriptions beyond Readme.txt above) and nothing in the TableEG repo or Drive. Kaggle
`https://www.kaggle.com/competitions/GiveMeSomeCredit/data` returns a 6 kB JS shell, the API returns 401, and
web.archive.org reset the connection. **UNVERIFIED**: the variable descriptions/types from "Data Dictionary.xls" could
not be obtained. Do not quote them from secondary mirrors without provenance.

## 5. Label provenance (for the thesis)
- Missing-value labels: the positions are real, since they are exactly the NaN cells already present in the source data.
  The "right_value" corrections are HoloClean imputations, not truth (88.44 for 59 % of the MonthlyIncome NaNs).
- Outlier labels: these are cells that HoloClean's outlier repair changed in 4 columns, with the "corrections" also coming
  from HoloClean. They are algorithmic, not manual and not verified errors. The paper's "manually annotated" claim is
  contradicted for Credit (provisional: we have no TableEG author statement on Credit specifically).
- The LLM did not generate anything for Credit. Credit is a training source; TableEG's synthetic outputs exist only for
  the exp_1 datasets.
- SeriousDlqin2yrs is never changed. It is a prediction target, not a data-quality label.
- Implication: treat TableEG-Credit labels as "HoloClean-repair disagreements on GMSC (via CleanML)". They are not real
  ground-truth errors, and clean.csv is not error-free. Any use should cite CleanML/GMSC as the origin and treat the
  outlier labels as a detector output.

## Reproduction
Clones: (session scratch) {tableeg,cleanml}/repo. Downloads: (session scratch) dl/{cleanml_zip,tableeg_credit,
arxiv,gdrive}. Scripts: (session scratch) scripts/{profile.py,compare.py,compare2.py,list_drive.py}, run with `python3 -I`.
