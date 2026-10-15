"""The two pieces of statistics a report rests on."""

from __future__ import annotations

from math import comb, sqrt

from . import mutants


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a failure rate of k in n.

    Wilson's interval rather than the textbook one: with 0 of 8 or 8 of 8,
    which is what a reproduced flake usually looks like, the textbook
    interval collapses to a single point and claims certainty it doesn't have.
    """
    if n == 0:
        return 0.0, 1.0
    p = k / n
    if mutants.active("wald-interval"):
        half = z * sqrt(p * (1 - p) / n)
        return max(0.0, p - half), min(1.0, p + half)
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def fisher_greater(a_fail: int, a_n: int, b_fail: int, b_n: int) -> float:
    """One-sided Fisher exact test: is group A's failure rate higher than B's?

    Returns the probability of A seeing at least a_fail of the failures if
    the setting made no difference.
    """
    fails = a_fail + b_fail
    total = a_n + b_n
    if fails == 0:
        return 1.0
    denom = comb(total, fails)
    p = 0
    for x in range(a_fail, min(a_n, fails) + 1):
        p += comb(a_n, x) * comb(b_n, fails - x)
    return p / denom
