"""Update test_batch_process.py for slice assembly.

Order matters: the REQ-17 section is rewritten BEFORE the global build_jobs
signature substitution, or its anchor no longer matches.

Usage:
    python patch_tests.py <path to test_batch_process.py>
"""

from __future__ import annotations

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# A  imports and the row() fixture
# --------------------------------------------------------------------------

A_OLD = '''import csv

import pytest

from pathlib import Path

from batch_process import (
    Job,
'''

A_NEW = '''import csv

import pytest

from pathlib import Path

from shapely.geometry import box

from batch_process import (
    Job,
    Product,
'''

B_OLD = '''def row(date, platform="S1A", orbit=1, direction="ASCENDING",
        pid=None, size=1_760_000_000, name=None):
    stamp = date.replace("-", "")
    return {
        "product_id": pid or f"id-{stamp}-{platform}",
        "name": name or f"{platform}_IW_GRDH_1SDV_{stamp}T181402_x.SAFE",
        "start": f"{date} 18:14:02+00:00",
        "platform": platform,
        "relative_orbit": str(orbit),
        "orbit_direction": direction,
        "size_bytes": str(size),
    }
'''

B_NEW = '''# Geometry for slice planning. The AOI spans y 0..10 and the slice boundary
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
'''

# --------------------------------------------------------------------------
# C  the REQ-17 section, rewritten for assembly
# --------------------------------------------------------------------------

C_OLD = '''# --------------------------------------------------------------------------
# REQ-17: multi-slice acquisitions are excluded, not silently half-processed
# --------------------------------------------------------------------------

def test_multi_slice_acquisition_is_excluded_with_a_reason():
    rows = [row("2025-04-04", pid="a", name="S1C_..._1.SAFE"),
            row("2025-04-04", pid="b", name="S1C_..._2.SAFE")]
    jobs, excluded = build_jobs(rows, 1, "ASCENDING")
    assert jobs == []
    assert len(excluded) == 1
    assert excluded[0].status == "skipped"
    assert "REQ-17" in excluded[0].detail
    assert "2 GRD slices" in excluded[0].detail


def test_exclusion_does_not_stop_the_other_dates():
    rows = [row("2025-04-04", pid="a"), row("2025-04-04", pid="b"),
            row("2025-04-10", pid="c")]
    jobs, excluded = build_jobs(rows, 1, "ASCENDING")
    assert [j.date for j in jobs] == ["2025-04-10"]
    assert len(excluded) == 1


def test_single_slice_date_is_not_excluded():
    jobs, excluded = build_jobs([row("2026-07-17")], 1, "ASCENDING")
    assert len(jobs) == 1 and excluded == []
'''

C_NEW = '''# --------------------------------------------------------------------------
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
'''

# --------------------------------------------------------------------------
# D  global: build_jobs takes the AOI
# --------------------------------------------------------------------------

# One pass, so a site cannot be rewritten twice. The lookahead accepts both
# call shapes: build_jobs(rows, 1, "ASCENDING") and
# build_jobs(rows, 1, "ASCENDING", months=(4, 10)).
# The negative lookahead skips sites that already carry the AOI -- the tests
# inserted by section C pass it explicitly, and would otherwise be rewritten
# into build_jobs(..., AOI, AOI).
D_PATTERN = r'1, "ASCENDING"(?!\s*,\s*AOI)(?=\s*[,)])'
D_REPL = '1, "ASCENDING", AOI'

ANCHORED = [("A imports", A_OLD, A_NEW),
            ("B row fixture", B_OLD, B_NEW),
            ("C assembly section", C_OLD, C_NEW)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    text = original = path.read_text(encoding="utf-8")

    failures = []
    for label, old, new in ANCHORED:
        n = text.count(old)
        if n != 1:
            failures.append(f"{label}: anchor matched {n} times, expected 1")
            continue
        text = text.replace(old, new, 1)
    if failures:
        print("PATCH NOT APPLIED — file unchanged:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    import re
    text, total = re.subn(D_PATTERN, D_REPL, text)
    print(f"build_jobs call sites updated: {total}")
    if 'AOI, AOI' in text:
        print("PATCH NOT APPLIED — a call site was rewritten twice",
              file=sys.stderr)
        return 1

    import ast
    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"PATCH NOT APPLIED — result would not parse: {exc}", file=sys.stderr)
        return 1

    backup = path.with_suffix(".py.pre-assembly")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"backup: {backup.name}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name}: parses clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
