# Error-injection validation

Status: 2026-10-20. All numbers are **[ours]** unless marked otherwise. Reproduce with

```bash
python scripts/validate_injection.py uci_credit
python scripts/validate_injection.py uci_bank_marketing
python -m pytest -q tests/test_injection.py tests/test_tab_err_behaviour.py
```

Results: `results/qualification/injection_validation_<dataset>.csv` (one row per scenario variant).
Validation uses the **dev** partition of split seed 1 only; test partitions were not touched.

## 1. Design: operation ≠ mechanism

An injected scenario is `(column, operation, mechanism, rate, seed)`.

* **Operation** (`src/dq_framework/injection/operations.py`) – *how* a value changes, with an explicit
  eligibility rule (cells where the change is real and semantically meaningful).
* **Mechanism** (`src/dq_framework/injection/mechanisms.py`) – *where* errors occur:
  ECAR (independent of the data), EAR (depends on another observed attribute), ENAR (depends on the cell's
  own value). Verbal definitions follow Jung et al. (JDIQ 2025) as documented by the tab_err authors; the
  paper's formal §3 definitions could not be read here and must be quoted from the PDF (see
  `literature_review.md` §3).
* Ground truth = the injection log: only cells whose value **actually changed** count as errors; original
  and injected values are stored per cell; raw files are never modified (injection works on copies of a
  partition that is disjoint from the reference partition – enforced in `inject()`).

## 2. tab_err 0.2.1: what is used, what is not, and why

| tab_err component | Used? | Evidence |
|---|---|---|
| `WrongUnit` (scaling) | yes, via `scale`, only on non-zero cells | The tab_err mask marks zero cells as errors although ×10 leaves them unchanged: 50 masked vs 26 changed cells in `test_wrong_unit_mask_includes_unchanged_zero_cells`. In UCI Credit 17–24% of PAY_AMT and 7–13% of BILL_AMT values are 0, so using tab_err's mask as ground truth would mislabel up to a quarter of "errors". |
| `MissingValue` | yes (`missing`, sanity) | – |
| `Outlier` | yes (`outlier`, sanity) | – |
| `CategorySwap` (uniform) | **only as `code_remap`** | With pandas 2.3.3, `Series.apply` on a categorical runs once per *category*, so every cell with the same true code receives the same wrong code within one call (`test_category_swap_maps_each_true_code_to_one_wrong_code`; in the first demo all 59 swapped EDUCATION=2 cells became 0). This is a systematic mapping error, not the documented random mislabel; it is kept as an explicitly named operation. |
| `CategorySwap` (frequency weighing) | **no** | Uses pandas `.sample()` without a random state: results depend on the global numpy state, not on tab_err's seed (`test_category_swap_frequency_depends_on_global_numpy_state`). |
| `AddDelta` default | **no** | Without configuration it adds a constant z-scale delta (0.71 on amounts of ~50,000) – not a material error. |
| `ECAR` / `EAR` / `ENAR` | yes, as the `tab_err_*` family | See §4 for their properties. |
| Global `random` seeding | worked around | tab_err re-seeds Python's global `random` on every apply; our wrapper restores the global state afterwards. |

Custom operations (tested per cell in `tests/test_injection.py`): `category_swap` (per-cell, frequency- or
uniform-weighted, reproducible), `sign_flip`, `digit_transposition`, `period_shift` (value of an adjacent
month column), `rounding`, `plausible_substitution` (value from the reference distribution, ≥20% relative
difference), `invalid_code` (sanity).

## 3. Results of the validation grid

| Check | UCI Credit (366 variants) | Bank Marketing (216 variants) |
|---|---|---|
| every logged cell really changed; realised = intended count | 100% | 100% |
| no change outside logged cells | 100% | 100% |
| identical log when re-run with the same seed | 100% | 100% |
| different selection with another seed | 100% | 100% |
| operation semantics hold (e.g. injected = factor × original; swap target is a valid other code) | 100% | 100% |

### Placement dependence (mean / max over variants)

Two-sample KS statistic (numeric) or Cramér's V (categorical) between selected and eligible-but-unselected
cells; ≈0.04–0.05 is the sampling floor for 60–300 selected cells.

| Mechanism | own value | conditioning column | unrelated control column |
|---|---|---|---|
| soft ECAR | 0.045 / 0.095 | – | 0.054 / 0.097 |
| tab_err ECAR | 0.046 / 0.124 | – | 0.041 / 0.070 |
| soft EAR (`LIMIT_BAL`, high) | 0.117 / 0.219 | **0.443 / 0.519** | 0.120 / 0.170 |
| tab_err EAR (`LIMIT_BAL`) | 0.177 / 0.390 | **0.683 / 0.813** | 0.095 / 0.137 |
| soft ENAR (high) | **0.406 / 0.571** | – | 0.107 / 0.450 |
| tab_err ENAR | **0.587 / 0.814** | – | 0.148 / 0.776 |

(UCI Credit; Bank Marketing in the CSV shows the same pattern.) ECAR shows no dependence; EAR depends on
its conditioning column; ENAR on the cell's own value. Control-column maxima for ENAR come from targets
whose own value is correlated with the control column (e.g. AGE as target and control), not from leakage.
**Verdict: mechanisms are implemented as intended at the qualitative level.**

