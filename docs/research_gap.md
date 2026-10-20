# Research gap and novelty assessment

Status: provisional, for supervisor review (2026-10-19). Sources: `literature_review.md`, `references.bib`.

## 1. The provisional research question

> "How reliably can controlled error-injection experiments estimate the incremental detection value of
> learned data-quality detectors beyond conventional validation checks, across different error types,
> error mechanisms and financial tabular datasets?"

### What is already answered elsewhere

| Part of the question | Closest work | What it shows | What it does not show |
|---|---|---|---|
| Learned detectors add value beyond rules | Abedjan et al. 2016; ECB SPS 41 (2021); Bank of Thailand (IFC 66, 2026) | Complementarity exists; tool contributions to combined recall on real data; ML as "second line of defense" | Controlled, budgeted, cell-level increment conditional on a realistic rule suite; dependence on error mechanism |
| Error type changes method rankings | ADBench (2022); Emmott et al. (2013/2015) | Strong type dependence for row-level anomaly detection | Cell-level errors; mechanisms; decisions |
| Error mechanism matters | Jung et al. (JDIQ 2025); CURED (2026) | Mechanism changes cleaning-benchmark outcomes (abstract); CDC TPR ≈ unchanged across mechanisms in a small demo | Effect on *incremental* value over rules; effect on adoption decisions |
| Synthetic evaluation can guide selection | AutoAnoEval (EACL Findings 2026); SWSA | Rank agreement with real labels depends on anomaly realism | Cell-level, conditional on rules, mechanism dimension |
| Injected faults as proxy for real faults | Just et al. 2014; Papadakis et al. 2018 (software) | 73% coupling; suite-size confound | Data-quality test suites |

**Conclusion.** The question as phrased is *not* already solved, but two of its premises are known:
learned detectors can complement rules, and error type changes rankings. A thesis that only showed "CDC
finds errors that dbt tests miss" or "rankings depend on error type" would not be novel.

## 2. Weaknesses of the provisional question (and of the earlier pilot)

1. **"Reliably" was not operationalised.** Reliability must be defined as the agreement (or regret) between
   a decision made from one evaluation design and the decision that is correct under a *different*,
   held-out condition. Otherwise the question reduces to measuring variance.
2. **Circularity risk.** If a mechanism-diverse evaluation (ECAR+EAR+ENAR) is tested on held-out scenarios
   drawn from the *same* mixture, it wins by construction. Held-out conditions must be genuinely unseen:
   another mechanism family or strength, another error type, another dataset, or real errors.
3. **Dominance makes agreement uninformative.** In the pilot one detector (CDC) dominated, so ECAR-only and
   mechanism-aware selection agreed in 15/18 cases. Agreement must be compared with what dominance alone
   predicts, and the decision should be framed against the *baseline* (adopt / not adopt / insufficient
   evidence), which can flip, rather than as a choice among learned detectors.
4. **The baseline was weak.** The pilot compared CDC with Tukey bounds and code domains only. With a strong
   baseline (documented rules + fitted cross-field statistical controls) the measured increment shrinks
   substantially (first indication in `feasibility_report.md`).
5. **The mechanism implementation is itself a factor.** tab_err's EAR/ENAR are hard contiguous windows with
   a random position; the region of values that is hit changes with the seed, and ties are resolved by file
   order. Seed variance in the pilot was therefore partly *mechanism-position* variance (verified in
   `error_injection_validation.md`).
6. **External validation for the main detector is not available.** The only well-documented real-error
   benchmark (Flights) has errors that are inter-source conflicts; a leakage-free evaluation of CDC on it is
   at chance level (AUC ≈ 0.5, `results/qualification/flights_typed_probe.json`). No public financial
   real-error benchmark was found. Claims about synthetic-to-real transfer must therefore be limited.

## 3. Genuinely open, MSc-feasible gaps

- **G1 – Conditional incremental value.** Budgeted cell-level incremental recall (ΔR@k) of a learned detector
  over a realistic deterministic + statistical control suite, decomposed by error type × mechanism × rule
  coverage, with the alert burden on untouched data.
- **G2 – Decision reliability under mechanism shift.** Whether adoption decisions (adopt / do not adopt /
  insufficient evidence) derived from ECAR-only injection remain correct under held-out mechanisms (other
  shape, strength, conditioning attribute), held-out error types and a second dataset; and whether a
  mechanism-diverse design lowers decision regret under leave-one-condition-out validation.
- **G3 – Adequacy of conventional data test suites as mutation analysis.** Mutation score and surviving
  errors of dbt + statistical suites under realistic error models, including "equivalent mutants" (injected
  errors indistinguishable from valid data).
- **G4 – Synthetic-to-real transfer in finance.** Essentially no public evidence or data; only a limited
  coupling check is feasible (see below).

Too ambitious for an MSc: building a new real-error financial benchmark (SEC amendments, revision
histories), a universal detector selector, or production deployment claims.

## 4. Smallest defensible novelty

A pre-registered, mechanism-controlled evaluation showing **when the decision to add a learned cell-level
detector to an existing conventional control suite changes**, with:

1. the increment measured *conditional on* a strong, documented baseline and at a fixed review budget;
2. the error mechanism treated as an explicit, *dose-controlled* factor (shape and strength), not only as
   three labels;
3. decision reliability measured as regret/agreement under leave-one-condition-out validation, against a
   dominance-aware reference;
4. a reusable, auditable tool that produces this evidence for a new source from a contract.

Each element exists separately in the literature; the combination for cell-level financial data quality,
and the decision-reliability framing, were not found. This is a modest but defensible MSc contribution; it
does not depend on the learned detector "winning".

## 5. Strongest objections and how to address them

| Objection | Response in the design |
|---|---|
| "Synthetic errors prove nothing about real errors." | Agreed for prevalence. Claims are restricted to *which kinds of plausible errors* the controls miss and to *decision stability*; real-error coupling is reported only where valid (Raha on Flights; out-of-generator check on BART-generated Tax errors if qualified). |
| "The baseline is a straw man." | Rules come from documentation and untouched data, are versioned with evidence status, include fitted cross-field statistical controls, and are frozen before any injection results are seen. A stronger and a documented-only baseline are reported (sensitivity). |
| "You tuned the injections to make ML look good (or bad)." | Scenario catalog with rationale per error; primary vs sanity roles fixed in advance; all scenarios reported. |
| "Only one learned detector." | CDC (cell-level, two implementations cross-checked) plus a row-level Isolation Forest with different inductive bias; Raha documented as incompatible with the low-rate setting. The research question concerns adding *a* detector to the baseline, so a large detector zoo is not required. |
| "Seeds share rows; CIs are optimistic." | Unit of replication = (split seed × injection seed); hierarchical/bootstrap over split seeds; power analysis before the confirmatory run. |
