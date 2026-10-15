import pytest

from flaky_hunt.stats import fisher_greater, wilson


def test_wilson_known_values():
    lo, hi = wilson(8, 8)
    assert lo == pytest.approx(0.6756, abs=1e-3) and hi == 1.0
    lo, hi = wilson(0, 8)
    assert lo == 0.0 and hi == pytest.approx(0.3244, abs=1e-3)
    lo, hi = wilson(3, 10)
    assert lo == pytest.approx(0.1078, abs=1e-3) and hi == pytest.approx(0.6032, abs=1e-3)


def test_wilson_never_claims_certainty_from_few_runs():
    # 0 failures in 8 runs does not mean the rate is 0.
    assert wilson(0, 8)[1] > 0.25
    assert wilson(8, 8)[0] < 0.75


def test_wilson_no_runs():
    assert wilson(0, 0) == (0.0, 1.0)


def test_fisher_known_values():
    assert fisher_greater(8, 8, 0, 8) == pytest.approx(1 / 12870)
    assert fisher_greater(8, 8, 4, 8) == pytest.approx(70 / 1820)
    assert fisher_greater(0, 8, 0, 8) == 1.0
    assert fisher_greater(4, 8, 4, 8) > 0.5


def test_fisher_is_one_sided():
    assert fisher_greater(0, 8, 8, 8) == 1.0
