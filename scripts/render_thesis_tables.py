#!/usr/bin/env python
"""Regenerate the report's descriptive tables from committed study summaries (no fitting)."""

import pandas as pd

from dq_framework import paths


def table(frame, *, trailing=True):
    def cell(v):
        if isinstance(v, float):
            return '—' if pd.isna(v) else f'{v:.3f}'
        return str(v).replace('|', '/').replace('<', '&lt;').replace('>', '&gt;')
    print('| ' + ' | '.join(map(str, frame.columns)) + ' |')
    print('|' + '|'.join('---' for _ in frame.columns) + '|')
    for row in frame.itertuples(index=False, name=None):
        print('| ' + ' | '.join(cell(v) for v in row) + ' |')
    if trailing:
        print()


def main():
    root = paths.RESULTS_DIR / 'thesis_integrated'
    runtime = pd.read_csv(root / 'runtime.csv')
    runs = runtime.drop_duplicates(['dataset', 'scheme', 'pilot_seed'])
    print('### Completed runs\n')
    table(runs.groupby(['dataset', 'scheme']).agg(runs=('pilot_seed', 'size'),
        scenarios=('scenarios', 'sum'), failed=('failed_scenarios', 'sum'),
        elapsed_s=('elapsed_s', 'sum'), reserved=('holdout_excluded', 'min')).reset_index())
    print('Scenario counts include selection, target and sanity cases. Time is summed job time, not wall time.\n')
    cases = pd.read_csv(root / 'case_metrics.csv')
    uncertainty = pd.read_csv(root / 'case_uncertainty.csv')
    print('### Primary shared-budget results\n')
    print('Budget 25/1,000. Recall quantities below are percentages; gain and interval endpoints are percentage points. '
          'Each error case receives equal weight after dependent observations are averaged.\n')
    c = cases[cases.budget == 25].groupby(['dataset', 'baseline', 'detector'])[
        ['base_recall', 'solo_recall', 'recall', 'utility', 'precision_lb', 'ap_all_scored', 'scored_positive_coverage']].mean().reset_index()
    c = c.merge(uncertainty[['dataset', 'baseline', 'detector', 'conditional_case_ci_lo', 'conditional_case_ci_hi']],
                on=['dataset', 'baseline', 'detector'], validate='one_to_one')
    for col in c.columns[3:]:
        c[col] *= 100
    table(c)
    print('### Budget sensitivity\n')
    c = cases.groupby(['dataset', 'baseline', 'budget', 'detector']).utility.mean().mul(100).unstack('budget').reset_index()
    table(c)
    print('### Family variation\n')
    c = cases[(cases.budget == 25) & (cases.baseline == 'full')]
    table(c.groupby(['dataset', 'detector', 'family']).utility.mean().mul(100).unstack('family').reset_index())
    print('### Placement mechanism contrasts\n')
    print('Matched test-diverse cases, full baseline, budget 25. EAR/ENAR minus ECAR gain in percentage points; '
          'descriptive averages, no independent-seed inference.\n')
    m = pd.concat([pd.read_csv(p) for p in sorted(root.glob('matched_mechanisms_*.csv'))])
    idx = ['dataset', 'pilot_seed', 'scheme', 'case_id', 'rate', 'detector']
    m = m[(m.budget == 25) & (m.baseline == 'full')].pivot(index=idx, columns='mechanism_class', values='utility')
    for mech in ('EAR', 'ENAR'):
        if mech in m and 'ECAR' in m:
            m[mech + '_minus_ECAR'] = 100 * (m[mech] - m.ECAR)
    table(m.reset_index().groupby(['dataset', 'detector'])[[c for c in m if c.endswith('_minus_ECAR')]].mean().reset_index())
    decisions = pd.read_csv(root / 'selection.csv')
    print('### Selector performance\n')
    print('Budget 25, full baseline. Regret/utility are recall fractions. Rates are descriptive dependent conditions.\n')
    d = decisions[(decisions.budget == 25) & (decisions.baseline == 'full')].copy()
    d['condition'] = d.condition.str.replace(r'^unseen_family:.*', 'unseen_family (pooled)', regex=True)
    table(d.groupby(['dataset', 'condition', 'selector']).agg(regret=('regret', 'mean'),
        utility=('target_utility', 'mean'), agreement=('exact_agreement', 'mean'),
        no_addition=('choice', lambda s: (s == 'NO_ADDITION').mean()),
        insufficient=('decision', lambda s: (s == 'INSUFFICIENT_EVIDENCE').mean()),
        net_added_hits=('target_net_added_hits_per_scenario', 'mean'), decisions=('choice', 'size')).reset_index())
    print('### Paired selection-design contrast\n')
    p = pd.read_csv(root / 'paired_designs.csv')
    p = p[(p.budget == 25) & (p.condition == 'test_heldout')]
    table(p.groupby(['dataset', 'baseline', 'selector']).diverse_minus_simple_regret.mean().reset_index())
    print('Negative means diverse selection has lower regret; zero means no observed difference.\n')
    print('### Native alert workload\n')
    w = pd.read_csv(root / 'untouched_workload.csv')
    w = w[(w.partition == 'test') & (w.baseline == 'full')]
    table(w.groupby(['dataset', 'detector'])[['alerts_per_1k', 'flags_per_1k']].mean().reset_index())
    print('For detectors, alerts_per_1k counts native flags absent from full controls, while flags_per_1k counts all native flags. '
          'The baseline row counts total rule alerts. These are burden, not verified false positives.\n')
    print('### Detector runtime\n')
    table(runtime.groupby(['dataset', 'detector'])[['fit_seconds', 'score_seconds']].mean().reset_index())
    print('### Published shared-budget transfer\n')
    p = pd.read_csv(root / 'published_transfer.csv')
    p = p[p.budget == 25]
    table(p.groupby(['dataset', 'baseline', 'selector', 'status'], dropna=False).agg(
        choice=('choice', lambda s: ', '.join(sorted(set(s)))), utility=('utility', 'mean'), regret=('regret', 'mean')).reset_index())
    failures = pd.read_csv(root / 'failures.csv')
    print('### Failed injection scenarios\n')
    table(failures.groupby(['dataset', 'case_id', 'stage', 'error']).size().rename('count').reset_index(), trailing=False)


if __name__ == '__main__':
    main()
