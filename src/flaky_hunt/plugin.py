"""The pytest side of flaky-hunt.

Every option here is inert unless given, so having the plugin installed
changes nothing about an ordinary pytest run. The `flaky-hunt` command turns
these options on one at a time; each is also usable by hand, which is what
the reproducing commands in a report rely on.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import random
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

_state: dict = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("flaky-hunt", "perturbations used by flaky-hunt")
    g.addoption(
        "--fh-report",
        default=None,
        metavar="PATH",
        help="write each test's outcome to PATH as JSON",
    )
    g.addoption(
        "--fh-collect",
        default=None,
        metavar="PATH",
        help="write the collected node ids to PATH as JSON",
    )
    g.addoption(
        "--fh-order",
        default=None,
        metavar="PATH",
        help="run exactly the node ids listed in PATH, in that order",
    )
    g.addoption(
        "--fh-seed",
        type=int,
        default=None,
        metavar="N",
        help="seed random (and numpy, hypothesis) with N before every test",
    )
    g.addoption(
        "--fh-time",
        default=None,
        metavar="ISO",
        help="start the wall clock at ISO (local time if no offset); it keeps ticking",
    )
    g.addoption(
        "--fh-switch-interval",
        type=float,
        default=None,
        metavar="S",
        help="sys.setswitchinterval(S): threads switch far more often",
    )
    g.addoption(
        "--fh-sleep-jitter",
        type=float,
        default=None,
        metavar="MS",
        help="every time.sleep / asyncio.sleep takes up to MS ms longer",
    )
    g.addoption(
        "--fh-gil-hog",
        action="store_true",
        help="a background thread spins, competing for the GIL like a busy machine",
    )
    g.addoption(
        "--fh-clock-speed",
        type=float,
        default=None,
        metavar="X",
        help="time.monotonic and time.perf_counter run X times faster: a slow machine",
    )
    g.addoption(
        "--fh-no-network",
        action="store_true",
        help="refuse connections and DNS lookups, except to loopback",
    )


# ---------------------------------------------------------------- set-up


def pytest_configure(config: pytest.Config) -> None:
    opt = config.option
    if getattr(opt, "fh_seed", None) is not None and hasattr(opt, "hypothesis_seed"):
        if opt.hypothesis_seed is None:
            opt.hypothesis_seed = opt.fh_seed
    if getattr(opt, "fh_time", None):
        _start_time(opt.fh_time)
    if getattr(opt, "fh_switch_interval", None) is not None:
        _state["switch"] = sys.getswitchinterval()
        sys.setswitchinterval(opt.fh_switch_interval)
    if getattr(opt, "fh_sleep_jitter", None):
        _patch_sleep(opt.fh_sleep_jitter / 1000.0)
    if getattr(opt, "fh_gil_hog", False):
        _start_hog()
    if getattr(opt, "fh_clock_speed", None):
        _patch_clock(opt.fh_clock_speed)
    if getattr(opt, "fh_no_network", False):
        _block_network()
    if getattr(opt, "fh_report", None):
        _state["report"] = {}


def pytest_unconfigure(config: pytest.Config) -> None:
    path = getattr(config.option, "fh_report", None)
    if path and "report" in _state:
        Path(path).write_text(json.dumps(_state["report"]))
    for undo in reversed(_state.pop("undo", [])):
        undo()
    if "switch" in _state:
        sys.setswitchinterval(_state.pop("switch"))


def _undo(fn) -> None:
    _state.setdefault("undo", []).append(fn)


def _start_time(iso: str) -> None:
    import time_machine

    when = datetime.fromisoformat(iso)
    if when.tzinfo is None:
        when = when.astimezone()  # a naive time means local wall-clock time
    # A timestamp, not the datetime: given a datetime with a zone, time-machine
    # also changes the process's time zone, which would mix two factors.
    traveller = time_machine.travel(when.timestamp(), tick=True)
    traveller.start()
    _undo(traveller.stop)


def _patch_sleep(max_extra: float) -> None:
    rng = random.Random()  # private: must not disturb the test's own random state
    real_sleep, real_async_sleep = time.sleep, asyncio.sleep

    def sleep(seconds: float) -> None:
        real_sleep(seconds + rng.uniform(0, max_extra))

    async def async_sleep(delay: float, result=None):
        return await real_async_sleep(delay + rng.uniform(0, max_extra), result)

    time.sleep, asyncio.sleep = sleep, async_sleep

    def undo() -> None:
        time.sleep, asyncio.sleep = real_sleep, real_async_sleep

    _undo(undo)


def _start_hog() -> None:
    stop = threading.Event()

    def spin() -> None:
        while not stop.is_set():
            for _ in range(10_000):
                pass

    threading.Thread(target=spin, name="flaky-hunt-gil-hog", daemon=True).start()
    _undo(stop.set)


def _patch_clock(speed: float) -> None:
    names = ("monotonic", "perf_counter", "monotonic_ns", "perf_counter_ns")
    real = {n: getattr(time, n) for n in names}

    def fast(name: str):
        f = real[name]
        start = f()
        if name.endswith("_ns"):
            return lambda: start + int((f() - start) * speed)
        return lambda: start + (f() - start) * speed

    for n in names:
        setattr(time, n, fast(n))

    def undo() -> None:
        for n in names:
            setattr(time, n, real[n])

    _undo(undo)


def _loopback(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode()
    if host in ("localhost", "localhost.localdomain", ""):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _block_network() -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def check(sock: socket.socket, address) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(address[0]):
            raise ConnectionRefusedError(f"flaky-hunt: network blocked ({address[0]})")

    def connect(self, address):
        check(self, address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check(self, address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _loopback(host):
            raise socket.gaierror(socket.EAI_NONAME, f"flaky-hunt: network blocked ({host})")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo

    def undo() -> None:
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex
        socket.getaddrinfo = real_getaddrinfo

    _undo(undo)


# ---------------------------------------------------------------- collection


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    path = getattr(config.option, "fh_order", None)
    if not path:
        return
    wanted = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    by_id = {item.nodeid: item for item in items}
    chosen = [by_id[n] for n in wanted if n in by_id]
    keep = {id(i) for i in chosen}
    config.hook.pytest_deselected(items=[i for i in items if id(i) not in keep])
    items[:] = chosen


def pytest_collection_finish(session: pytest.Session) -> None:
    path = getattr(session.config.option, "fh_collect", None)
    if path:
        Path(path).write_text(json.dumps([item.nodeid for item in session.items]))


# ---------------------------------------------------------------- running


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    seed = item.config.option.fh_seed
    if seed is None:
        return
    random.seed(seed)
    numpy = sys.modules.get("numpy")
    if numpy is not None:
        numpy.random.seed(seed)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    results = _state.get("report")
    if results is None:
        return
    entry = results.setdefault(report.nodeid, {"outcome": "passed", "message": ""})
    if report.failed:
        if entry["outcome"] != "failed":
            entry["outcome"] = "failed"
            entry["message"] = _message(report)
    elif report.skipped and report.when in ("setup", "call") and entry["outcome"] == "passed":
        entry["outcome"] = "skipped"


def _message(report: pytest.TestReport) -> str:
    crash = getattr(report.longrepr, "reprcrash", None)
    text = crash.message if crash is not None else str(report.longrepr)
    line = text.strip().splitlines()[0] if text.strip() else ""
    prefix = "" if report.when == "call" else f"[{report.when}] "
    return (prefix + line)[:200]
