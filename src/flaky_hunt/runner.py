"""Runs pytest in a fresh process under one setting and reads back each test's outcome."""

from __future__ import annotations

import json
import os
import random
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import mutants
from .probes import Setting


class RunError(RuntimeError):
    pass


@dataclass
class Outcome:
    outcome: str  # "passed", "failed", "skipped"
    message: str = ""

    @property
    def failed(self) -> bool:
        return self.outcome == "failed"


class Runner:
    def __init__(
        self,
        project: Path,
        paths: list[str],
        pytest_opts: list[str],
        workdir: Path,
        timeout: float = 600.0,
    ):
        self.project = project.resolve()
        self.paths = paths
        self.opts = pytest_opts
        self.workdir = workdir
        self.timeout = timeout
        self.runs = 0
        self.seconds = 0.0
        self._lock = threading.Lock()
        self._n = 0
        self._shared_tmp = workdir / "shared-tmp"

    def _scratch(self, kind: str) -> Path:
        with self._lock:
            self._n += 1
            n = self._n
        d = self.workdir / f"{kind}-{n}"
        d.mkdir(parents=True)
        return d

    def collect(self) -> list[str]:
        scratch = self._scratch("collect")
        out = scratch / "collected.json"
        self._pytest(
            ["--collect-only", f"--fh-collect={out}", *self.opts, *self.paths],
            self._env(scratch),
            self.project,
            scratch,
        )
        if not out.exists():
            raise RunError("pytest did not collect any tests (see the output above)")
        return json.loads(out.read_text())

    def run(
        self, setting: Setting, nodeids: list[str] | None = None, order: list[str] | None = None
    ) -> dict[str, Outcome]:
        """Run the suite (or `nodeids`, in that order) under `setting`."""
        scratch = self._scratch("run")
        env = self._env(scratch)
        for key, value in setting.env:
            if key == "TZ" and mutants.active("tz-dropped"):
                continue
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        args = list(setting.args) + list(self.opts)
        cwd = self.project
        if setting.elsewhere:
            cwd = scratch / "elsewhere"
            cwd.mkdir()
            args.append(f"--rootdir={self.project}")
        if nodeids is not None:
            targets = [self._target(n, setting.elsewhere) for n in nodeids]
        else:
            targets = [self._target(p, setting.elsewhere) for p in self.paths]
            if order is not None:
                listing = scratch / "order.txt"
                listing.write_text("\n".join(order) + "\n")
                args.append(f"--fh-order={listing}")
        report = scratch / "report.json"
        args += [f"--fh-report={report}", *targets]
        if setting.tmp_reuse:
            self._pytest(args, env, cwd, scratch)
            report.unlink(missing_ok=True)
        self._pytest(args, env, cwd, scratch)
        if not report.exists():
            raise RunError(
                f"pytest wrote no results under {setting.label!r}; "
                f"its output is in {scratch / 'output.txt'}"
            )
        data = json.loads(report.read_text())
        return {k: Outcome(v["outcome"], v["message"]) for k, v in data.items()}

    def _target(self, t: str, absolute: bool) -> str:
        return str(self.project / t) if absolute else t

    def _env(self, scratch: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("PYTEST_ADDOPTS", None)
        tmp = scratch / "tmp"
        if mutants.active("shared-tmpdir"):
            tmp = self._shared_tmp
        tmp.mkdir(exist_ok=True)
        env["TMPDIR"] = str(tmp)
        return env

    def _pytest(self, args: list[str], env: dict, cwd: Path, scratch: Path) -> None:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:randomly",
            "-p",
            "no:cacheprovider",
            *args,
        ]
        start = time.monotonic()
        with open(scratch / "output.txt", "ab") as out:
            out.write(("$ " + shlex.join(cmd) + "\n").encode())
            out.flush()
            try:
                subprocess.run(
                    cmd,
                    cwd=cwd,
                    env=env,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                out.write(f"\nflaky-hunt: timed out after {self.timeout:.0f} s\n".encode())
        with self._lock:
            self.runs += 1
            self.seconds += time.monotonic() - start


def shuffled(ids: list[str], spec: str) -> list[str]:
    if spec == "reverse":
        return list(reversed(ids))
    seed = int(spec.split(":")[1])
    out = list(ids)
    random.Random(seed).shuffle(out)
    return out


def make_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="flaky-hunt-"))
