# Error injection in the pilot: error model, strategies and fairness

Status: 2026-10-20. Builds on `docs/error_injection_validation.md` (tab_err analysis, 582 validated variants).

## 1. Error model (Jung et al., JDIQ 2025, as stated by its authors)

tab_err remains the primary implementation. The JDIQ article (Jung, Jäger, Chandler & Biessmann, "Towards
realistic error models for tabular data") could still not be read here (ACM DL 403). Its authors summarise the
model in the CURED demonstrator paper (Chandler, Jäger, Jung & Bießmann, arXiv 2607.20140, §2.2, read):
"errors are parametrized by error type, error mechanism, and error rate. The error type is simply how the cell
in the table is actually altered … The error rate is the proportion of cells in the table that contain errors.
The error mechanism describes the distribution of error locations in a table", with ECAR = independent of the
data, EAR = dependent on another column, ENAR = dependent on the same column (their Table 1), as a
generalisation of Rubin's missing-data theory. **[lit]** The framework keeps the three apart:

| Concept | Where in the code | Pilot factor |
|---|---|---|
| error **type** – how a value changes | `injection/operations.py` (`scale`, `category_swap`, `code_remap`, `plausible_substitution`, `period_shift`, `ordinal_shift`, `digit_transposition`, `rounding`, sanity: `sign_flip`, `missing`, `invalid_code`) | error *case* = column × type, grouped into *families* |
| error **mechanism** – where errors occur | `injection/mechanisms.py` (soft and tab_err ECAR/EAR/ENAR) | named *mechanism settings* in `config/pilot/*.yaml` |
| error **rate** – how many cells change | `Scenario.rate` × batch rows | 1 % and 2 % |

Our rate differs in reference set: it is the share of **rows of the batch** whose target cell actually changes
(one target column per scenario). The table-level cell rate in the authors' sense is rate / n_columns (e.g. 1 %
in one of 23 Credit columns = 0.043 % of the table's cells). Both are reported in `scenarios.csv`
(`intended`, `realised`, `n_rows`).

## 2. Ground truth = changed cells only (verified)

`inject()` compares old and new values cell by cell and logs only changed cells; the realised count is
stored next to the intended count. tab_err's raw error mask is never used (it marks unchanged zero cells under
`WrongUnit`; `tests/test_tab_err_behaviour.py`). Tests covering this: `test_every_operation_mechanism_pair_validates`
(78 operation × mechanism pairs), `test_scale_never_selects_zero`, `test_category_swap_is_independent_per_cell`,
`test_frequency_weighted_swap_prefers_common_codes`, the EAR/ENAR placement tests, and — new —
`test_injection_log_counts_only_changed_cells_when_operation_is_a_no_op`,
`test_pilot_block_and_segment_mechanisms_log_only_changed_cells`, `test_ordinal_shift_changes_to_an_observed_neighbour`.
In the pilot runs every scenario had realised = intended; scenarios that could not be injected are listed in
`results/pilot/failures.csv` (none expected; see the report).

## 3. Two strategies with equal budgets

| | A – simple | B – diverse |
|---|---|---|
| error cases | the same primary cases (Credit 14, Bank 11) | identical |
| rates | 1 %, 2 % | identical |
| scenarios per (case, rate) | 3 | 3 |
| rows | the same selection partition | identical |
| mechanism | ECAR only | rotation over ECAR, soft EAR (segment / high values of another attribute), soft ENAR, tab_err EAR / ENAR windows, and a realistic **batch block** (Credit: a contiguous block of IDs = one upstream file segment; Bank: a contiguous block of delivery periods) |

Hence both strategies inject the same number of errors into the same rows and cost the same to evaluate
(84 / 66 selection scenarios each for Credit / Bank). The rotation is deterministic, so each B mechanism is used
about equally often; it is tested in `tests/test_pilot.py::test_strategies_have_equal_budgets_and_heldout_is_disjoint`.
ECAR/EAR/ENAR are experimental factors of strategy B, not a commitment of the research question.

Evaluation sets (pilot test partition, fresh seeds, never used for selection):

- `test_simple`, `test_diverse` — the generators of A and B with new seeds on other rows (in-distribution checks;
  B would win on `test_diverse` by construction, so that comparison is not used to judge B);
- `test_heldout` — **10 error cases that are in neither strategy** (other columns or column × type pairs, e.g.
  BILL_AMT3 ×10, PAY_3 swaps, AGE digit transposition; Bank: marital/loan/contact swaps, weekday shift, age
  in months) under **mechanism settings that neither strategy uses** (ENAR in the opposite direction, EAR on an
  attribute nobody conditions on) plus ECAR. This is the set on which regret and decision agreement are judged.

## 4. BART as an independent generator

BART (Arocena et al., PVLDB 9(2) 2015; dbunibas/BART, MIT) generates denial-constraint violations plus typos,
bogus values and outliers; it needs Java 7 and PostgreSQL ≤ 11 or H2. UCI Credit and Bank have few exact
dependencies (Bank: macro indicators only), so BART's main strength (detectable DC violations) does not match
our error catalog. Instead of installing it, the existing BART-generated Raha Tax pair is used as an
out-of-generator check (`scripts/independent_validation.py`, track A): it tests whether a selection made on our
injections agrees with a selection on BART's errors. BART is therefore **not required**; it remains an option for
a robustness study if supervisors want a second generator on the financial tables.
