"""Tests for slices.py -- GRD slice selection and assembly validation.

The geometry fixtures are modelled on the real 2018 case: two along-track
slices, the southern one covering 0.1766 of the AOI and the northern 0.8232,
joining on a shared edge.
"""

from __future__ import annotations

import pytest
from shapely.geometry import Polygon, box

import slices as sl

# --------------------------------------------------------------------------
# fixtures shaped like the real data
# --------------------------------------------------------------------------

# AOI spanning y 0..10. The slice boundary falls at y = 1.768, so the later
# (northern) slice holds 82.32% of the AOI and the earlier one 17.68% --
# matching the catalogue, where the 181441-181506 slice reads 0.8232 and the
# 181416-181441 slice reads 0.1766.
AOI = box(0, 0, 10, 10)
SOUTH = box(-2, -5, 12, 1.768)
NORTH = box(-2, 1.768, 12, 20)
FAR = box(100, 100, 110, 110)


def row(name, wkt_geom, **extra):
    r = {"name": name, "footprint_wkt": wkt_geom.wkt,
         "product_id": name[:8], "start": "2018-07-04 18:14:16+00:00",
         "size_bytes": "1710000000", "aoi_coverage": "0.0",
         "relative_orbit": "1", "orbit_direction": "ASCENDING",
         "platform": name[:3]}
    r.update(extra)
    return r


def s1a(start, stop, datatake="027435", unique="4422", geom=NORTH, plat="S1A"):
    name = (f"{plat}_IW_GRDH_1SDV_20180704T{start}_20180704T{stop}"
            f"_022648_{datatake}_{unique}.SAFE")
    return row(name, geom)


# the real pair, times taken from the catalogue
SOUTH_SLICE = s1a("181416", "181441", unique="4422", geom=SOUTH)
NORTH_SLICE = s1a("181441", "181506", unique="479A", geom=NORTH)


# --------------------------------------------------------------------------
# parse_name
# --------------------------------------------------------------------------

def test_parse_name_reads_a_real_product_name():
    p = sl.parse_name(
        "S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_4422.SAFE")
    assert p["platform"] == "S1A"
    assert p["datatake"] == "027435"
    assert p["unique"] == "4422"
    assert p["start_dt"].hour == 18
    assert (p["stop_dt"] - p["start_dt"]).total_seconds() == 25


def test_parse_name_accepts_single_pol_products():
    p = sl.parse_name(
        "S1A_IW_GRDH_1SSV_20150320T114745_20150320T114810_005123_0066F1_AAAA.SAFE")
    assert p is not None and p["pol"] == "SV"


@pytest.mark.parametrize("name", [
    "",
    "not-a-product",
    "S1A_IW_SLC__1SDV_20180704T181416_20180704T181441_022648_027435_4422.SAFE",
    "S1A_IW_GRDH_1SDV_20180704T181416_022648_027435_4422.SAFE",
    "S1Z_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_4422.SAFE",
])
def test_parse_name_returns_none_rather_than_raising(name):
    assert sl.parse_name(name) is None


def test_parse_name_rejects_a_missing_safe_suffix():
    assert sl.parse_name(
        "S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_4422") is None


# --------------------------------------------------------------------------
# slice_key / dedupe
# --------------------------------------------------------------------------

def test_slice_key_ignores_the_product_unique_id():
    """Two publications of one slice differ only in the trailing field."""
    a = sl.slice_key(
        "S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_63D5.SAFE")
    b = sl.slice_key(
        "S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_0169.SAFE")
    assert a == b


def test_slice_key_separates_genuinely_different_slices():
    a = sl.slice_key(NORTH_SLICE["name"])
    b = sl.slice_key(SOUTH_SLICE["name"])
    assert a != b


def test_dedupe_collapses_the_real_2018_08_03_case():
    """Four products, two real slices -- the case that looked like 4 slices."""
    rows = [
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_63D5.SAFE", SOUTH),
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_0169.SAFE", SOUTH),
        row("S1B_IW_GRDH_1SDV_20180803T181401_20180803T181426_012102_016488_A7F5.SAFE", NORTH),
        row("S1B_IW_GRDH_1SDV_20180803T181401_20180803T181426_012102_016488_8B2E.SAFE", NORTH),
    ]
    kept, dropped = sl.dedupe(rows)
    assert len(kept) == 2
    assert len(dropped) == 2
    assert {sl.slice_key(r["name"]) for r in kept} == {
        sl.slice_key(rows[0]["name"]), sl.slice_key(rows[2]["name"])}


