"""The settings flaky-hunt runs a suite under, one factor at a time."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

FACTORS = ("order", "time", "timezone", "random", "timing", "environment", "network")


@dataclass(frozen=True)
class Setting:
    factor: str  # "control" or one of FACTORS
    knob: str  # settings with the same knob are alternative values of one thing
    label: str  # how a report names it
    env: tuple[tuple[str, str | None], ...] = ()  # None unsets the variable
    args: tuple[str, ...] = ()  # plugin options
    order: str = ""  # "", "reverse" or "shuffle:N"
    tmp_reuse: bool = False  # run twice in one TMPDIR; the second run counts
    elsewhere: bool = False  # run from an empty directory instead of the project
    in_suite_only: bool = field(default=False, compare=False)

    def command(self, targets: list[str]) -> str:
        """The shell command that runs `targets` under this setting."""
        sets = [f"{k}={shlex.quote(v)}" for k, v in self.env if v is not None]
        unsets = [k for k, v in self.env if v is None]
        prefix = ""
        if unsets:
            prefix = "env " + " ".join(f"-u {k}" for k in unsets) + " "
        if sets:
            prefix += " ".join(sets) + " "
        tgt = " ".join(shlex.quote(t) for t in targets)
        if self.elsewhere:
            tgt = " ".join(f'"$OLDPWD"/{shlex.quote(t)}' for t in targets)
        cmd = f"{prefix}pytest {' '.join(self.args) + ' ' if self.args else ''}{tgt}"
        if self.tmp_reuse:
            return f"export TMPDIR=$(mktemp -d); pytest {tgt}; pytest {tgt}"
        if self.elsewhere:
            return f'cd "$(mktemp -d)" && {cmd}'
        return cmd


CONTROL = Setting("control", "control", "as-is")

TIMEZONES = ("UTC", "Pacific/Kiritimati", "Pacific/Pago_Pago", "Asia/Kolkata", "America/St_Johns")


ZONE_DIRS = ("/usr/share/zoneinfo", "/usr/lib/zoneinfo", "/etc/zoneinfo")


def zone_file(tz: str, env: dict[str, str], dirs: tuple[str, ...] = ZONE_DIRS) -> bool:
    """Whether the C library can load `tz`. Without the file, TZ=Pacific/Kiritimati
    silently means UTC, and a hunt would wrongly report nothing zone-dependent."""
    search = [env.get("TZDIR"), *dirs]
    return tz == "UTC" or any(d and (Path(d) / tz).is_file() for d in search)


def missing_zones(env: dict[str, str] | None = None) -> list[str]:
    env = dict(os.environ) if env is None else env
    return [tz for tz in TIMEZONES if not zone_file(tz, env)]


def default_probes(env: dict[str, str], zone_dirs: tuple[str, ...] = ZONE_DIRS) -> list[Setting]:
    p: list[Setting] = []

    p.append(Setting("order", "order", "reverse order", order="reverse", in_suite_only=True))
    for n in (1, 2, 3):
        p.append(
            Setting(
                "order",
                "order",
                f"shuffled order (seed {n})",
                order=f"shuffle:{n}",
                in_suite_only=True,
            )
        )

    for iso, why in (
        ("2024-06-12T23:58:30", "just before midnight"),
        ("2024-02-29T12:00:00", "leap day"),
        ("2024-12-31T23:59:30", "just before new year"),
        ("2038-01-19T03:13:00+00:00", "just before the 32-bit time_t limit"),
    ):
        p.append(Setting("time", "time", f"clock at {iso} ({why})", args=(f"--fh-time={iso}",)))

    for tz in TIMEZONES:
        if env.get("TZ") == tz or not zone_file(tz, env, zone_dirs):
            continue
        p.append(Setting("timezone", "tz", f"TZ={tz}", env=(("TZ", tz),)))

    for n in range(1, 7):
        p.append(Setting("random", "seed", f"random seeded with {n}", args=(f"--fh-seed={n}",)))
    for n in range(4):
        p.append(
            Setting("random", "hashseed", f"PYTHONHASHSEED={n}", env=(("PYTHONHASHSEED", str(n)),))
        )

    timing = [
        Setting(
            "timing",
            "switch",
            "threads switch every microsecond",
            args=("--fh-switch-interval=1e-6",),
        ),
        Setting("timing", "jitter", "sleeps run up to 20 ms long", args=("--fh-sleep-jitter=20",)),
        Setting("timing", "hog", "a busy thread competes for the GIL", args=("--fh-gil-hog",)),
        Setting(
            "timing",
            "clock",
            "a 3x slower machine (monotonic clock runs 3x fast)",
            args=("--fh-clock-speed=3",),
        ),
    ]
    p.extend(timing + timing)  # timing effects are chancy: try each twice

    p.append(Setting("environment", "tmp", "second run in the same TMPDIR", tmp_reuse=True))
    p.append(Setting("environment", "cwd", "run from another directory", elsewhere=True))
    p.append(
        Setting(
            "environment",
            "locale",
            "ASCII locale (LC_ALL=C, no UTF-8 mode)",
            env=(("LC_ALL", "C"), ("LANG", "C"), ("PYTHONCOERCECLOCALE", "0"), ("PYTHONUTF8", "0")),
        )
    )
    if env.get("CI") or env.get("GITHUB_ACTIONS"):
        p.append(
            Setting(
                "environment",
                "ci",
                "CI variables unset",
                env=(("CI", None), ("GITHUB_ACTIONS", None)),
            )
        )
    else:
        p.append(Setting("environment", "ci", "CI=true", env=(("CI", "true"),)))

    p.append(Setting("network", "network", "network blocked", args=("--fh-no-network",)))
    return p
