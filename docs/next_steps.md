# Next steps

Status: 2026-10-20. Ordered by dependency. "User" = actions only the student (or supervisor) can take.

## A. Actions for the student / supervisors

1. **Review the recommended research question** (`research_directions.md` §3) and the decision log entries
   marked *provisional* (D-03, D-05, D-07, D-08, D-10, D-11, D-13, D-15) with the university supervisors.
2. **Obtain the full text of Jung et al. (JDIQ 2025, open access, DOI 10.1145/3774914)** via university
   access and quote the formal ECAR/EAR/ENAR definitions (§3 of the paper); check whether the paper reports
   rank changes between mechanisms. The ACM site was not reachable from this environment.
3. **Ask the industry contact the eight questions** in `practical_use_case.md` §6 (review capacity, observed
   error types and their concentration, statistical controls in use). The answers fix the review budget k,
   the minimum gain δ and which mechanism scenarios count as realistic.
4. **Optional – BAF:** only if a monthly-batch synthetic bank dataset at scale is still wanted. Download is
   now scripted (`scripts/download_baf.py`, Kaggle token); still requires supervisor/legal confirmation of the non-commercial licence (NC-ND per the
   datasheet, NC-SA per Kaggle). Bank Marketing currently covers the batch role.
5. Optionally read the 2025 University of Twente MSc thesis on ensemble anomaly detection for credit-risk
   data quality (`madaras2025ensemble` in `references.bib`) to differentiate the contribution.
6. Decide whether to report the tab_err findings upstream (CategorySwap per-category mapping, mask includes
   unchanged cells, frequency weighing not seeded). This is an external action and was not done.

## B. Implementation before the confirmatory study

1. **Freeze the baseline**: review every contract rule with its evidence; add a *documented-only* baseline
   variant (rules with status `verified` only) to measure the effect of baseline strength.
2. **Mechanism-strength grid**: extend the scenario catalog with soft strengths {0, 1, 2, 4, 8}, ENAR
   direction low/high and a second EAR conditioning attribute per dataset (with rationale).
3. **Decision-reliability module**: implement leave-one-condition-out evaluation (mechanism shape, strength,
   error family, dataset, temporal) producing agreement, dominance-aware reference and regret.
4. **Power analysis by simulation** from the demo results to fix split seeds and injection seeds.
5. **Hierarchical analysis** script (mixed-effects or Bayesian) over split seeds.
6. **Parallel execution**: run scenarios in chunks per process with `OMP_NUM_THREADS`, or on a small cloud
   VM; record runtime per stage (already in manifests).
7. Freeze detector configuration on dev data (CDC confidence 0.99 vs 0.999; base quantile; Isolation
   Forest alert rate) and tag the repository before touching test partitions.

## C. Confirmatory study (after A and B)

Run `research_design.md` on new split seeds and test partitions; report all scenarios, decisions, regret,
null results and failures. Then the bounded validity checks (Tax out-of-generator; Raha on Flights).

## D. Engineering polish (only if time permits)

Docker images for the isolated environments; MLflow or a lightweight run index; HTML rendering of reports;
dbt `docs generate` for the generated models; optional Databricks/Azure target for the same dbt project.

## E. Explicitly out of scope

Multi-table inconsistency detection as a research objective; LLM-based detectors; automatic correction;
building a real-error financial benchmark (SEC amendments) – future work; any claim about real error rates
in bank sources.