def test_dedupe_is_deterministic_regardless_of_input_order():
    rows = [
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_63D5.SAFE", SOUTH),
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_0169.SAFE", SOUTH),
    ]
    a, _ = sl.dedupe(rows)
    b, _ = sl.dedupe(list(reversed(rows)))
    assert [r["name"] for r in a] == [r["name"] for r in b]
    assert a[0]["name"].endswith("63D5.SAFE")   # lexicographically largest


def test_dedupe_leaves_a_clean_single_product_alone():
    kept, dropped = sl.dedupe([NORTH_SLICE])
    assert kept == [NORTH_SLICE] and dropped == []


def test_dedupe_returns_unparsed_products_as_dropped():
    bad = row("mystery.zip", NORTH)
    kept, dropped = sl.dedupe([NORTH_SLICE, bad])
    assert kept == [NORTH_SLICE]
    assert dropped == [bad]


def test_dedupe_drops_nothing_when_all_slices_are_distinct():
    kept, dropped = sl.dedupe([SOUTH_SLICE, NORTH_SLICE])
    assert len(kept) == 2 and dropped == []


# --------------------------------------------------------------------------
# intersecting
# --------------------------------------------------------------------------

def test_intersecting_keeps_both_slices_that_cover_the_aoi():
    got = sl.intersecting([SOUTH_SLICE, NORTH_SLICE], AOI)
    assert len(got) == 2


def test_intersecting_discards_a_slice_hundreds_of_km_away():
    far = s1a("181506", "181531", unique="FFFF", geom=FAR)
    got = sl.intersecting([SOUTH_SLICE, NORTH_SLICE, far], AOI)
    assert [r["name"] for r in got] == [SOUTH_SLICE["name"], NORTH_SLICE["name"]]


def test_intersecting_discards_a_slice_that_only_touches_an_edge():
    """Edge contact contributes no pixels and would widen the assembly."""
    touching = s1a("181506", "181531", unique="EEEE",
                   geom=box(10, 0, 20, 10))
    assert sl.intersecting([touching], AOI) == []


def test_intersecting_skips_a_row_with_no_footprint():
    blank = row("S1A_IW_GRDH_1SDV_20180704T181441_20180704T181506_022648_027435_0001.SAFE",
                NORTH)
    blank["footprint_wkt"] = ""
    assert sl.intersecting([blank], AOI) == []


def test_intersecting_skips_a_row_with_unparseable_wkt():
    broken = dict(NORTH_SLICE)
    broken["footprint_wkt"] = "POLYGON ((bad"
    assert sl.intersecting([broken], AOI) == []


# --------------------------------------------------------------------------
# assembly_order
# --------------------------------------------------------------------------

def test_assembly_order_is_by_acquisition_time():
    got = sl.assembly_order([NORTH_SLICE, SOUTH_SLICE])
    assert [r["name"] for r in got] == [SOUTH_SLICE["name"], NORTH_SLICE["name"]]


def test_assembly_order_puts_an_unparsed_name_last():
    bad = row("mystery.zip", NORTH)
    got = sl.assembly_order([bad, NORTH_SLICE])
    assert got[-1] is bad


# --------------------------------------------------------------------------
# union_coverage
# --------------------------------------------------------------------------

def test_union_of_the_two_real_slices_covers_the_whole_aoi():
    cov, parts = sl.union_coverage([SOUTH_SLICE, NORTH_SLICE], AOI)
    assert cov == pytest.approx(1.0, abs=1e-9)
    assert parts == 1


def test_the_northern_slice_alone_reproduces_the_observed_0_8232():
    cov, parts = sl.union_coverage([NORTH_SLICE], AOI)
    assert cov == pytest.approx(0.8232, abs=5e-4)
    assert parts == 1


