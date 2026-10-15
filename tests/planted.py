"""Runs a hunt on examples/planted and compares it with expected.json."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from flaky_hunt.hunt import Hunt, Report
from flaky_hunt.probes import default_probes
from flaky_hunt.runner import Runner

PLANTED = Path(__file__).resolve().parent.parent / "examples" / "planted"


def hunt(tmp_path: Path, factors: list[str], monkeypatch=None) -> Report:
    project = tmp_path / "planted"
    shutil.copytree(PLANTED, project)
    work = tmp_path / "work"
    work.mkdir()
    env = dict(__import__("os").environ)
    probes = [p for p in default_probes(env) if p.factor in factors]
    return Hunt(Runner(project, [], [], work), probes, confirm=8, workers=4).run()


def problems(report: Report, factors: list[str]) -> list[str]:
    """Everything about `report` that differs from expected.json, for the
    planted tests whose cause is among `factors`."""
    expected = json.loads((PLANTED / "expected.json").read_text())
    want = {t: e for t, e in expected.items() if e["factor"] in factors}
    out = []
    got: dict[str, list] = {}
    for d in report.diagnoses:
        got.setdefault(d.test, []).append(d)
    for t, e in want.items():
        ds = got.get(t, [])
        if [d.factor for d in ds] != [e["factor"]]:
            out.append(f"{t}: expected only {e['factor']}, got {[d.factor for d in ds]}")
            continue
        d = ds[0]
        if "culprit" in e and d.culprit != e["culprit"]:
            out.append(f"{t}: blamed {d.culprit!r}, expected {e['culprit']!r}")
        if "trigger" in e and e["trigger"] not in f"{d.trigger} | {d.passes}":
            out.append(f"{t}: trigger {d.trigger!r} / {d.passes!r}, expected {e['trigger']!r}")
    for t, ds in got.items():
        if t not in want:
            out.append(f"{t}: unexpected diagnosis {[d.factor + ': ' + d.trigger for d in ds]}")
    for t in report.unexplained:
        if t in want or t not in expected:  # others' causes are outside this hunt
            out.append(f"{t}: flaky with no cause found")
    for t in report.always_fail:
        if t in want:
            out.append(f"{t}: reported as failing every time")
    return out
