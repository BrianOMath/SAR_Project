"""Tests for the batch runner's decision logic.

Nothing here downloads, runs gpt, or touches CDSE. Every test exercises a pure
function, which is why the orchestration is kept thin and the choices — what to
run, what to skip, what to exclude, when a token has expired — live in
functions that take plain data.
"""

import csv

import pytest

from pathlib import Path

from shapely.geometry import box

from batch_process import (
    Job,
    Product,
    Result,
    already_done,
    append_manifest,
    build_jobs,
    gpt_error,
    import_problem,
    listed_in_requirements,
    plan,
    preflight,
    read_manifest,
    token_expired,
    total_gb,
)

# The real stderr from the 2026-09-20 cross-calibration run, trimmed.
REAL_GPT_STDERR = '''INFO: org.esa.snap.core.gpf.operators.tooladapter.ToolAdapterIO: Initializing external tool adapters
INFO: org.esa.snap.core.util.EngineVersionCheckActivator: Please check regularly for new updates for the best SNAP experience.

Error: ..\\graphs\\s1_grd_preprocess_v2.xml (The system cannot find the path specified)
java.io.FileNotFoundException: ..\\graphs\\s1_grd_preprocess_v2.xml (The system cannot find the path specified)
\tat java.base/java.io.FileInputStream.open0(Native Method)
\tat org.esa.snap.core.gpf.main.GPT.main(GPT.java:42)
\tat com.exe4j.runtime.WinLauncher.main(WinLauncher.java:94)
\tat com.install4j.runtime.launcher.WinLauncher.main(WinLauncher.java:25)
'''


# Geometry for slice planning. The AOI spans y 0..10 and the slice boundary
# falls at y = 1.768, so UPPER holds 82.32% of the AOI and LOWER 17.68% --
# the real 2016-2020 split on relative orbit 1, where the best single slice
# measures 0.8232 stable to four decimals.
AOI = box(0, 0, 10, 10)
FULL = box(-2, -5, 12, 20)
LOWER = box(-2, -5, 12, 1.768)
UPPER = box(-2, 1.768, 12, 20)


def row(date, platform="S1A", orbit=1, direction="ASCENDING",
        pid=None, size=1_760_000_000, name=None, geom=None,
        start_hms="181402", stop_hms="181427",
        datatake="006A7D", unique="80F9"):
    """One scenes.csv row.

    The name is built to the real GRD pattern rather than a placeholder,
    because slice planning parses it: the datatake and start time identify
    which real slice a product is a publication of, and the trailing unique id
    is what differs between two publications of the same slice.
    """
    stamp = date.replace("-", "")
    return {
        "product_id": pid or f"id-{stamp}-{platform}-{unique}",
        "name": name or (f"{platform}_IW_GRDH_1SDV_{stamp}T{start_hms}_"
                         f"{stamp}T{stop_hms}_003717_{datatake}_{unique}.SAFE"),
        "start": f"{date} 18:14:02+00:00",
        "platform": platform,
        "relative_orbit": str(orbit),
        "orbit_direction": direction,
        "size_bytes": str(size),
        "footprint_wkt": (geom or FULL).wkt,
    }


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

def test_selects_only_the_configured_orbit_and_direction():
    rows = [row("2026-07-17"),
            row("2026-07-18", orbit=103),
            row("2026-07-19", direction="DESCENDING")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI)
    assert [j.date for j in jobs] == ["2026-07-17"]


def test_direction_match_is_case_insensitive():
    jobs, _ = build_jobs([row("2026-07-17", direction="ascending")], 1, "ASCENDING", AOI)
    assert len(jobs) == 1


def test_month_window_is_applied():
    rows = [row("2026-03-15"), row("2026-07-17"), row("2026-12-01")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI, months=(4, 10))
    assert [j.date for j in jobs] == ["2026-07-17"]


def test_all_months_when_window_is_none():
    rows = [row("2026-03-15"), row("2026-12-01")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI, months=None)
    assert len(jobs) == 2


def test_year_filter():
    rows = [row("2024-07-17"), row("2025-07-17"), row("2026-07-17")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI, years=[2025, 2026])
    assert [j.date[:4] for j in jobs] == ["2025", "2026"]


def test_explicit_dates_win_over_everything_but_orbit():
    rows = [row(d) for d in ("2026-04-23", "2026-06-28", "2026-07-17")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI,
                         dates=["2026-04-23", "2026-06-28"])
    assert [j.date for j in jobs] == ["2026-04-23", "2026-06-28"]


