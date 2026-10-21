import json

import pandas as pd
import pytest
from scripts.analyse_thesis_study import NO_ADDITION, assess, choose, load_runs

RULE = {'bootstrap_replicates': 1000, 'lower_quantile': .1, 'minimum_lower_gain': .005,
        'worst_family_floor': -.01, 'min_cases': 3, 'seed': 0}


def frame(values):
    return pd.DataFrame([{'case_key': str(i), 'family': str(i % 2), 'detector': d, 'utility': v}
                         for d, vs in values.items() for i, v in enumerate(vs)])


def test_naive_no_addition_and_robust_abstention():
    f = frame({'a': [-.2, -.1, 0, 0], 'b': [0, 0, 0, 0]})
    assert choose(f, RULE)[0] == NO_ADDITION
    f = frame({'a': [1, -.1, -.1, -.1], 'b': [.01, .01, .01, .01]})
    assert choose(f, RULE)[0] == 'a'
    assert choose(f, RULE, robust=True)[0] == 'b'


def test_repeating_dependent_seeds_does_not_inflate_case_count():
    f = frame({'a': [.1, .1]})
    repeated = pd.concat([f] * 100, ignore_index=True)
    assert choose(repeated, RULE, robust=True)[1] == 'INSUFFICIENT_EVIDENCE'


def test_target_labels_change_regret_but_not_selection():
    training = frame({'a': [.1, .1, .1], 'b': [.02, .02, .02]})
    target = frame({'a': [-.1, -.1, -.1], 'b': [.3, .3, .3]})
    decisions = assess(training, target, RULE, {})
    assert all(d['choice'] == 'a' and d['oracle'] == 'b' for d in decisions)
    assert all(abs(d['regret'] - .4) < 1e-12 for d in decisions)
    reversed_target = target.assign(utility=-target.utility)
    assert [d['choice'] for d in assess(training, reversed_target, RULE, {})] == ['a', 'a']


def test_incompatible_target_method_is_absent_from_selection_not_zero_filled():
    training = frame({'a': [.5, .5, .5], 'b': [.1, .1, .1]})
    target = frame({'b': [.2, .2, .2]})
    assert all(d['choice'] == 'b' and d['regret'] == 0 for d in assess(training, target, RULE, {}))


def test_analysis_rejects_modified_prediction_artifact(tmp_path):
    (tmp_path / 'frozen_inputs.json').write_text(json.dumps({'digest': 'frozen'}))
    run = tmp_path / 'one_run'
    run.mkdir()
    (run / 'complete.json').write_text(json.dumps({'input_digest': 'frozen', 'outputs': {'scores.csv': 'expected'}}))
    (run / 'scores.csv').write_text('changed')
    with pytest.raises(ValueError, match='Run output changed'):
        load_runs(tmp_path)
