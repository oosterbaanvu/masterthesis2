# MSc proposal draft: simulation-guided selection beyond data-quality rules

**Status:** exploratory proposal, 2026-10-21; supervisor approval and confirmatory evaluation outstanding.

## Problem and question

A data engineer already runs completeness, domain and SQL consistency checks. A learned error detector
can find additional defects, but also competes for a limited human review queue. A high standalone score
on a synthetic benchmark does not show that adding it is a good decision for a future source or delivery.

**How reliably can controlled error injection guide the selection of cell-level error detectors that
add detection value beyond conventional data-quality checks?**

The question is retained regardless of positive, negative or inconclusive detector outcomes. Hypotheses
are that baseline strength and error-family shift alter the preferred detector; more diverse placement
mechanisms and uncertainty-aware selection may reduce regret, but may also have no benefit or abstain
too often.

## Evidence and scope

The repository supplies a working contract → dbt/SQL → statistical control → detector → findings service.
The integrated exploratory evidence and numerical tables are in `thesis_scale_pilot_report.md`. It adds
a chemistry domain to Credit/Bank, uses two baseline suites and a shared total review budget, and
compares mean selection with a pre-specified case-bootstrap/family guard. Historical financial pilot
results use a different, extra-budget estimand and remain separate.

The completed package contains eleven replications and 3,318 successful scenarios, with 110 failed
injections disclosed. At 25 total reviews/1,000 rows, CDC adds 8.50, 8.06 and 35.15 percentage points
on Credit, Bank and Wine above deterministic rules; with historical statistics the gains are −1.56,
−3.23 and +2.03 pp. The robust selector finds the held-out A oracle in these splits, but both selectors
miss 18.50 pp of available gain on shifted Wine cases with B. This mixed result supports studying
conditional decision reliability and abstention failure, not assuming robust superiority or generic
ML benefit. Reusing nine qualified published scans supplies a missingness-ceiling check, not verified
natural substantive-error generalization.

Method qualification currently supports CDC-HGB and Gaussian dBoost, including typed/text dBoost
configurations, with historical-reference IQR as secondary. These are three primary configurations
from **two families**, not three independent learned methods. CDC-HGB and dBoost rankings are existing,
documented adaptations. Full LUCARIO and a faithful label-free Picket cell-budget interface have not
been qualified. Few-label Raha/HoloDetect, LLM-assisted ZeroED and record-level detectors belong to
separate information tracks.

Published references are a major scientific constraint. Restaurant/Cars mainly contain synthetic
missingness; Rayyan changes need adjudication. The earlier nine dirty-only scans establish execution
and explanations, not verified natural-error generalization. Flights, Beers and Tax also have documented
reference/formatting limitations. A defensible study must be able to conclude that transfer is
unidentifiable rather than manufacture a favourable score.

## Proposed method and contribution

Freeze the eligible implementations, source contracts, allocation policy and selector before
confirmatory scoring. Keep prediction targets out of DQ labels. Use exact changed-cell injection
labels for 1%/2% substantive errors crossed with applicable ECAR/EAR/ENAR placement. Exclude the
reserved seed-1 holdout from exploration; fit/calibrate only on allowed historical rows.

Measure signed incremental recall at 10/25/50 unique total reviews per 1,000 rows, baseline and native
workload, precision lower bounds, genuine-score AP, overlap, selection regret and abstention. Evaluate
held-out families, mechanisms/strengths/rates, sources and actual Bank deliveries. Collapse dependent
resplits/seeds within error cases; report conditional case-mix sensitivity, not dataset-level confidence
from thousands of injections. Published reference evaluation remains injection-free and label-qualified.

The proposed contribution is an empirical decision framework and evidence about when **simulation
selection conditional on an existing rule suite** succeeds, fails or should abstain. It is not a new
error detector, invention of robust selection, or proof of real bank error performance. The novelty
claim requires a focused check against CDC, REIN, Raha, realistic error models, selective editing and
anomaly-model selection; the qualification review identifies this boundary explicitly.

## Completion conditions

Proceed with the narrower decision-reliability scope only if the supervisor accepts the information
track and available independent units. Before confirmation: qualify a second expressive learned method
or retain the explicit two-family scope; independently adjudicate substantive external errors; freeze
review allocation and selector parameters; justify family/source sampling and power; then unlock the
reserved evaluation once. If credible external labels cannot be obtained, narrow the claim to controlled
robustness and decision abstention. A broad natural-error superiority claim is unsupported.
