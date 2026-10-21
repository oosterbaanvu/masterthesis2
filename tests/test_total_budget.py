import numpy as np

from dq_framework.pilot.total_budget import metrics, queues


def test_baseline_credit_is_not_free_and_novel_cells_can_displace_hits():
    inj = np.array([[True, True, False, False]])
    base = np.array([[True, True, False, False]])
    flags = np.array([[False, False, True, True]])
    b, mix, solo = queues(base, flags, None, 2)
    assert b.sum() == mix.sum() == solo.sum() == 2
    assert (b & inj).sum() == 2 and (mix & inj).sum() == 1
    m = metrics(inj, base, flags, None, (2000,))
    assert m['total_delta@2000'] == -.5
    assert m['total_displaced_hits@2000'] == 1


def test_binary_no_flags_do_not_invent_scores_or_pad_nonalerts():
    z = np.zeros((3, 2), bool)
    b, mix, solo = queues(z, z, None, 3)
    assert b.sum() == mix.sum() == solo.sum() == 0


def test_budget_unique_finite_and_no_greater_than_capacity():
    b = np.array([[True, False, True, False]])
    f = np.ones_like(b)
    s = np.array([[.9, np.nan, .2, .7]])
    for k in (0, 1, 2, 8):
        x, y, z = queues(b, f, s, k)
        assert x.sum() <= k and y.sum() <= k and z.sum() <= k
        assert not z[0, 1]
        np.testing.assert_array_equal(y, queues(b, f, s, k)[1])