def test_jobs_come_back_in_date_order():
    rows = [row("2026-07-17"), row("2026-04-23"), row("2026-06-28")]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI)
    assert [j.date for j in jobs] == sorted(j.date for j in jobs)


# --------------------------------------------------------------------------
# slice assembly, which replaced REQ-17's blanket exclusion
# --------------------------------------------------------------------------
# REQ-17 excluded every multi-slice date, which was right while mosaicking did
# not exist: half-processing an acquisition would have put a partial footprint
# into the series with nothing downstream to catch it. But it removed all 34
# acquisitions in 2018, all 34 in 2019 and all 35 in 2020 -- the entire
# confirmatory test. These tests pin the behaviour that replaced it.

def pair_2018(date="2018-07-04"):
    """The real two-slice geometry: 0.1768 + 0.8232, contiguous, one datatake."""
    return [row(date, start_hms="181416", stop_hms="181441",
                datatake="027435", unique="4422", geom=LOWER),
            row(date, start_hms="181441", stop_hms="181506",
                datatake="027435", unique="479A", geom=UPPER)]


def test_two_partial_slices_are_assembled_not_excluded():
    jobs, excluded = build_jobs(pair_2018(), 1, "ASCENDING", AOI)
    assert excluded == []
    assert len(jobs) == 1
    assert jobs[0].action == "assemble"
    assert len(jobs[0].products) == 2


def test_assembled_products_are_in_acquisition_order():
    """SliceAssembly concatenates along-track; order is not decorative."""
    jobs, _ = build_jobs(list(reversed(pair_2018())), 1, "ASCENDING", AOI)
    assert [p.name for p in jobs[0].products] == [
        n["name"] for n in pair_2018()]


def test_an_assembly_job_sums_the_size_of_every_slice():
    jobs, _ = build_jobs(pair_2018(), 1, "ASCENDING", AOI)
    assert jobs[0].size_bytes == 2 * 1_760_000_000


def test_an_assembly_job_records_every_product_id():
    """The manifest must say what was actually used, not just the first slice."""
    jobs, _ = build_jobs(pair_2018(), 1, "ASCENDING", AOI)
    assert jobs[0].product_id.count(",") == 1
    for p in jobs[0].products:
        assert p.product_id in jobs[0].product_id


def test_a_lone_partial_slice_is_excluded_with_its_coverage_named():
    """Still excluded, but now specifically, and the reason carries the number."""
    jobs, excluded = build_jobs([pair_2018()[1]], 1, "ASCENDING", AOI)
    assert jobs == []
    assert len(excluded) == 1
    assert excluded[0].status == "skipped"
    assert "0.8232" in excluded[0].detail


def test_exclusion_does_not_stop_the_other_dates():
    rows = pair_2018()[1:] + [row("2025-04-10", pid="c")]
    jobs, excluded = build_jobs(rows, 1, "ASCENDING", AOI)
    assert [j.date for j in jobs] == ["2025-04-10"]
    assert len(excluded) == 1


def test_single_full_slice_is_not_excluded():
    jobs, excluded = build_jobs([row("2026-07-17")], 1, "ASCENDING", AOI)
    assert len(jobs) == 1 and excluded == []
    assert jobs[0].action == "single"
    assert len(jobs[0].products) == 1


def test_two_publications_of_one_slice_collapse_to_a_single_product():
    """83 dates in the catalogue carry the same real slice published twice --
    identical datatake and start time, different trailing id. Feeding both to
    SliceAssembly would assemble a strip with itself."""
    rows = [row("2026-07-17", unique="AAAA"), row("2026-07-17", unique="BBBB")]
    jobs, excluded = build_jobs(rows, 1, "ASCENDING", AOI)
    assert excluded == []
    assert len(jobs) == 1
    assert jobs[0].action == "single"
    assert len(jobs[0].products) == 1


def test_a_full_coverage_reslicing_is_taken_singly_not_assembled():
    """2022-10-11: one datatake, re-sliced two seconds apart, each product
    covering the AOI on its own. Neither assembly nor exclusion -- take one."""
    rows = [row("2022-10-11", start_hms="181455", stop_hms="181520",
                datatake="056DAA", unique="F323", geom=FULL),
            row("2022-10-11", start_hms="181457", stop_hms="181522",
                datatake="056DAA", unique="E714", geom=FULL)]
    jobs, excluded = build_jobs(rows, 1, "ASCENDING", AOI)
    assert excluded == []
    assert len(jobs) == 1 and jobs[0].action == "single"
    assert len(jobs[0].products) == 1


