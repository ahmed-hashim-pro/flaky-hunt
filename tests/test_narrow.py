import random

import pytest

from flaky_hunt.hunt import narrow


def oracle(culprits, calls):
    def breaks(prefix):
        calls.append(list(prefix))
        return any(c in prefix for c in culprits)

    return breaks


@pytest.mark.parametrize("size", [1, 2, 3, 7, 50, 333])
def test_finds_the_one_culprit_wherever_it_is(size):
    rng = random.Random(size)
    tests = [f"t{i}" for i in range(size)]
    for _ in range(20):
        culprit = rng.choice(tests)
        calls: list = []
        assert narrow(tests, oracle([culprit], calls)) == culprit
        assert len(calls) <= 2 * size.bit_length() + 3


def test_nothing_breaks_it():
    assert narrow([f"t{i}" for i in range(10)], lambda p: False) is None
    assert narrow([], lambda p: True) is None


def test_two_culprits_returns_one_of_them():
    tests = [f"t{i}" for i in range(16)]
    assert narrow(tests, oracle(["t3", "t12"], [])) in {"t3", "t12"}


def test_needs_two_together_finds_none():
    tests = [f"t{i}" for i in range(16)]

    def breaks(prefix):
        return "t3" in prefix and "t12" in prefix

    assert narrow(tests, breaks) is None
