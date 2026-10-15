# flaky-hunt

[![CI](https://github.com/ahmed-hashim-pro/flaky-hunt/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmed-hashim-pro/flaky-hunt/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Finds flaky pytest tests and tells you **why** each one flakes. It re-runs
the suite while changing one thing at a time: test order, the clock, the
time zone, random seeds, thread timing, the environment, network access.
It names the factor that makes each test fail, measures how often, and
gives a command that reproduces the failure.

A flaky test is usually reported as "fails sometimes". That is the least
useful thing to know about it. Rerunning until green, or marking it
`@flaky`, hides it, and the bug it covers ships. What a developer needs is
the cause: *it fails when `test_enable_debug_mode` runs first*, *it fails in
the last ten minutes of the day*, *it fails when the hash seed is 0*. Each
of those is a one-line fix once it's known. Finding it by hand takes an
afternoon of rerunning and guessing.

```
$ flaky-hunt run
flaky-hunt: 16 tests, 9 flaky (9 with a cause found)
39 runs of the suite and 314 of single tests in 1m 34s

tests/test_cart.py::test_checkout_hides_debug_details
  order        after tests/test_settings.py::test_enable_debug_mode  fails 8/8  (68%–100%)
               on its own                                            fails 0/8  (0%–32%)
               assert "Total: 5.50 ...'cake': 2.0}]" == 'Total: 5.50 EUR'
  reproduce    pytest tests/test_settings.py::test_enable_debug_mode tests/test_cart.py::test_checkout_hides_debug_details

tests/test_tags.py::test_render_tags
  random       PYTHONHASHSEED=0  fails 8/8  (68%–100%)
               PYTHONHASHSEED=1  fails 0/8  (0%–32%)
               as-is             fails 4/8  (22%–78%)
               AssertionError: assert 'new, sale' == 'sale, new'
  reproduce    PYTHONHASHSEED=0 pytest tests/test_tags.py::test_render_tags
...
```

![Terminal recording: plain pytest on the planted suite fails one test this time; flaky-hunt run over the order, random, timing and network factors reports six flaky tests, each with the setting that breaks it, failure rates with 95% intervals and a reproducing command; the race in test_inventory, which passed under plain pytest, then fails with the switch-interval option it suggested](docs/demo.gif)

## What it found in real projects

Five releases of four well-known projects, each hunted with every factor in
a clean `python:3.12-slim` container (`make real`; the full reports are in
[`docs/real/`](docs/real)):

| Project | Tests | Flaky | Cause found | Hunt took |
| --- | ---: | ---: | --- | ---: |
| click 8.1.7 | 555 | 0 | | 25 s |
| python-dateutil 2.9.0.post0 | 1,527 | 0 | | 39 s |
| humanize 4.10.0 | 572 | 25 | order: tests delete `humanize.i18n.__file__` and never put it back; 24 translation tests fail after one of them, and the second deleting test fails after the first | 3m 55s |
| humanize 4.11.0 | 621 | 0 | upstream had since rewritten those two tests with `monkeypatch` | 1m 34s |
| arrow 1.4.0 | 1,865 | 2 | order: `test_custom_locale_subclass` defines two `Locale` subclasses, which register themselves in arrow's global locale table for good; the two tests that validate every registered locale then fail | 15m 04s |

Plain `pytest` passes all five, because in file order each polluter runs
after the tests it breaks. They show up as soon as the order changes
(`pytest-randomly`, `pytest-xdist`, a new test file). The arrow pair
is [arrow-py/arrow#1038](https://github.com/arrow-py/arrow/issues/1038),
reported in 2021 from a `pytest-randomly` failure and still open; a
commenter there found the same pair with `pytest --find-dependencies`.
The humanize one was fixed upstream in 4.11.0, and its hunt comes back
clean. So nothing here is a new bug report: one is known and open, the
other fixed. They show the hunt finds real ones, unprompted.

No time, time-zone, seed, timing, environment or network dependence turned
up in any of them. These are mature suites that pin their own clocks and
zones; a clean result is what that looks like, and it is not a proof that
none exists.

## Quickstart

Python 3.10 or newer.

```bash
git clone https://github.com/ahmed-hashim-pro/flaky-hunt && cd flaky-hunt
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'

cd examples/planted
pytest -q                         # usually passes, or fails one or two tests
flaky-hunt run                    # about 1.5 minutes; exits 1 because it finds 9
flaky-hunt run --factors order    # only one factor
flaky-hunt factors                # every setting it tries
```

On your own project, install flaky-hunt into the environment its tests run
in, and run it where you would run `pytest`:

```bash
flaky-hunt run tests/ --json flaky.json
flaky-hunt run --pytest-args "-m 'not integration'" --workers 8
```

`make test` runs the fast self-tests (seconds), `make check` adds whole
hunts of the planted suite (about 3 minutes), `make mutants` runs the
self-tests against deliberately broken versions of flaky-hunt, and
`make real` repeats the real-project runs above in Docker.

## How it works

1. **Probe.** Run the whole suite three times as-is, then once under each
   setting below (39 runs). Every run is a fresh pytest process with its
   own empty `TMPDIR`.
2. **Suspect.** A test that failed under one value of a knob and passed
   under another (seed 5 and seed 1, `TZ=Pacific/Kiritimati` and
   `TZ=UTC`), or under a setting and as-is, is a suspect for that knob.
3. **Confirm.** Run the test on its own, in 8 fresh processes under the
   failing setting and 8 under the passing one. The knob is reported only
   if the failing side fails significantly more often (one-sided Fisher
   exact test). This is what stops a test that fails at random from being
   blamed on whichever setting it happened to fail under: the hash-order
   test above fails under half of all settings, but only `PYTHONHASHSEED`
   survives.
   - If 8 a side is inconclusive but leaning that way (p < 0.25), both
     sides go to 32 runs. That is for tests that also fail now and then
     as-is: on a busy machine the planted race fails as-is in up to a fifth
     of runs, and 8 of 8 against 3 of 8 proves nothing, while 32 of 32
     against 10 of 32 does.
   - The 1% significance level is split over the two stages and over every
     cause tried for that test (Bonferroni), so for each test the chance of
     blaming any cause that isn't there stays under 1%. A test that fails at
     random is a suspect under nearly every knob; without the split, one of
     a dozen comparisons would now and then come out "significant" by
     chance.
4. **Order.** A test that fails in some order but passes on its own is
   bisected over the tests that ran before it, down to the one that breaks
   it, and the pair is confirmed the same way. A test that fails on its own
   but passes in the suite is bisected to the test it silently depends on.

Rates are failures out of runs, with Wilson 95% intervals. 8 of 8 means
"at least 68%", not "always", and 0 of 8 means "at most 32%", not "never".
Raise `--confirm` (first stage) or `--confirm-max` (second) for tighter
intervals.

## The factors

| Factor | Settings tried | How |
| --- | --- | --- |
| order | reverse; three seeded shuffles; each test on its own (suites up to 200 tests) | `--fh-order` file, or the tests as arguments |
| time | clock at 23:58:30 local, noon on 29 February 2024, 23:59:30 on new year's eve, a minute before the 32-bit `time_t` limit | [time-machine](https://github.com/adamchainz/time-machine), clock keeps ticking |
| timezone | `TZ=` UTC, Pacific/Kiritimati (+14), Pacific/Pago_Pago (−11), Asia/Kolkata (+5:30), America/St_Johns (−3:30) | environment; zones without a zone file are skipped with a warning |
| random | `random` (and numpy, hypothesis) seeded with 1–6 before every test; `PYTHONHASHSEED` 0–3 | plugin; environment |
| timing | threads switch every microsecond; every sleep up to 20 ms longer; a busy thread competing for the GIL; monotonic clock running 3x fast (a slow machine) | plugin, each tried twice |
| environment | a second run in the same `TMPDIR`; run from another directory; ASCII locale; `CI` set or unset | environment, working directory |
| network | connections and DNS refused except to loopback | plugin |

Every plugin option is also an ordinary pytest option (`pytest --help`
lists them under *flaky-hunt*), which is why each reproducing command is
plain `pytest`.

## Checking the checker

`examples/planted` is a small shop with nine tests that are flaky in nine
known ways, and seven that aren't. `expected.json` says which factor each
flaky one must be blamed on (and for the order test, which test pollutes
it). The self-tests run whole hunts and require exactly that: every planted
cause found, nothing blamed on anything else, no stable test reported.

| Planted test | Bug | Found as |
| --- | --- | --- |
| `test_checkout_hides_debug_details` | another test sets `settings.DEBUG` and never resets it | order: after `test_enable_debug_mode` |
| `test_short_coupon_expires_today` | "expires today" breaks in the last ten minutes of the day | time: 23:58:30 |
| `test_bulk_discount` | unseeded `random.randint`; the code is wrong for 10 | random: seed 5 |
| `test_render_tags` | expects one iteration order of a set | random: `PYTHONHASHSEED=0` |
| `test_parallel_reservations_use_all_stock` | read-modify-write without a lock | timing: frequent thread switches |
| `test_nightly_report_is_fast` | a 0.2 s wall-clock budget | timing: slow machine |
| `test_receipt_epoch` | `naive_datetime.timestamp()` reads local time | timezone |
| `test_init_cache_creates_price_file` | `mkdir()` in `TMPDIR`, never removed | environment: second run, same `TMPDIR` |
| `test_price_index_reachable` | calls pypi.org | network |

Three of these (the race, the timing budget and the receipt) pass every
time as-is on a typical machine in UTC; they are flaky across machines,
not across runs, which is exactly how they reach CI unnoticed.

To show those tests can fail, `scripts/mutants.py` runs them against five
deliberately broken versions of flaky-hunt. Every one is caught:

```
mutant          result     time  what it breaks
blame-last      caught      16s  the polluter search names the test that ran just before the victim
shared-tmpdir   caught      19s  every run shares one TMPDIR, so files leak between runs
tz-dropped      caught       5s  the TZ setting never reaches the test process
no-confirm      caught      14s  a single failure under a setting is taken as the cause, without re-running
wald-interval   caught       0s  failure-rate intervals use the textbook formula
```

`no-confirm` is the interesting one: without the confirmation step, the
hash-order test is also blamed on the time zone and on thread timing.

The bisection is tested separately against an oracle with the culprit at
every position in lists of 1 to 333 tests, and each plugin option has a
test that runs it in a real pytest process.

## In CI

flaky-hunt exits 1 when it finds a flaky test, 0 when it finds none and 2
when pytest itself can't run. It takes dozens of suite runs, so it belongs
in a nightly or weekly job rather than on every pull request:

```yaml
- run: pip install git+https://github.com/ahmed-hashim-pro/flaky-hunt   # not on PyPI
- run: flaky-hunt run --json flaky.json
- uses: actions/upload-artifact@v4
  if: always()
  with: { name: flaky, path: flaky.json }
```

## What this does not do

- **It finds causes that one factor triggers.** A test that only fails
  when two things coincide (a shuffled order *and* a slow machine) is
  reported as flaky with "no single factor reproduced it", not diagnosed.
- **Timing is simulated in-process.** Frequent thread switches, longer
  sleeps, a competing busy thread and a fast monotonic clock. It does not
  throttle the CPU with cgroups or `taskset`, slow the disk, or reorder
  events inside C extensions. A race that needs real parallelism outside
  the GIL may not show.
- **Time travel covers Python's clocks.** time-machine moves `time.time`,
  `datetime.now` and friends; code that reads the clock in C (or in a
  subprocess the test starts) still sees the real time.
- **Order checks are bounded.** Three shuffles and a reversal won't find
  every order dependency in a large suite, and running every test on its
  own (to find tests that depend on an earlier one) is skipped for suites
  over 200 tests unless `--isolated-max` is raised.
- **No xdist.** Runs are serial inside each pytest process; drop `-n` from
  your `addopts` for the hunt. flaky-hunt runs several processes at once
  (`--workers`) instead.
- **Plain pytest only.** unittest suites work when run through pytest;
  nose, tox matrices and non-Python tests don't.
- **Not every hidden dependency is a bug.** A test that needs the network,
  a UTF-8 locale or a particular working directory is reported, because
  it will fail somewhere; whether that's acceptable is your call.
- **The numbers are from one machine.** The planted results come from a
  12-core Linux box and GitHub's runners; rates depend on load.

## Layout

```
src/flaky_hunt/
  plugin.py     the pytest plugin: every perturbation, and the JSON outcome report
  probes.py     the settings for each factor, and their reproducing commands
  runner.py     runs pytest in a fresh process under a setting
  hunt.py       probe, suspect, confirm, bisect
  stats.py      Wilson intervals, one-sided Fisher exact test
  report.py     text and JSON output
  mutants.py    the deliberately broken variants
examples/planted/   the shop with nine planted flaky tests, and expected.json
tests/              self-tests (test_planted.py runs whole hunts)
scripts/            mutants.py, real.sh
docs/               demo.gif and its tape, real/ (the real-project reports)
```

## License

MIT
