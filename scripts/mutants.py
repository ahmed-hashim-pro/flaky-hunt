"""Run the self-tests against each deliberately broken flaky-hunt.

Each mutant runs only the tests aimed at what it breaks. A mutant is caught
when those tests fail; the script exits 1 if any mutant survives.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from flaky_hunt.mutants import MUTANTS  # noqa: E402

AIMED = {
    "blame-last": ["tests/test_planted.py::test_order"],
    "shared-tmpdir": ["tests/test_planted.py::test_environment"],
    "tz-dropped": ["tests/test_planted.py::test_timezone"],
    "no-confirm": ["tests/test_planted.py::test_noise_not_blamed"],
    "wald-interval": ["tests/test_stats.py"],
    "sequential-sides": ["tests/test_hunt_logic.py"],
}

survived = 0
print(f"{'mutant':<15} {'result':<8} {'time':>6}  what it breaks")
for name, what in MUTANTS.items():
    start = time.monotonic()
    env = {**os.environ, "FLAKY_HUNT_MUTANT": name}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *AIMED[name]],
        env=env,
        capture_output=True,
        text=True,
    )
    caught = r.returncode != 0
    survived += not caught
    took = time.monotonic() - start
    print(f"{name:<15} {'caught' if caught else 'MISSED':<8} {took:>5.0f}s  {what}")
sys.exit(1 if survived else 0)
