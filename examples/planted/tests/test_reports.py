import time

from shop.reports import nightly_report


def test_nightly_report_is_fast():  # a wall-clock budget: fails on a slow machine
    start = time.perf_counter()
    assert nightly_report() == "ok"
    assert time.perf_counter() - start < 0.2
