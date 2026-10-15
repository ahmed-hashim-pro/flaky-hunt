"""Deliberately wrong versions of flaky-hunt, to show the self-tests have teeth.

Set FLAKY_HUNT_MUTANT to one of these names and flaky-hunt misbehaves in
that one way. `make mutants` runs the self-tests against each and expects
every one to be caught.
"""

from __future__ import annotations

import os

MUTANTS = {
    "blame-last": "the polluter search names the test that ran just before the victim",
    "shared-tmpdir": "every run shares one TMPDIR, so files leak between runs",
    "tz-dropped": "the TZ setting never reaches the test process",
    "no-confirm": "a single failure under a setting is taken as the cause, without re-running",
    "wald-interval": "failure-rate intervals use the textbook formula",
    "sequential-sides": "a comparison runs all of one side, then all of the other",
}


def active(name: str) -> bool:
    return os.environ.get("FLAKY_HUNT_MUTANT") == name
