"""flaky-hunt's command line."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
from pathlib import Path

from . import __version__
from .hunt import Hunt
from .probes import FACTORS, default_probes, missing_zones
from .report import render, to_json
from .runner import RunError, Runner, make_workdir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="flaky-hunt",
        description="Find flaky tests and the one factor that makes each of them fail.",
    )
    ap.add_argument("--version", action="version", version=f"flaky-hunt {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="hunt for flaky tests in a pytest suite")
    run.add_argument("paths", nargs="*", help="test paths for pytest (default: pytest's own)")
    run.add_argument("--project", default=".", help="directory to run pytest in (default: .)")
    run.add_argument(
        "--factors",
        default=",".join(FACTORS),
        help=f"comma-separated subset of: {', '.join(FACTORS)}",
    )
    run.add_argument(
        "--confirm",
        type=int,
        default=8,
        metavar="N",
        help="fresh-process runs on each side when confirming a cause (default 8)",
    )
    run.add_argument(
        "--alpha",
        type=float,
        default=0.01,
        help="significance level for confirming a cause (default 0.01)",
    )
    run.add_argument("--workers", type=int, default=4, help="pytest processes at once (default 4)")
    run.add_argument(
        "--isolated-max",
        type=int,
        default=200,
        metavar="N",
        help="run every test on its own only if the suite has at most N (default 200)",
    )
    run.add_argument(
        "--pytest-args",
        default="",
        metavar="ARGS",
        help="extra options for every pytest run, as one string",
    )
    run.add_argument("--timeout", type=float, default=600, help="seconds per pytest run")
    run.add_argument("--json", metavar="PATH", help="also write the report as JSON")
    run.add_argument("--keep", action="store_true", help="keep the scratch directory of runs")
    run.add_argument("-q", "--quiet", action="store_true", help="no progress lines")

    sub.add_parser("factors", help="list the settings each factor tries")

    args = ap.parse_args(argv)
    if args.cmd == "factors":
        for s in default_probes(dict(os.environ)):
            print(f"{s.factor:<12} {s.label}")
        return 0

    factors = [f.strip() for f in args.factors.split(",") if f.strip()]
    unknown = [f for f in factors if f not in FACTORS]
    if unknown:
        ap.error(f"unknown factor(s): {', '.join(unknown)}")
    probes = [p for p in default_probes(dict(os.environ)) if p.factor in factors]

    missing = missing_zones() if "timezone" in factors else []
    if missing:
        print(
            f"flaky-hunt: no zone files for {', '.join(missing)}; skipping those time zones "
            "(install tzdata to test them)",
            file=sys.stderr,
        )

    workdir = make_workdir()
    runner = Runner(
        Path(args.project), args.paths, shlex.split(args.pytest_args), workdir, timeout=args.timeout
    )
    say = (lambda s: None) if args.quiet else (lambda s: print(f"· {s}", file=sys.stderr))
    hunt = Hunt(
        runner,
        probes,
        confirm=args.confirm,
        alpha=args.alpha,
        workers=args.workers,
        isolated_max=args.isolated_max,
        progress=say,
    )
    try:
        report = hunt.run()
    except RunError as e:
        print(f"flaky-hunt: {e}", file=sys.stderr)
        print(f"flaky-hunt: scratch directory kept at {workdir}", file=sys.stderr)
        return 2
    finally:
        if not args.keep and workdir.exists() and sys.exc_info()[0] is None:
            shutil.rmtree(workdir, ignore_errors=True)
    if args.keep:
        say(f"runs kept in {workdir}")

    print(render(report, factors))
    if args.json:
        Path(args.json).write_text(to_json(report))
    return 1 if report.flaky() else 0


if __name__ == "__main__":
    sys.exit(main())
