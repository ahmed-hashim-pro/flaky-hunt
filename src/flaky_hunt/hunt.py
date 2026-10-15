"""Find which tests flake, and which single factor makes each one fail.

1. Probe: run the whole suite as-is three times, then once under every
   setting in probes.py.
2. Suspect: a test that failed under some setting of a factor and passed
   under another value of the same knob (or as-is) is a suspect for that
   factor.
3. Confirm: run the suspect test on its own, in fresh processes, n times
   under the failing setting and n times under the passing one. The factor
   is the cause only if the failing setting fails significantly more often
   (one-sided Fisher exact test). This is what keeps a test that fails at
   random from being blamed on whatever setting it happened to fail under.
4. Order is different: a test that fails in some order but passes alone is
   bisected down to the one earlier test that breaks it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import mutants
from .probes import CONTROL, Setting
from .runner import Outcome, Runner, shuffled
from .stats import fisher_greater, wilson


@dataclass
class Rate:
    fails: int
    runs: int
    skipped: int = 0  # runs where the test was skipped (they count as not failing)

    @property
    def interval(self) -> tuple[float, float]:
        return wilson(self.fails, self.runs)

    def __str__(self) -> str:
        lo, hi = self.interval
        return f"{self.fails}/{self.runs} ({lo:.0%}–{hi:.0%})"


@dataclass
class Diagnosis:
    test: str
    factor: str
    trigger: str  # what makes it fail
    passes: str  # what it passes under
    failing: Rate
    passing: Rate
    p_value: float
    command: str  # reproduces the failure
    message: str  # the failure, from a failing run
    culprit: str = ""  # order only: the test that breaks it (or that it needs)
    as_is: Rate | None = None  # run alone, unperturbed, when neither side above is that


@dataclass
class Report:
    tests: list[str]
    diagnoses: list[Diagnosis] = field(default_factory=list)
    unexplained: dict[str, Rate] = field(default_factory=dict)
    always_fail: list[str] = field(default_factory=list)
    suite_runs: int = 0
    single_runs: int = 0
    seconds: float = 0.0
    run_seconds: float = 0.0

    def flaky(self) -> list[str]:
        seen = dict.fromkeys(d.test for d in self.diagnoses)
        seen.update(dict.fromkeys(self.unexplained))
        return list(seen)


Progress = Callable[[str], None]


class Hunt:
    def __init__(
        self,
        runner: Runner,
        probes: list[Setting],
        confirm: int = 8,
        alpha: float = 0.01,
        workers: int = 4,
        isolated_max: int = 200,
        progress: Progress | None = None,
    ):
        self.runner = runner
        self.probes = probes
        self.n = confirm
        self.alpha = alpha
        self.workers = max(1, workers)
        self.isolated_max = isolated_max
        self.say = progress or (lambda s: None)
        self._alone: dict[tuple[str, Setting], tuple[Rate, str]] = {}

    # ------------------------------------------------------------ driver

    def run(self) -> Report:
        start = time.monotonic()
        ids = self.runner.collect()
        report = Report(tests=ids)
        self.say(f"collected {len(ids)} tests")

        jobs: list[tuple[Setting, list[str] | None]] = [(CONTROL, None)] * 3
        for s in self.probes:
            jobs.append((s, shuffled(ids, s.order) if s.order else None))
        self.say(f"probing: {len(jobs)} runs of the whole suite")
        results = self._map(lambda j: (j[0], j[1], self.runner.run(j[0], order=j[1])), jobs)
        control = [r for s, _, r in results if s is CONTROL]
        probes = [(s, o, r) for s, o, r in results if s is not CONTROL]

        isolated: dict[str, Outcome] = {}
        if "order" in {s.factor for s in self.probes} and len(ids) <= self.isolated_max:
            self.say(f"running each of the {len(ids)} tests on its own")
            alone = self._map(lambda t: (t, self.runner.run(CONTROL, nodeids=[t])), ids)
            isolated = {t: r[t] for t, r in alone if t in r}

        suspects: list[Callable[[], Diagnosis | None]] = []
        for t in ids:
            ctrl = [r[t] for r in control if t in r]
            seen = ctrl + [r[t] for _, _, r in probes if t in r]
            if not any(o.failed for o in seen):
                continue
            if all(o.failed for o in seen) and (t not in isolated or isolated[t].failed):
                report.always_fail.append(t)
                continue
            suspects += self._suspects(t, ids, ctrl, probes, isolated.get(t))

        self.say(f"confirming {len(suspects)} suspects, {self.n} runs a side")
        found = [d for d in self._map(lambda f: f(), suspects) if d is not None]
        found = _dedupe(found)
        report.diagnoses = sorted(found, key=lambda d: (ids.index(d.test), d.factor))

        explained = {d.test for d in report.diagnoses}
        for t in ids:
            if t in explained or t in report.always_fail:
                continue
            fails = sum(r[t].failed for _, _, r in probes if t in r)
            fails += sum(r[t].failed for r in control if t in r)
            if fails:
                runs = sum(t in r for _, _, r in probes) + sum(t in r for r in control)
                report.unexplained[t] = Rate(fails, runs)

        report.suite_runs = self.runner.suite_runs
        report.single_runs = self.runner.single_runs
        report.run_seconds = self.runner.seconds
        report.seconds = time.monotonic() - start
        return report

    def _map(self, fn, items):
        with ThreadPoolExecutor(self.workers) as pool:
            return list(pool.map(fn, items))

    # ------------------------------------------------------------ suspects

    def _suspects(
        self, t: str, ids: list[str], ctrl: list[Outcome], probes, isolated: Outcome | None
    ) -> list[Callable[[], Diagnosis | None]]:
        out: list[Callable[[], Diagnosis | None]] = []
        ctrl_pass = any(not o.failed for o in ctrl)
        ctrl_fail = any(o.failed for o in ctrl)

        by_knob: dict[str, list[tuple[Setting, list[str] | None, Outcome]]] = {}
        for s, order, r in probes:
            if t in r:
                by_knob.setdefault(s.knob, []).append((s, order, r[t]))

        for knob, seen in by_knob.items():
            if knob == "order":
                continue
            failing = [s for s, _, o in seen if o.failed]
            passing = [s for s, _, o in seen if not o.failed]
            if failing:
                # Compare against another value of the same knob if one passed
                # (seed 3 against seed 1), otherwise against running as-is.
                s_fail = failing[0]
                others = [s for s in passing if s != s_fail]
                s_pass = others[0] if others else (CONTROL if ctrl_pass else None)
            elif ctrl_fail and passing:
                s_fail, s_pass = CONTROL, passing[0]  # fails as-is, passes under this
            else:
                continue
            if s_pass is None:
                continue
            factor = seen[0][0].factor
            msg = next((o.message for s, _, o in seen if s == s_fail and o.failed), "")
            out.append(
                lambda t=t, a=s_fail, b=s_pass, f=factor, m=msg: self._confirm(t, f, a, b, m)
            )

        if "order" in by_knob and all(not o.failed for o in ctrl):
            for _, order, o in by_knob["order"]:
                if o.failed and order is not None:
                    out.append(lambda t=t, order=order, m=o.message: self._polluter(t, order, m))
                    break
        if isolated is not None and isolated.failed and ctrl and not ctrl_fail:
            out.append(lambda t=t, m=isolated.message: self._needs(t, ids, m))
        return out

    # ------------------------------------------------------------ confirming

    def _rate(self, t: str, s: Setting, prefix: tuple[str, ...] = ()) -> tuple[Rate, str]:
        key = (t if not prefix else " ".join(prefix + (t,)), s)
        if key not in self._alone:
            fails, skipped, message = 0, 0, ""
            for _ in range(self.n):
                o = self.runner.run(s, nodeids=[*prefix, t]).get(t)
                if o is not None and o.failed:
                    fails += 1
                    message = message or o.message
                elif o is not None and o.outcome == "skipped":
                    skipped += 1
            self._alone[key] = (Rate(fails, self.n, skipped), message)
        return self._alone[key]

    def _confirm(
        self, t: str, factor: str, s_fail: Setting, s_pass: Setting, message: str
    ) -> Diagnosis | None:
        if mutants.active("no-confirm"):
            bad, good = Rate(1, 1), Rate(0, 1)
            p = 0.0
        else:
            bad, m = self._rate(t, s_fail)
            good, _ = self._rate(t, s_pass)
            message = m or message
            p = fisher_greater(bad.fails, bad.runs, good.fails, good.runs)
            if p >= self.alpha:
                return None
        d = Diagnosis(
            t, factor, s_fail.label, s_pass.label, bad, good, p, s_fail.command([t]), message
        )
        if CONTROL not in (s_fail, s_pass) and not mutants.active("no-confirm"):
            d.as_is = self._rate(t, CONTROL)[0]
        return d

    def _oracle(self, t: str, want_fail: bool):
        def check(prefix: list[str]) -> bool:
            o = self.runner.run(CONTROL, nodeids=[*prefix, t]).get(t)
            return o is not None and o.failed == want_fail

        return check

    def _polluter(self, t: str, order: list[str], message: str) -> Diagnosis | None:
        before = order[: order.index(t)]
        alone, _ = self._rate(t, CONTROL)
        if alone.fails:
            return None
        if mutants.active("blame-last"):
            culprit = before[-1] if before else None
        else:
            culprit = narrow(before, self._oracle(t, want_fail=True))
        if culprit is None:
            return None
        bad, m = self._rate(t, CONTROL, (culprit,))
        p = fisher_greater(bad.fails, bad.runs, alone.fails, alone.runs)
        if p >= self.alpha and not mutants.active("blame-last"):
            return None
        return Diagnosis(
            t,
            "order",
            f"run after {culprit}",
            "run on its own",
            bad,
            alone,
            p,
            CONTROL.command([culprit, t]),
            m or message,
            culprit,
        )

    def _needs(self, t: str, ids: list[str], message: str) -> Diagnosis | None:
        before = ids[: ids.index(t)]
        alone, m = self._rate(t, CONTROL)
        culprit = narrow(before, self._oracle(t, want_fail=False))
        if culprit is None:
            return None
        paired, _ = self._rate(t, CONTROL, (culprit,))
        p = fisher_greater(alone.fails, alone.runs, paired.fails, paired.runs)
        if p >= self.alpha:
            return None
        return Diagnosis(
            t,
            "order",
            "run on its own",
            f"run after {culprit}",
            alone,
            paired,
            p,
            CONTROL.command([t]),
            m or message,
            culprit,
        )


def narrow(before: list[str], breaks: Callable[[list[str]], bool]) -> str | None:
    """The single test in `before` that, run just ahead of the victim, makes
    `breaks` true. Halves the list while one half alone still breaks it, then
    checks the remaining candidates one by one."""
    cands = list(before)
    if not cands or not breaks(cands):
        return None
    while len(cands) > 1:
        half = len(cands) // 2
        if breaks(cands[:half]):
            cands = cands[:half]
        elif breaks(cands[half:]):
            cands = cands[half:]
        else:
            break  # it takes tests from both halves together
    for c in cands:
        if breaks([c]):
            return c
    return None


def _dedupe(found: list[Diagnosis]) -> list[Diagnosis]:
    seen: set[tuple[str, str]] = set()
    out = []
    for d in found:
        if (d.test, d.factor) not in seen:
            seen.add((d.test, d.factor))
            out.append(d)
    return out
