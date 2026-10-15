"""Turns a hunt into the text a person reads, or JSON a machine reads."""

from __future__ import annotations

import json
import textwrap
from dataclasses import asdict

from .hunt import Diagnosis, Rate, Report


def _duration(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def render(report: Report, factors: list[str]) -> str:
    out: list[str] = []
    flaky = report.flaky()
    explained = {d.test for d in report.diagnoses}
    head = f"flaky-hunt: {len(report.tests)} tests, {len(flaky)} flaky"
    if flaky:
        head += f" ({len(explained)} with a cause found)"
    if report.always_fail:
        head += f", {len(report.always_fail)} failing in every run"
    out.append(head)
    out.append(
        f"{report.suite_runs} runs of the suite and {report.single_runs} of single tests "
        f"in {_duration(report.seconds)}"
    )

    # Tests that fail for the same reason (one polluter breaking 24 tests) are
    # shown as one group; everything is still listed one by one in --json.
    groups: dict[tuple[str, str, str], list[Diagnosis]] = {}
    for d in report.diagnoses:
        groups.setdefault((d.factor, d.trigger, d.culprit), []).append(d)
    shown: set[int] = set()
    for d in report.diagnoses:
        if id(d) in shown:
            continue
        group = groups[(d.factor, d.trigger, d.culprit)]
        if len(group) >= GROUP:
            out += _group(group)
            shown.update(id(g) for g in group)
        else:
            out += ["", d.test, *_block(d)]
            shown.add(id(d))

    for test, rate in report.unexplained.items():
        out.append("")
        out.append(test)
        out.append(f"  {'no cause':<11}  failed in {rate}; no single factor reproduced it")

    if report.always_fail:
        out.append("")
        out.append("failed in every run (not flaky under the factors tried):")
        out += [f"  {t}" for t in report.always_fail]

    out.append("")
    out.append("factors tried: " + ", ".join(factors))
    out.append("rates are failures in fresh processes, with 95% intervals")
    return "\n".join(out)


GROUP = 3  # this many tests failing for one reason are shown together
LIST = 6  # and this many of them by name


def _block(d: Diagnosis, rates_of: str = "") -> list[str]:
    out = []
    rows = _rows(d)
    width = max(len(label) for label, _ in rows)
    for n, (label, rate) in enumerate(rows):
        head = d.factor if n == 0 else ""
        lo, hi = rate.interval
        line = f"  {head:<11}  {label:<{width}}  fails {rate.fails}/{rate.runs}"
        line += f"  ({lo:.0%}–{hi:.0%})"
        if rate.skipped:
            line += f", skipped in {rate.skipped}"
        out.append(line)
    if d.message:
        out.append(f"  {'':<11}  " + textwrap.shorten(d.message, 90, placeholder=" …"))
    out.append(f"  {'reproduce':<11}  {d.command}")
    return out


def _group(group: list[Diagnosis]) -> list[str]:
    first = group[0]
    what = (
        f"fail when run after {first.culprit}"
        if first.factor == "order" and first.trigger.startswith("run after")
        else f"fail under: {first.trigger}"
    )
    out = ["", f"{len(group)} tests {what}"]
    out += [f"  {'tests' if n == 0 else '':<11}  {g.test}" for n, g in enumerate(group[:LIST])]
    if len(group) > LIST:
        out.append(f"  {'':<11}  … and {len(group) - LIST} more (all in --json)")
    same = all(
        (g.failing.fails, g.passing.fails) == (first.failing.fails, first.passing.fails)
        for g in group
    )
    out.append(
        f"  {'':<11}  "
        + ("the same rates for each:" if same else "rates for the first (they differ; see --json):")
    )
    out += _block(first)
    return out


def _rows(d: Diagnosis) -> list[tuple[str, Rate]]:
    if d.factor == "order" and d.trigger.startswith("run after"):
        rows = [(f"after {d.culprit}", d.failing), ("on its own", d.passing)]
    elif d.factor == "order":
        rows = [("on its own", d.failing), (f"after {d.culprit}", d.passing)]
    else:
        rows = [(d.trigger, d.failing), (d.passes, d.passing)]
    if d.as_is is not None:
        rows.append(("as-is", d.as_is))
    return rows


def to_json(report: Report) -> str:
    data = asdict(report)
    for d, src in zip(data["diagnoses"], report.diagnoses, strict=True):
        d["failing"]["interval"] = src.failing.interval
        d["passing"]["interval"] = src.passing.interval
        if src.as_is is not None:
            d["as_is"]["interval"] = src.as_is.interval
    data["flaky"] = report.flaky()
    return json.dumps(data, indent=2)
