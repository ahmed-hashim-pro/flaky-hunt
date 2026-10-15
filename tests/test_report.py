import json

from flaky_hunt.hunt import Diagnosis, Rate, Report
from flaky_hunt.report import render, to_json


def diag(test, culprit="t::polluter", skipped=0):
    return Diagnosis(
        test,
        "order",
        f"run after {culprit}",
        "run on its own",
        Rate(8, 8),
        Rate(0, 8, skipped),
        1e-4,
        f"pytest {culprit} {test}",
        "boom",
        culprit,
    )


def report(ds):
    return Report(
        tests=[d.test for d in ds], diagnoses=ds, suite_runs=39, single_runs=100, seconds=75
    )


def test_one_cause_many_tests_is_one_group():
    ds = [diag(f"t::victim{i}") for i in range(9)]
    text = render(report(ds), ["order"])
    assert "9 tests fail when run after t::polluter" in text
    assert "t::victim5" in text and "t::victim6" not in text
    assert "… and 3 more (all in --json)" in text
    assert text.count("reproduce") == 1
    assert "1m 15s" in text


def test_two_tests_are_shown_one_by_one():
    text = render(report([diag("t::a"), diag("t::b")]), ["order"])
    assert text.count("reproduce") == 2


def test_skips_are_shown():
    text = render(report([diag("t::a", skipped=8)]), ["order"])
    assert "fails 0/8  (0%–32%), skipped in 8" in text


def test_json_lists_every_test_with_intervals():
    ds = [diag(f"t::victim{i}") for i in range(9)]
    data = json.loads(to_json(report(ds)))
    assert len(data["diagnoses"]) == 9 and len(data["flaky"]) == 9
    lo, hi = data["diagnoses"][0]["failing"]["interval"]
    assert round(lo, 2) == 0.68 and hi == 1.0