## 4. Properties of tab_err's EAR/ENAR that matter for the research question

1. **Hard window, random position.** EAR/ENAR corrupt one contiguous block of the sorted values, starting at
   a uniformly random offset. *Which* value region is hit is therefore a seed effect. Example (×10 on
   BILL_AMT1, 5% rate, share of injected values outside the reference 0.05–99.95% envelope):

   | mechanism | seed 101 | seed 202 | seed 303 |
   |---|---|---|---|
   | soft ECAR | 0.32 | 0.32 | 0.33 |
   | soft ENAR (high, strength 4) | 0.72 | 0.72 | 0.74 |
   | tab_err EAR (`LIMIT_BAL`) | 0.43 | **0.01** | 0.51 |
   | tab_err ENAR | 0.00 | 0.00 | 0.00 |

   Under tab_err EAR the *difficulty* of the scenario swings from trivially detectable to undetectable with
   the seed. Part of the "seed sensitivity" reported in the earlier pilot is therefore mechanism-position
   variance, not detector instability. The soft family makes direction and strength explicit design
   parameters and is stable across seeds.
2. **Tie order follows the file.** With a low-cardinality conditioning column the window falls inside one
   tie block, and the unstable pandas sort keeps rows close to file order. In Bank Marketing (file ordered
   by date), tab_err EAR conditioned on the binary `contact` selected **0% telephone records** in all three
   seeds and concentrated all errors in 2–8 contiguous delivery months (KS on `_period` up to 0.92). The
   realised mechanism is "a time window among cellular contacts", not "channel-dependent errors"
   (`test_tab_err_ear_on_low_cardinality_condition_follows_row_order`). The soft EAR selected 97% telephone
   records as intended.
3. **ENAR on categorical codes** sorts the codes, i.e. imposes an order on nominal values. For categorical
   targets the soft family instead uses an explicit *segment* (e.g. only cells whose true PAY_0 is 0).

**Consequence.** tab_err's mechanisms are valid instances of ECAR/EAR/ENAR, but the window shape, its
random position and tie handling are uncontrolled experimental factors. For the confirmatory study we
propose: soft mechanisms with strength as a continuous factor (0 = ECAR), plus the tab_err window as a
second, explicitly named mechanism *shape*. This preserves the definitions and turns the mechanism into a
dose–response variable.

## 5. Triviality: which errors are easy by construction?

Share of injected values outside the reference range / 0.05–99.95% envelope (numeric) or outside the
reference domain (categorical), mean over mechanisms and seeds:

| Case | outside range | outside envelope | Interpretation |
|---|---|---|---|
| Credit `PAY_AMT1` sign flip | 1.00 | 1.00 | sanity: caught by `PAY_AMT ≥ 0` |
| Credit `EDUCATION` invalid code | – | domain 1.00 | sanity |
| Bank `euribor3m` ×0.01 | 1.00 | 1.00 | percent→fraction: trivially out of range |
| Credit `BILL_AMT1` sign flip | 0.11 | 0.83 | mostly caught by the envelope; negatives are legal |
| Bank `duration` ÷60 | 0.00 | 0.67 | partly out of envelope |
| Credit `BILL_AMT1` ×10 | 0.11 | 0.17 | **mostly inside the observed distribution** |
| Credit `LIMIT_BAL` digit transposition | 0.00 | 0.12 | mostly plausible |
| Credit `PAY_AMT1` ×10 | 0.01 | 0.05 | heavy tail hides scaling |
| all plausible substitutions, period shifts, rounding, valid-code swaps | ≈0 | ≈0 | non-trivial for univariate checks |

The catalog therefore keeps trivial errors as **sanity** cases and draws primary conclusions from the
non-trivial ones. Univariate triviality is not the full story: cross-field statistical controls catch some
"in-range" errors (e.g. ×10 when the month-over-month change is implausible); this is what the baseline
recall measures.

## 6. EAR conditioning variables

No synthetic attribute (such as the pilot's `source_system`) is introduced. Conditioning columns are real
attributes with a stated rationale in `config/experiments/scenario_catalog.yaml`:
UCI Credit – `LIMIT_BAL` (errors concentrated in high-limit accounts handled by a separate process);
Bank Marketing – `contact = telephone` (errors from one capture channel). These are **stress-test design
choices**, not claims about real banking error mechanisms. The only real mechanism evidence we have is
Flights, where error rates depend strongly on the observed `src` (0–100% per source): real errors can be
attribute-dependent (EAR-like).

## 7. Leakage and fairness checks

* Injection refuses batches overlapping the reference partition; detectors and statistical controls are
  fitted on the reference partition only; rules come from documentation and untouched data.
* Duplicate rows are kept in one partition (group-aware split).
* The realised error count equals the intended count for every variant (no silent no-ops).
* Uniform category swaps over-represent rare codes (easy for rare-category controls); the primary catalog
  uses frequency-weighted swaps, uniform weighting is a sensitivity setting.
* Remaining open point: a *mechanism-strength* grid and its power analysis are part of the confirmatory
  protocol (`research_design.md`), not of this qualification.
