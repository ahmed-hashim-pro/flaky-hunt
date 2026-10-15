"""End to end: flaky-hunt on a suite whose nine flaky tests have known causes."""

import pytest

from flaky_hunt.probes import FACTORS

from .planted import hunt, problems

pytestmark = pytest.mark.slow


def test_every_planted_cause_found(tmp_path):
    report = hunt(tmp_path, list(FACTORS))
    assert problems(report, list(FACTORS)) == []
    assert len(report.flaky()) == 9


# Smaller hunts, each aimed at what one mutant breaks (see scripts/mutants.py).


def test_order(tmp_path):
    assert problems(hunt(tmp_path, ["order"]), ["order"]) == []


def test_environment(tmp_path):
    assert problems(hunt(tmp_path, ["environment"]), ["environment"]) == []


def test_timezone(tmp_path):
    assert problems(hunt(tmp_path, ["timezone"]), ["timezone"]) == []


def test_noise_not_blamed(tmp_path):
    """The hash-order and unseeded tests fail at random under every setting;
    only their own knob may be confirmed as the cause."""
    factors = ["timezone", "random", "timing"]
    assert problems(hunt(tmp_path, factors), factors) == []