def test_a_slice_outside_the_aoi_is_not_downloaded():
    """A pass over Ireland can arrive as four slices with two of them far from
    Carlow. Each is 1.7 GB."""
    rows = pair_2018() + [row("2018-07-04", start_hms="181506",
                              stop_hms="181531", datatake="027435",
                              unique="FFFF", geom=box(100, 100, 110, 110))]
    jobs, _ = build_jobs(rows, 1, "ASCENDING", AOI)
    assert len(jobs[0].products) == 2
    assert all("FFFF" not in p.name for p in jobs[0].products)


# --------------------------------------------------------------------------
# resume
# --------------------------------------------------------------------------

def test_already_done_counts_only_verified():
    rows = [{"stem": "20260717_S1D", "status": "verified"},
            {"stem": "20260711_S1C", "status": "gpt_failed"},
            {"stem": "20260705_S1D", "status": "verify_failed"},
            {"stem": "20250404_S1C", "status": "skipped"}]
    assert already_done(rows) == {"20260717_S1D"}


def test_plan_skips_completed_and_keeps_the_rest():
    jobs, _ = build_jobs([row("2026-07-17", "S1D"), row("2026-07-11", "S1C")],
                         1, "ASCENDING", AOI)
    todo, skip = plan(jobs, {"20260717_S1D"})
    assert [j.stem for j in skip] == ["20260717_S1D"]
    assert [j.stem for j in todo] == ["20260711_S1C"]


def test_a_failed_scene_is_retried_on_the_next_run():
    """The point of resume: failures come back, successes do not."""
    jobs, _ = build_jobs([row("2026-07-17", "S1D")], 1, "ASCENDING", AOI)
    done = already_done([{"stem": "20260717_S1D", "status": "verify_failed"}])
    todo, skip = plan(jobs, done)
    assert len(todo) == 1 and skip == []


def test_plan_is_empty_when_everything_is_done():
    jobs, _ = build_jobs([row("2026-07-17", "S1D")], 1, "ASCENDING", AOI)
    todo, _ = plan(jobs, {"20260717_S1D"})
    assert todo == []


# --------------------------------------------------------------------------
# naming and sizing
# --------------------------------------------------------------------------

@pytest.mark.parametrize("date,platform,expected", [
    ("2026-07-17", "S1D", "20260717_S1D"),
    ("2025-04-04", "S1C", "20250404_S1C"),
    ("2024-06-26", "S1A", "20240626_S1A"),
])
def test_stem_matches_the_existing_naming_convention(date, platform, expected):
    jobs, _ = build_jobs([row(date, platform)], 1, "ASCENDING", AOI)
    assert jobs[0].stem == expected


def test_raw_filename_keeps_the_whole_product_id():
    """Regression: rstrip('.SAFE') strips CHARACTERS, not the suffix, so a
    product ending ..._702F.SAFE lost its final F. That is a real product in
    this batch — the 2026-04-24 S1D cross-calibration scene."""
    name = ("S1D_IW_GRDH_1SDV_20260424T181357_20260424T181422"
            "_002492_0041C9_702F.SAFE")
    assert name.rstrip(".SAFE") != name.removesuffix(".SAFE")   # the trap
    assert name.removesuffix(".SAFE").endswith("_702F")


def test_total_gb():
    jobs, _ = build_jobs([row("2026-07-17", size=2_000_000_000),
                          row("2026-07-11", size=1_000_000_000)], 1, "ASCENDING", AOI)
    assert total_gb(jobs) == pytest.approx(3.0)


def test_total_gb_of_nothing_is_zero():
    assert total_gb([]) == 0


# --------------------------------------------------------------------------
# token lifetime -- a batch runs for hours, a token lasts ten minutes
# --------------------------------------------------------------------------

def test_fresh_token_is_not_expired():
    assert not token_expired(issued_at=1000.0, expires_in=600, now=1100.0)


def test_token_expires_inside_the_safety_margin():
    # 30 s of life left, 60 s margin -> treat as expired
    assert token_expired(issued_at=1000.0, expires_in=600, now=1570.0)


def test_token_past_expiry():
    assert token_expired(issued_at=1000.0, expires_in=600, now=2000.0)


def test_margin_is_configurable():
    assert not token_expired(1000.0, 600, 1570.0, margin_s=10.0)


# --------------------------------------------------------------------------
# manifest round-trip
# --------------------------------------------------------------------------

