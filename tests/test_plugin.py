"""Each plugin option, checked in a real pytest run in a subprocess."""

import json
import socket
import threading

import pytest


@pytest.fixture
def run(pytester):
    def go(src: str, *args: str):
        pytester.makepyfile(test_x=src)
        report = pytester.path / "report.json"
        result = pytester.runpytest_subprocess(
            "-p", "no:cacheprovider", f"--fh-report={report}", *args
        )
        data = json.loads(report.read_text()) if report.exists() else {}
        return result, {k.split("::")[-1]: v["outcome"] for k, v in data.items()}

    return go


def test_inert_without_options(run):
    result, out = run("def test_a(): pass\ndef test_b(): assert False")
    assert out == {"test_a": "passed", "test_b": "failed"}


def test_report_records_setup_errors_and_skips(run):
    src = """
import pytest

@pytest.fixture
def broken():
    raise RuntimeError("no")

def test_err(broken): pass

def test_skip(): pytest.skip("later")
"""
    _, out = run(src)
    assert out == {"test_err": "failed", "test_skip": "skipped"}


def test_order_file_runs_exactly_those_in_that_order(run, pytester):
    order = pytester.path / "order.txt"
    order.write_text("test_x.py::test_c\ntest_x.py::test_a\n")
    src = """
seen = []
def test_a(): seen.append("a"); assert seen == ["c", "a"]
def test_b(): seen.append("b")
def test_c(): seen.append("c")
"""
    _, out = run(src, f"--fh-order={order}")
    assert out == {"test_c": "passed", "test_a": "passed"}


def test_seed_makes_random_repeatable(run):
    src = "import random\ndef test_r(): print('value', random.random())"
    a, _ = run(src, "--fh-seed=7", "-s")
    b, _ = run(src, "--fh-seed=7", "-s")
    c, _ = run(src, "--fh-seed=8", "-s")

    def value(r):
        return [line for line in r.outlines if "value" in line]

    assert value(a) == value(b) != value(c)


def test_seed_is_reset_before_each_test(run):
    src = """
import random
first = []
def test_one(): first.append(random.random())
def test_two(): assert random.random() == first[0]
"""
    _, out = run(src, "--fh-seed=3")
    assert out == {"test_one": "passed", "test_two": "passed"}


def test_time_starts_at_given_local_time_and_ticks(run):
    src = """
import time
from datetime import datetime
def test_t():
    a = datetime.now()
    assert (a.year, a.month, a.day, a.hour, a.minute) == (2024, 6, 12, 23, 58)
    time.sleep(0.05)
    assert datetime.now() > a
"""
    _, out = run(src, "--fh-time=2024-06-12T23:58:30")
    assert out == {"test_t": "passed"}


def test_time_does_not_change_the_time_zone(run, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    src = """
import time
def test_tz(): assert time.localtime().tm_gmtoff == 5 * 3600 + 1800
"""
    _, out = run(src, "--fh-time=2038-01-19T03:13:00+00:00")
    assert out == {"test_tz": "passed"}


def test_clock_speed(run):
    src = """
import time
def test_c():
    a = time.perf_counter(); time.sleep(0.1); d = time.perf_counter() - a
    assert 0.25 < d < 0.6
"""
    _, out = run(src, "--fh-clock-speed=3")
    assert out == {"test_c": "passed"}


def test_switch_interval(run):
    src = "import sys\ndef test_s(): assert sys.getswitchinterval() < 1e-5"
    _, out = run(src, "--fh-switch-interval=1e-6")
    assert out == {"test_s": "passed"}


def test_sleep_jitter_only_lengthens(run):
    src = """
import time, asyncio
def test_j():
    for _ in range(5):
        a = time.monotonic(); time.sleep(0.01); assert time.monotonic() - a >= 0.01
async def body():
    a = time.monotonic(); await asyncio.sleep(0.01); return time.monotonic() - a
def test_async(): assert asyncio.run(body()) >= 0.01
"""
    _, out = run(src, "--fh-sleep-jitter=30")
    assert out == {"test_j": "passed", "test_async": "passed"}


def test_gil_hog_runs_a_thread(run):
    src = """
import threading
def test_h(): assert any(t.name == "flaky-hunt-gil-hog" for t in threading.enumerate())
"""
    _, out = run(src, "--fh-gil-hog")
    assert out == {"test_h": "passed"}


@pytest.fixture
def local_server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    port = srv.getsockname()[1]

    def serve():
        try:
            conn, _ = srv.accept()
            conn.close()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    yield port
    srv.close()


def test_no_network_blocks_remote_but_not_loopback(run, local_server):
    src = f"""
import socket, pytest
def test_dns():
    with pytest.raises(OSError, match="flaky-hunt: network blocked"):
        socket.getaddrinfo("example.com", 80)
def test_ip():
    with pytest.raises(OSError, match="flaky-hunt: network blocked"):
        socket.create_connection(("93.184.215.14", 80), timeout=1)
def test_loopback():
    socket.create_connection(("localhost", {local_server}), timeout=2).close()
"""
    _, out = run(src, "--fh-no-network")
    assert out == {"test_dns": "passed", "test_ip": "passed", "test_loopback": "passed"}


def test_collect_writes_ids(pytester):
    pytester.makepyfile(test_x="def test_a(): pass\ndef test_b(): pass")
    out = pytester.path / "ids.json"
    pytester.runpytest_subprocess("--collect-only", f"--fh-collect={out}")
    assert json.loads(out.read_text()) == ["test_x.py::test_a", "test_x.py::test_b"]
