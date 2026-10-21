#!/usr/bin/env python
"""Re-score existing, frozen dirty-only published scans under the new shared-total-budget policy.

No new errors, no fitting, no original experiment overwrite. The earlier predictions and their input
hashes remain the provenance; this is a new cost-policy analysis of those same dependent batches.
"""

import json

import numpy as np
import pandas as pd
import yaml

from analyse_thesis_study import NO_ADDITION, choose, load_runs, require_complete_study
from dq_framework import paths
from dq_framework.acquisition import load_registry, sha256_file
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_pair
from dq_framework.evaluation.published import label_cells
from dq_framework.pilot.total_budget import queues


def main():
    output = paths.RESULTS_DIR / "thesis_integrated"
    controlled_root = paths.RESULTS_DIR / "runs/thesis_integrated"
    require_complete_study(controlled_root)
    controlled, *_ = load_runs(controlled_root)
    controlled["case_key"] = controlled.dataset + "|" + controlled.case_id
    spec = yaml.safe_load((paths.CONFIG_DIR / "thesis/study.yaml").read_text())
    root = paths.RESULTS_DIR / "runs/real_error_benchmark"
    plan = json.loads((root / "completed_scans.json").read_text())
    registry = load_registry()
    labels = {}
    for dataset in plan["protocol"]["datasets"]:
        dirty, clean = load_pair(registry[dataset])
        contract = load_contract(dataset)
        ids = dirty[contract.row_id].astype(int) if contract.row_id else pd.Series(dirty.index + 1)
        eligible = set()
        for job in plan["jobs"]:
            if job["dataset"] == dataset:
                p = pd.read_csv(root / job["directory"] / "partitions.csv")
                eligible.update(p.loc[p.partition == "batch", "_row_id"])
        mask = ids.isin(eligible)
        labels[dataset] = label_cells(dataset, dirty[mask], clean[mask], contract)
    metrics = []
    # The earlier Cars CDC snapshot used 32 calibration rows. This study fixes 512, which its
    # tiny historical batches cannot support. Do not silently transfer a different configuration.
    mapping = {"dboost_gaussian": "dboost_typed", "dboost_gaussian_text": "dboost_text"}
    for job in plan["jobs"]:
        folder = root / job["directory"]
        for filename, sha in job["output_sha256"].items():
            if sha256_file(folder / filename) != sha:
                raise ValueError(f"Existing published prediction artifact changed: {folder / filename}")
        dataset = job["dataset"]
        p = pd.read_csv(folder / "partitions.csv")
        ids = p.loc[p.partition == "batch", "_row_id"].to_list()
        cols = load_contract(dataset).column_names
        rowpos, colpos = {int(r): i for i, r in enumerate(ids)}, {c: i for i, c in enumerate(cols)}
        shape = len(ids), len(cols)

        def array(frame, value=None, shape=shape, rowpos=rowpos, colpos=colpos):
            out = np.zeros(shape, bool) if value is None else np.full(shape, np.nan)
            for _, r in frame.iterrows():
                if int(r['_row_id']) in rowpos and r['column'] in colpos:
                    out[rowpos[int(r['_row_id'])], colpos[r['column']]] = True if value is None else r[value]
            return out

        label = labels[dataset]
        truth = array(label[label.label.isin(['missing', 'value_candidate'])])
        uncertain = array(label[label.label.isin(['uncertain', 'reference_missing'])])
        controls = pd.read_parquet(folder / "control_cells.parquet")
        scores = pd.read_parquet(folder / "detector_scores.parquet")
        summary = json.loads((folder / "scan_summary.json").read_text())
        compatible = {d['detector']: d for d in summary['detectors'] if d['status'] == 'ok'}
        for baseline in ('deterministic', 'full'):
            base = array(controls if baseline == 'full' else controls[controls.tier == 'deterministic'])
            for budget in spec['total_budgets']:
                k = int(round(budget * len(ids) / 1000))
                for key, target_key in mapping.items():
                    if target_key not in compatible:
                        continue
                    rows = scores[scores.detector == target_key]
                    flags = array(rows[rows.flag])
                    score = array(rows, 'score')
                    b, mixed, _ = queues(base, flags, score, k)
                    gain = float(((mixed & truth).sum() - (b & truth).sum()) / truth.sum()) if truth.any() else np.nan
                    metrics.append({'dataset': dataset, 'seed': job['seed'], 'baseline': baseline, 'budget': budget,
                                    'detector': key, 'utility': gain, 'reference_error_labels': int(truth.sum()),
                                    'reviews': int(mixed.sum()), 'unknown_reviews': int((mixed & uncertain).sum()),
                                    'positive_hits': int((mixed & truth).sum()), 'base_hits': int((b & truth).sum())})
    metrics = pd.DataFrame(metrics)
    metrics.to_csv(output / 'published_total_budget.csv', index=False)
    decisions = []
    for (dataset, baseline, budget), target in metrics.groupby(['dataset', 'baseline', 'budget']):
        eligible = set(target.detector)
        target_mean = target.groupby('detector').utility.mean()
        for strategy in ('simple', 'diverse'):
            train = controlled[(controlled.baseline == baseline) & (controlled['set'] == f'sel_{strategy}')
                               & (controlled.role == 'primary') & controlled.detector.isin(eligible)].copy()
            train['utility'] = train[f'total_delta@{budget}']
            for robust in (False, True):
                choice, decision, score = choose(train, spec['robust'], robust)
                scorable = target.reference_error_labels.sum() > 0
                gain = (0.0 if choice == NO_ADDITION else float(target_mean[choice])) if scorable else np.nan
                oracle = max(0.0, target_mean.max()) if scorable else np.nan
                decisions.append({'dataset': dataset, 'baseline': baseline, 'budget': budget, 'strategy': strategy,
                                  'selector': 'robust' if robust else 'naive', 'choice': choice, 'decision': decision,
                                  'status': 'REFERENCE_RELATIVE_SYNTHETIC' if scorable else 'UNADJUDICATED_NOT_SCORABLE',
                                  'utility': gain, 'oracle_utility': oracle, 'regret': oracle - gain})
    pd.DataFrame(decisions).to_csv(output / 'published_transfer.csv', index=False)
    (output / 'published_prediction_provenance.json').write_text(json.dumps({
        'source_plan_sha256': plan['plan_sha256'], 'new_policy': spec['budget_policy'],
        'note': 'Reused earlier frozen dirty-only predictions. No new model fit or injection. Not new independent replications.'}, indent=2)+'\n')
    print('Published total-budget evaluation and simulation-selector transfer saved.')


if __name__ == '__main__':
    main()