def test_union_coverage_counts_disjoint_footprints_as_separate_parts():
    far = s1a("181506", "181531", unique="FFFF", geom=FAR)
    _, parts = sl.union_coverage([NORTH_SLICE, far], AOI)
    assert parts == 2


def test_union_coverage_of_nothing_is_zero():
    assert sl.union_coverage([], AOI) == (0.0, 0)


def test_abutting_slices_with_a_metres_wide_sliver_count_as_one_part():
    """The real 2018-07-04 geometry. The two catalogue footprints describe the
    same shared edge about 3 m apart, so a raw union is a MultiPolygon and
    every genuine pair reads as disjoint. This is the bug JOIN_TOLERANCE_DEG
    exists for -- the imagery overlaps; the simplified polygons do not."""
    lower = Polygon([(-8.689227, 52.554928), (-4.957621, 52.954735),
                     (-4.587564, 51.459347), (-8.197609, 51.061700)])
    upper = Polygon([(-9.207246, 54.046288), (-5.341431, 54.449299),
                     (-4.956024, 52.954971), (-8.689258, 52.555000)])
    assert lower.intersection(upper).area == 0          # they do not overlap
    carlow = box(-7.2155, 52.6783, -6.6126, 53.0432)    # the real AOI bounds
    cov, parts = sl.union_coverage(
        [row("S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_4422.SAFE", lower),
         row("S1A_IW_GRDH_1SDV_20180704T181441_20180704T181506_022648_027435_479A.SAFE", upper)],
        carlow)
    assert parts == 1
    assert cov > sl.MIN_UNION_COVERAGE


def test_a_genuinely_missing_slice_is_still_seen_as_a_gap():
    """The tolerance must not be so generous that it bridges real absence. A
    missing IW slice leaves roughly 170 km, against a 550 m tolerance."""
    far_south = box(-2, -20, 12, -10)
    _, parts = sl.union_coverage(
        [s1a("181416", "181441", unique="4422", geom=far_south), NORTH_SLICE], AOI)
    assert parts == 2


# --------------------------------------------------------------------------
# assembly_problems
# --------------------------------------------------------------------------

def test_the_real_2018_pair_has_no_problems():
    assert sl.assembly_problems([SOUTH_SLICE, NORTH_SLICE], AOI) == []


def test_empty_input_is_a_problem():
    assert sl.assembly_problems([], AOI) == ["no products"]


def test_mixed_platforms_are_rejected():
    other = s1a("181441", "181506", unique="479A", geom=NORTH, plat="S1B")
    problems = sl.assembly_problems([SOUTH_SLICE, other], AOI)
    assert any("mixed platforms" in p for p in problems)


def test_different_datatakes_are_rejected():
    other = s1a("181441", "181506", datatake="999999", unique="479A", geom=NORTH)
    problems = sl.assembly_problems([SOUTH_SLICE, other], AOI)
    assert any("different datatakes" in p for p in problems)


def test_a_time_gap_between_slices_is_rejected():
    """A missing slice between two kept ones would assemble a product with a
    hole, and nothing downstream would notice."""
    late = s1a("181600", "181625", unique="479A", geom=NORTH)
    problems = sl.assembly_problems([SOUTH_SLICE, late], AOI)
    assert any("non-contiguous" in p for p in problems)


def test_a_small_timing_slack_is_tolerated():
    """Catalogue times are second-rounded and adjacent slices overlap slightly."""
    nudged = s1a("181443", "181508", unique="479A", geom=NORTH)
    problems = sl.assembly_problems([SOUTH_SLICE, nudged], AOI)
    assert not any("non-contiguous" in p for p in problems)


def test_duplicates_reaching_validation_are_reported():
    dup = dict(NORTH_SLICE)
    problems = sl.assembly_problems([NORTH_SLICE, dup], AOI)
    assert any("duplicate slices" in p for p in problems)


def test_an_incomplete_union_is_rejected():
    """Assembling two slices that still miss part of the AOI buys nothing --
    the result is the partial footprint REQ-17 existed to prevent."""
    short = box(-2, 0.5, 12, 1.768)
    a = s1a("181416", "181441", unique="4422", geom=short)
    problems = sl.assembly_problems([a, NORTH_SLICE], AOI)
    assert any("union covers" in p for p in problems)