def test_manifest_appends_and_reads_back(tmp_path):
    m = tmp_path / "manifest.csv"
    append_manifest(m, Result("2026-07-17", "S1D", "20260717_S1D", "verified",
                              "all hard checks passed", 120.0, 48.0, "pid-1"))
    append_manifest(m, Result("2026-07-11", "S1C", "20260711_S1C", "gpt_failed",
                              "gpt exit 1"))
    rows = read_manifest(m)
    assert [r["stem"] for r in rows] == ["20260717_S1D", "20260711_S1C"]
    assert already_done(rows) == {"20260717_S1D"}


def test_manifest_writes_one_header_only(tmp_path):
    m = tmp_path / "manifest.csv"
    for i in range(3):
        append_manifest(m, Result(f"2026-07-0{i+1}", "S1D", f"stem{i}", "verified"))
    text = m.read_text(encoding="utf-8")
    assert text.count("stem,status") == 1


def test_missing_manifest_reads_as_empty(tmp_path):
    assert read_manifest(tmp_path / "nope.csv") == []


def test_manifest_survives_a_crash_midway(tmp_path):
    """Appending per scene is deliberate: a kill -9 keeps what finished."""
    m = tmp_path / "manifest.csv"
    append_manifest(m, Result("2026-07-17", "S1D", "a", "verified"))
    append_manifest(m, Result("2026-07-11", "S1C", "b", "verified"))
    # simulate restart
    assert already_done(read_manifest(m)) == {"a", "b"}


# --------------------------------------------------------------------------
# gpt diagnostics -- Java puts the message first and the stack trace after
# --------------------------------------------------------------------------

def test_gpt_error_reports_the_message_not_the_stack_bottom():
    """Regression: taking the LAST line of stderr gave
    'at com.install4j...WinLauncher.main(WinLauncher.java:25)' for every one
    of four failed scenes, hiding a plain missing-file error."""
    msg = gpt_error("", REAL_GPT_STDERR)
    assert "cannot find the path" in msg
    assert "WinLauncher" not in msg
    assert REAL_GPT_STDERR.strip().splitlines()[-1].strip() != msg


def test_gpt_error_skips_info_lines():
    assert gpt_error("", "INFO: loading\nINFO: more\nError: boom") == "Error: boom"


def test_gpt_error_falls_back_when_nothing_looks_like_an_error():
    assert gpt_error("", "INFO: fine\nsomething odd happened") == "something odd happened"


def test_gpt_error_with_no_output():
    assert gpt_error("", "") == "no diagnostic output"


def test_gpt_error_checks_stdout_too():
    assert "Error: from stdout" in gpt_error("Error: from stdout", "INFO: nothing")


# --------------------------------------------------------------------------
# preflight -- catch a missing graph before downloading 7 GB
# --------------------------------------------------------------------------

def test_preflight_passes_when_everything_exists(tmp_path):
    g = tmp_path / "graph.xml"; g.write_text("<graph/>")
    a = tmp_path / "aoi.geojson"; a.write_text("{}")
    x = tmp_path / "gpt.exe"; x.write_text("")
    assert preflight(x, g, a) == []


def _fake_import(monkeypatch, failing_module):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "verify_scene" and failing_module == "verify_scene":
            raise ImportError("No module named 'verify_scene'",
                              name="verify_scene")
        if name == "verify_scene":
            raise ImportError(f"No module named '{failing_module}'",
                              name=failing_module)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)


def test_missing_verify_scene_points_at_the_folder(monkeypatch):
    _fake_import(monkeypatch, "verify_scene")
    problems = import_problem()
    assert len(problems) == 1
    assert "must sit beside batch_process.py" in problems[0]


def test_missing_dependency_points_at_pip_not_the_folder(monkeypatch):
    """Regression: a missing rasterio was reported as verify_scene being in
    the wrong folder, sending the reader to fix something already correct."""
    _fake_import(monkeypatch, "rasterio")
    problems = import_problem()
    assert len(problems) == 1
    assert "rasterio" in problems[0]
    assert "pip install -r requirements.txt" in problems[0]
    assert "must sit beside" not in problems[0]


@pytest.mark.parametrize("dep", ["rasterio", "pyproj", "shapely", "numpy"])
def test_any_missing_dependency_is_named(monkeypatch, dep):
    _fake_import(monkeypatch, dep)
    assert dep in import_problem()[0]


def test_import_problem_is_empty_when_everything_imports():
    assert import_problem() == []


