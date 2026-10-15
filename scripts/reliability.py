"""Run the whole planted hunt N times and count how often it is exactly right.

    python scripts/reliability.py 10 [extra flaky-hunt options]

Each hunt is scored against examples/planted/expected.json the same way the
self-tests score it. Used to measure how reliable the diagnosis is on a busy
or small machine (run it under `docker run --cpus=...` with load).
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.planted import PLANTED, problems  # noqa: E402

FACTORS = ["order", "time", "timezone", "random", "timing", "environment", "network"]

n, extra = int(sys.argv[1]), sys.argv[2:]
right = 0
for i in range(1, n + 1):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "planted"
        shutil.copytree(PLANTED, project)
        out = Path(tmp) / "report.json"
        start = time.monotonic()
        subprocess.run(
            ["flaky-hunt", "run", "-q", "--json", str(out), *extra],
            cwd=project,
            stdout=subprocess.DEVNULL,
        )
        data = json.loads(out.read_text())
    report = SimpleNamespace(
        diagnoses=[SimpleNamespace(**d) for d in data["diagnoses"]],
        unexplained=data["unexplained"],
        always_fail=data["always_fail"],
    )
    wrong = problems(report, FACTORS)
    right += not wrong
    race = next((d for d in data["diagnoses"] if "inventory" in d["test"]), None)
    rates = (
        f"race {race['failing']['fails']}/{race['failing']['runs']} vs "
        f"{race['passing']['fails']}/{race['passing']['runs']} as-is"
        if race
        else "race: no cause"
    )
    print(
        f"hunt {i}: {'right' if not wrong else 'WRONG'} in {time.monotonic() - start:.0f}s; "
        f"{rates}; {'; '.join(wrong)}",
        flush=True,
    )
print(f"{right}/{n} hunts exactly right")
sys.exit(0 if right == n else 1)
