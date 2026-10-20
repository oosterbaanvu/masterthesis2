# Practical use case: onboarding a source and deciding whether to add a learned check

Status: design description, 2026-10-20. The industry context comes from conversations with one data
engineer in a Rabobank-related department; it describes that department's practice, not bank policy, and
it has not yet been validated with a wider group of practitioners (see *Open questions* below).

## 1. The situation

A data-engineering team receives a recurring structured delivery (e.g. a monthly client/credit snapshot or
a campaign/contact extract). Before it is used downstream they already run conventional controls:

- schema, type and mandatory-field checks;
- documented domain checks (accepted codes, ranges);
- business rules and cross-field consistency;
- uniqueness and referential integrity;
- statistical thresholds and distribution monitoring;
- reconciliation against control totals;
- manual investigation of exceptions, with evidence (record id, failed rule, observed vs. expected value).

The engineer is asked: *"Should we add an ML-based check to this pipeline?"* Today there is no
systematic, reproducible way to answer that. Vendor tools and data-observability products claim that ML
finds what rules miss, but give no evidence for *this* source, *these* controls and *this* review capacity.

## 2. What the framework does

```
contract (YAML)  ──►  dbt models + tests (generated, versioned)  ──►  run on DuckDB, store failing rows
      │                                                                     │
      ▼                                                                     ▼
reference partition ──► fitted statistical bounds ──► (dbt)        exception table with evidence
      │
      ├──► learned detector fitted on reference (CDC per cell; Isolation Forest per record)
      ▼
evaluation partition ──► copies with controlled errors (catalog: operation × mechanism × seed)
      │
      ▼
which injected errors do the controls catch? which survive? does the detector recover survivors
within a fixed review budget, and how many extra alerts does it add on untouched data?
      │
      ▼
auditable report + machine-readable metrics + decision: ADOPT / DO_NOT_ADOPT / INSUFFICIENT_EVIDENCE
```

Commands (all from a clean checkout, see `README.md`):

```bash
python scripts/download_datasets.py            # acquire + verify sources
dqf controls generate                          # contract -> dbt models/tests
dqf controls check uci_credit                  # run the controls on the untouched table
dqf run config/experiments/demo_uci_credit.yaml --report reports/demo_uci_credit.md
```

## 3. Why an engineer would use it

| Need | How it is met | Evidence in this repo |
|---|---|---|
| Know what the existing checks miss | Recall per error type and mechanism for deterministic rules alone and with statistical controls ("surviving errors") | `reports/demo_*.md` |
| Evaluate ML without trusting a vendor claim | Increment *conditional on* the existing suite, at a fixed review budget | ΔR@k columns in the reports |
| Control alert fatigue | Alerts on untouched data per 1,000 rows, per rule and per detector column | report sections "alert burden" |
| Auditability | Versioned contract with evidence status per rule; generated dbt tests; failing rows with rule id, observed and expected value; run manifest with versions, hashes and configuration | `config/contracts/`, `dbt/models/generated/`, `results/runs/*/manifest.json` |
| New source with little code | Contract + scenario catalog entry; no code changes (Bank Marketing demo) | `config/contracts/uci_bank_marketing.yaml` |
| Explainable applicability | Compatibility check per detector (PASS / CONDITIONAL / INCOMPATIBLE with reasons and required transformations) before anything is run | `method_compatibility.md` |
| "No ML" is an acceptable answer | Decision rule includes DO_NOT_ADOPT and INSUFFICIENT_EVIDENCE | `evaluation.DecisionRule` |

## 4. What it deliberately does not do

- It does not replace production governance or monitoring tools, does not correct records, and does not
  estimate real error rates of any bank source.
- It does not certify a source as clean: alerts on untouched data are reported as burden to investigate,
  not as false positives.
- It is not a universal detector selector; it answers one question for one source, configuration and
  budget.
- No web front-end; the outputs are Markdown/CSV/Parquet that fit existing review and ticketing processes.

## 5. Engineering skills demonstrated

Data contracts and versioned validation rules; dbt Core on DuckDB with generated, store-failures tests;
reproducible data acquisition with pinned hashes and immutable raw data; Parquet-based exchange between
isolated environments; experiment configuration and run manifests; conformal prediction and anomaly
detection in production-like settings; statistical evaluation (budgeted metrics, bootstrap CIs, decision
rules); automated tests and CI. Optional later steps (not needed for the thesis): containerised isolated
environments, MLflow tracking, a Databricks/Azure execution target for the same dbt project.

## 6. Open questions for practitioners (to ask before the confirmatory run)

1. What review capacity (alerts per 1,000 records per delivery) is realistic for exception handling?
2. Which errors have actually been observed in deliveries (unit/scale, sign, mapping tables, column
   shifts, stale or partial deliveries), and roughly how often relative to each other?
3. Are errors typically concentrated in a source system, channel, product or delivery period (EAR-like),
   or in particular value ranges (ENAR-like)?
4. Which statistical controls are already in use (thresholds, distribution drift), and on what reference?
5. What evidence must an exception carry to be actionable?
6. Is a "record-level" alert (which client, not which field) useful, or must the field be identified?
7. How are rules versioned and reviewed today, and who signs off on a new check?
8. Under what conditions would the team accept an ML-based check (explainability, stability, cost)?

The answers set the budget k, the minimum gain in the decision rule and the mechanism scenarios that are
treated as realistic; until then they are documented assumptions.