def test_disjoint_footprints_are_rejected():
    far = s1a("181441", "181506", unique="479A", geom=FAR)
    problems = sl.assembly_problems([SOUTH_SLICE, far], AOI)
    assert any("do not join" in p for p in problems)


def test_an_unparsed_name_short_circuits_the_other_checks():
    bad = row("mystery.zip", NORTH)
    problems = sl.assembly_problems([SOUTH_SLICE, bad], AOI)
    assert len(problems) == 1 and "unparsed" in problems[0]


# --------------------------------------------------------------------------
# ipf_consistent
# --------------------------------------------------------------------------

def test_matching_baselines_pass():
    assert sl.ipf_consistent({"a.SAFE": "2.84", "b.SAFE": "2.84"}) == []


def test_differing_baselines_are_reported_with_the_seam_reason():
    problems = sl.ipf_consistent({"a.SAFE": "2.84", "b.SAFE": "2.90"})
    assert len(problems) == 1
    assert "different IPF baselines" in problems[0]
    assert "seam" in problems[0]


def test_an_unreadable_version_is_reported():
    problems = sl.ipf_consistent({"a.SAFE": "2.84", "b.SAFE": ""})
    assert any("unreadable" in p for p in problems)


def test_a_single_slice_is_trivially_consistent():
    assert sl.ipf_consistent({"a.SAFE": "2.84"}) == []


def test_no_slices_is_trivially_consistent():
    assert sl.ipf_consistent({}) == []


# --------------------------------------------------------------------------
# plan_acquisition
# --------------------------------------------------------------------------

def test_a_single_full_coverage_product_plans_as_single():
    full = s1a("181416", "181441", unique="4422", geom=box(-2, -5, 12, 20))
    p = sl.plan_acquisition([full], AOI)
    assert p["action"] == "single"
    assert p["products"] == [full]


def test_the_real_2018_pair_plans_as_assemble_in_time_order():
    p = sl.plan_acquisition([NORTH_SLICE, SOUTH_SLICE], AOI)
    assert p["action"] == "assemble"
    assert [r["name"] for r in p["products"]] == [
        SOUTH_SLICE["name"], NORTH_SLICE["name"]]


def test_the_real_2018_08_03_quartet_plans_as_assemble_of_two():
    rows = [
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_63D5.SAFE", SOUTH),
        row("S1B_IW_GRDH_1SDV_20180803T181336_20180803T181401_012102_016488_0169.SAFE", SOUTH),
        row("S1B_IW_GRDH_1SDV_20180803T181401_20180803T181426_012102_016488_A7F5.SAFE", NORTH),
        row("S1B_IW_GRDH_1SDV_20180803T181401_20180803T181426_012102_016488_8B2E.SAFE", NORTH),
    ]
    p = sl.plan_acquisition(rows, AOI)
    assert p["action"] == "assemble"
    assert len(p["products"]) == 2
    assert len(p["dropped"]) == 2


def test_a_lone_partial_slice_is_excluded_with_its_coverage_stated():
    p = sl.plan_acquisition([NORTH_SLICE], AOI)
    assert p["action"] == "exclude"
    assert "0.8232" in p["reason"]


def test_a_date_whose_slices_all_miss_the_aoi_is_excluded():
    far = s1a("181441", "181506", unique="479A", geom=FAR)
    p = sl.plan_acquisition([far], AOI)
    assert p["action"] == "exclude"
    assert "no slice intersects" in p["reason"]


def test_an_unassemblable_pair_is_excluded_carrying_the_reason():
    late = s1a("181600", "181625", unique="479A", geom=NORTH)
    p = sl.plan_acquisition([SOUTH_SLICE, late], AOI)
    assert p["action"] == "exclude"
    assert "non-contiguous" in p["reason"]