def test_preflight_catches_an_unimportable_verify_module(tmp_path, monkeypatch):
    """Regression: verify_scene is imported per scene, AFTER download and
    AFTER gpt. Living in the wrong folder killed the whole run at scene 1."""
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "verify_scene":
            raise ImportError("No module named 'verify_scene'",
                              name="verify_scene")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    g = tmp_path / "graph.xml"; g.write_text("<graph/>")
    a = tmp_path / "aoi.geojson"; a.write_text("{}")
    x = tmp_path / "gpt.exe"; x.write_text("")
    problems = preflight(x, g, a)
    assert len(problems) == 1
    assert "verify_scene" in problems[0]
    assert "beside batch_process.py" in problems[0]


def test_preflight_can_skip_the_import_check(tmp_path):
    g = tmp_path / "graph.xml"; g.write_text("<graph/>")
    a = tmp_path / "aoi.geojson"; a.write_text("{}")
    x = tmp_path / "gpt.exe"; x.write_text("")
    assert preflight(x, g, a, check_import=False) == []


def test_preflight_names_the_missing_graph(tmp_path):
    a = tmp_path / "aoi.geojson"; a.write_text("{}")
    x = tmp_path / "gpt.exe"; x.write_text("")
    problems = preflight(x, tmp_path / "graphs" / "missing.xml", a,
                         check_import=False)
    assert len(problems) == 1
    assert "graph not found" in problems[0]


def test_preflight_reports_every_problem_at_once(tmp_path):
    problems = preflight(tmp_path / "gpt.exe", tmp_path / "g.xml",
                         tmp_path / "a.geojson", check_import=False)
    assert len(problems) == 3


def test_preflight_rejects_a_directory_given_as_the_graph(tmp_path):
    d = tmp_path / "graphs"; d.mkdir()
    a = tmp_path / "aoi.geojson"; a.write_text("{}")
    x = tmp_path / "gpt.exe"; x.write_text("")
    assert any("graph not found" in p for p in preflight(x, d, a,
                                                        check_import=False))


# --------------------------------------------------------------------------
# stale requirements.txt -- the loop that cost an evening
# --------------------------------------------------------------------------

STALE_REQ = "requests>=2.31\nshapely>=2.0\npytest>=8.0\n"
CURRENT_REQ = ("requests>=2.31\nshapely>=2.0\nrasterio>=1.3\n"
               "pyproj>=3.6\nnumpy>=1.26\npytest>=8.0\n")


def test_listed_in_requirements_finds_a_pinned_package(tmp_path):
    r = tmp_path / "requirements.txt"; r.write_text(CURRENT_REQ)
    assert listed_in_requirements("rasterio", r) is True
    assert listed_in_requirements("pyproj", r) is True


def test_listed_in_requirements_reports_absence(tmp_path):
    r = tmp_path / "requirements.txt"; r.write_text(STALE_REQ)
    assert listed_in_requirements("rasterio", r) is False


def test_listed_in_requirements_is_none_when_unreadable(tmp_path):
    assert listed_in_requirements("rasterio", tmp_path / "nope.txt") is None


@pytest.mark.parametrize("line", [
    "rasterio", "rasterio==1.4.4", "rasterio>=1.3", "rasterio ~= 1.4",
    "rasterio[s3]>=1.3", "  rasterio>=1.3  # needed by verify_scene",
])
def test_listed_in_requirements_handles_specifier_forms(tmp_path, line):
    r = tmp_path / "requirements.txt"; r.write_text(line + "\n")
    assert listed_in_requirements("rasterio", r) is True


def test_comment_only_line_is_not_a_package(tmp_path):
    r = tmp_path / "requirements.txt"; r.write_text("# rasterio>=1.3\n")
    assert listed_in_requirements("rasterio", r) is False


def test_stale_requirements_changes_the_advice(monkeypatch, tmp_path):
    """Regression: telling someone to run `pip install -r requirements.txt`
    when that file does not mention the package is an infinite loop. It cost
    two successful installs and an evening."""
    _fake_import(monkeypatch, "rasterio")
    r = tmp_path / "requirements.txt"; r.write_text(STALE_REQ)
    msg = import_problem(req=r)[0]
    assert "NOT listed" in msg
    assert "out of date" in msg


def test_current_requirements_gives_the_plain_advice(monkeypatch, tmp_path):
    _fake_import(monkeypatch, "rasterio")
    r = tmp_path / "requirements.txt"; r.write_text(CURRENT_REQ)
    msg = import_problem(req=r)[0]
    assert "NOT listed" not in msg
    assert "pip install -r requirements.txt" in msg
