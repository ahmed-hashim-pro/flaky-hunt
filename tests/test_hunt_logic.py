"""The hunt's decisions, against a fake runner whose rules are known exactly."""

from flaky_hunt.hunt import Hunt
from flaky_hunt.probes import Setting, default_probes
from flaky_hunt.runner import Outcome

IDS = ["t::setter", "t::needs_setter", "t::victim", "t::polluter", "t::zone", "t::fine"]


class FakeRunner:
    """victim fails if polluter ran before it; needs_setter fails unless setter
    ran before it; zone fails under any TZ other than UTC."""

    def __init__(self):
        self.suite_runs = self.single_runs = 0
        self.seconds = 0.0

    def collect(self):
        return list(IDS)

    def run(self, setting: Setting, nodeids=None, order=None):
        if nodeids is None:
            self.suite_runs += 1
        else:
            self.single_runs += 1
        seq = nodeids or order or IDS
        tz = dict(setting.env).get("TZ", "UTC")
        out = {}
        for i, t in enumerate(seq):
            before = seq[:i]
            failed = (
                (t == "t::victim" and "t::polluter" in before)
                or (t == "t::needs_setter" and "t::setter" not in before)
                or (t == "t::zone" and tz != "UTC")
            )
            out[t] = Outcome("failed" if failed else "passed", "boom" if failed else "")
        return out


def hunt(factors):
    probes = [p for p in default_probes({}) if p.factor in factors]
    return Hunt(FakeRunner(), probes, confirm=6, workers=2).run()


def test_polluter_and_dependency_found():
    r = hunt(["order"])
    found = {(d.test, d.trigger, d.culprit) for d in r.diagnoses}
    assert found == {
        ("t::victim", "run after t::polluter", "t::polluter"),
        ("t::needs_setter", "run on its own", "t::setter"),
    }
    victim = next(d for d in r.diagnoses if d.test == "t::victim")
    assert victim.command == "pytest t::polluter t::victim"
    assert (victim.failing.fails, victim.passing.fails) == (6, 0)


def test_zone_blamed_on_timezone_only():
    r = hunt(["timezone", "random", "timing"])
    assert [(d.test, d.factor) for d in r.diagnoses] == [("t::zone", "timezone")]
    assert r.unexplained == {} and r.always_fail == []


def test_needs_setter_fails_alone_but_is_not_called_always_failing():
    r = hunt(["order", "network"])
    assert "t::needs_setter" not in r.always_fail
    assert set(r.flaky()) == {"t::needs_setter", "t::victim"}