def test_duplicates_are_removed_before_the_single_slice_decision():
    """Two publications of one full-coverage slice must plan as 'single',
    not as an assembly of a strip with itself."""
    full_a = row("S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_AAAA.SAFE",
                 box(-2, -5, 12, 20))
    full_b = row("S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_BBBB.SAFE",
                 box(-2, -5, 12, 20))
    p = sl.plan_acquisition([full_a, full_b], AOI)
    assert p["action"] == "single"
    assert len(p["products"]) == 1
    assert len(p["dropped"]) == 1


def test_plan_never_returns_products_when_excluding():
    p = sl.plan_acquisition([NORTH_SLICE], AOI)
    assert p["action"] == "exclude" and p["products"] == []


def test_two_full_coverage_reslicings_plan_as_single_not_assemble():
    """The real 2022-10-11 case: one datatake, re-sliced two seconds apart,
    each product covering the AOI at 1.0000. Assembling them would weld two
    near-identical overlapping strips together; excluding loses a good
    acquisition. Take one."""
    whole = box(-2, -5, 12, 20)
    a = row("S1A_IW_GRDH_1SDV_20221011T181455_20221011T181520_045398_056DAA_F323.SAFE", whole)
    b = row("S1A_IW_GRDH_1SDV_20221011T181457_20221011T181522_045398_056DAA_E714.SAFE", whole)
    p = sl.plan_acquisition([a, b], AOI)
    assert p["action"] == "single"
    assert len(p["products"]) == 1
    assert len(p["dropped"]) == 1


def test_the_full_coverage_tie_break_is_the_name_not_a_rounding_artefact():
    """Two products covering the AOI, footprints differing by about a metre.
    The pick must come from the name, not from which area computes marginally
    larger in floating point."""
    # The product with the SMALLER name gets the LARGER footprint, so raw-area
    # comparison and name comparison disagree. Names differ first at the start
    # time (181455 vs 181457), which makes the 181457 product the larger name.
    bigger = box(-3, -6, 13, 21)
    smaller = box(-2, -5, 12, 20)
    a = row("S1A_IW_GRDH_1SDV_20221011T181455_20221011T181520_045398_056DAA_F323.SAFE", bigger)
    b = row("S1A_IW_GRDH_1SDV_20221011T181457_20221011T181522_045398_056DAA_E714.SAFE", smaller)
    assert sl.single_coverage(a, AOI) == sl.single_coverage(b, AOI) == 1.0
    p = sl.plan_acquisition([a, b], AOI)
    assert p["action"] == "single"
    # Both clip the AOI entirely, so coverage ties at 1.0 and the name decides.
    assert p["products"][0]["name"].endswith("E714.SAFE")


def test_a_full_slice_is_preferred_over_assembling_two_partials():
    """If one product covers the AOI, assembly is unnecessary work and an
    unnecessary seam."""
    whole = s1a("181506", "181531", unique="CCCC", geom=box(-2, -5, 12, 20))
    p = sl.plan_acquisition([SOUTH_SLICE, NORTH_SLICE, whole], AOI)
    assert p["action"] == "single"
    assert p["products"][0]["name"] == whole["name"]


def test_partial_slices_still_assemble_when_none_covers_alone():
    """2018: best single slice is 0.8232, so the preference above must not
    short-circuit the case assembly exists for."""
    p = sl.plan_acquisition([SOUTH_SLICE, NORTH_SLICE], AOI)
    assert p["action"] == "assemble"
    assert len(p["products"]) == 2


# --------------------------------------------------------------------------
# single_coverage
# --------------------------------------------------------------------------

def test_single_coverage_reproduces_the_catalogue_value():
    assert sl.single_coverage(NORTH_SLICE, AOI) == pytest.approx(0.8232, abs=5e-4)
    assert sl.single_coverage(SOUTH_SLICE, AOI) == pytest.approx(0.1768, abs=5e-4)


def test_single_coverage_of_a_distant_slice_is_zero():
    far = s1a("181506", "181531", unique="FFFF", geom=FAR)
    assert sl.single_coverage(far, AOI) == 0.0


def test_single_coverage_of_an_unreadable_footprint_is_zero():
    broken = dict(NORTH_SLICE)
    broken["footprint_wkt"] = "POLYGON ((bad"
    assert sl.single_coverage(broken, AOI) == 0.0
