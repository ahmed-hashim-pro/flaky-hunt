from flaky_hunt.probes import CONTROL, FACTORS, Setting, default_probes


def test_every_factor_has_settings():
    probes = default_probes({})
    assert {p.factor for p in probes} == set(FACTORS)


def test_current_tz_not_repeated():
    labels = [p.label for p in default_probes({"TZ": "UTC"})]
    assert "TZ=UTC" not in labels


def test_ci_setting_flips_what_is_there():
    assert any(p.label == "CI=true" for p in default_probes({}))
    assert any(p.label == "CI variables unset" for p in default_probes({"CI": "1"}))


def test_commands():
    t = "tests/test_a.py::test_x[1-2]"
    assert CONTROL.command(["a::b", t]) == "pytest a::b 'tests/test_a.py::test_x[1-2]'"
    s = Setting("timezone", "tz", "TZ=Asia/Kolkata", env=(("TZ", "Asia/Kolkata"),))
    assert s.command(["a::b"]) == "TZ=Asia/Kolkata pytest a::b"
    s = Setting("environment", "ci", "", env=(("CI", None), ("GITHUB_ACTIONS", None)))
    assert s.command(["a::b"]) == "env -u CI -u GITHUB_ACTIONS pytest a::b"
    s = Setting("random", "seed", "", args=("--fh-seed=3",))
    assert s.command(["a::b"]) == "pytest --fh-seed=3 a::b"
    s = Setting("environment", "tmp", "", tmp_reuse=True)
    assert s.command(["a::b"]) == "export TMPDIR=$(mktemp -d); pytest a::b; pytest a::b"
    s = Setting("environment", "cwd", "", elsewhere=True)
    assert s.command(["a::b"]) == 'cd "$(mktemp -d)" && pytest "$OLDPWD"/a::b'


def test_zones_without_files_are_skipped(tmp_path):
    (tmp_path / "Asia").mkdir()
    (tmp_path / "Asia" / "Kolkata").write_bytes(b"TZif")
    probes = default_probes({"TZDIR": str(tmp_path)}, zone_dirs=())
    assert {p.label for p in probes if p.factor == "timezone"} == {"TZ=UTC", "TZ=Asia/Kolkata"}
