# Defensible research directions after the pilot

Status: 2026-10-20, for supervisor review. Evidence: `docs/comprehensive_pilot_report.md` (all numbers there are
provisional pilot measurements on public data). No direction below claims novelty yet; each lists what the
pilot supports and what a confirmatory study must still show.

## What the pilot established (provisional)

1. For total detection, the strength of the existing controls (rules vs rules + statistical controls) changes
   recall on held-out errors more (0.11–0.16) than the choice of learned detector (0.03–0.07) in 8 of 9
   unit × budget cells.
2. The increment of a learned detector over a strong baseline is small (0.005–0.10 at 25 reviews per 1,000 rows).
   It differs measurably between CDC and dBoost, with a sign that depends on the source and on temporal shift.
3. Detector rankings obtained on a synthetic error catalog reverse on held-out error cases, so selection regret is
   non-zero (0.02–0.08). Diversifying the error *mechanisms* (strategy B) does not reduce that regret. On real
   non-financial errors a selection made on synthetic errors also picks the wrong transductive candidate.
4. The detectors find largely disjoint sets of errors (Jaccard ≤ 0.08).

## Direction 1 (recommended): selection reliability under error-population shift

> How reliable is a detector-adoption decision derived from controlled error injection when the errors that
> occur later differ from the error population used for the decision, and how does this reliability depend on
> the strength of the existing controls?

- **Why defensible:** observations 2–3 show non-trivial, measurable regret that cannot be removed by choosing
  mechanisms. Baseline strength is a natural, engineer-controlled factor (observation 1).
- **Design:** leave-one-error-family-out and leave-one-source-out validation; the error catalog as the shifted
  factor (not the mechanism); baseline strength and review budget as factors; regret and decision agreement as
  outcomes; delivery sets or independent sources as the unit of replication.
- **Needs:** ≥ 3 independent financial sources or long delivery histories. The pilot's delivery-set variance
  implies ~20–50 sets for a detector difference of 0.02 (`results/pilot/go_no_go.json`). Also GMSC (accept the
  Kaggle rules) or another permitted source, and a pre-registered held-out family.
- **Risk:** with few sources the conclusion may be source-specific; must be stated as such.

## Direction 2: baseline-conditional value of learned detectors

> When does a learned cell-level detector add enough detection, at a fixed review budget, over a given
> conventional control suite?

- Simpler; directly answers the practical question. Observation 1 makes the answer largely "it depends on the
  suite". The contribution is a measured coverage map: error family × suite strength × detector.
- **Risk:** close to existing complementarity studies (Abedjan et al. 2016) unless budget, rule status and
  conditional increments are central.

## Direction 3: combining detectors under a review budget

Observation 4 (disjoint findings) suggests that a budget split or rank fusion of CDC and dBoost may beat either
alone. This is a methods contribution (AI component), but it was not tested in the pilot [open], and it needs a
fair, pre-registered fusion rule.

## Not recommended

- Injection strategy A vs B as the main question: no effect on the selected method in this design.
- External real-error validation as a main result: no financial benchmark with verified labels exists (REIN
  blocked, Auto-Test/AddressTable unsuitable, TableEG Credit labels are HoloClean repairs).
- LLM detectors (ZeroED): not runnable as published, and in conflict with the confidentiality context.

## Concrete next steps

1. Supervisor decision on Direction 1 vs 2 and on the hold-out policy (D-20).
2. Accept the Kaggle GMSC rules; pin the hash; write its contract from the data dictionary and the untouched
   data.
3. Freeze contracts, catalog (with a separate pre-registered held-out family), detector configurations and the
   decision rule; tag the commit.
4. Run the confirmatory study on delivery-based replications and the seed-1 hold-out.
