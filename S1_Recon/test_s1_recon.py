"""Tests for the Phase 0 reconnaissance script.

Nothing here touches the network: every test exercises a pure function with
plain data, which is the point of keeping HTTP confined to `fetch_products`.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from s1_recon import (
    Acquisition,
    Scene,
    merge_slices,
    build_filter,
    container_from_name,
    coverage_stats,
    max_gap_days,
    parse_attributes,
    platform_from_name,
    polygon_to_wkt,
    scene_from_product,
    summarise,
    year_windows,
)

AOI = box(-7.2155, 52.6783, -6.6126, 53.0432)


def dt(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# query construction
# --------------------------------------------------------------------------

def test_wkt_closes_the_ring_and_uses_lon_lat():
    wkt = polygon_to_wkt(box(0, 1, 2, 3))
    assert wkt.startswith("POLYGON((") and wkt.endswith("))")
    coords = [c.split() for c in wkt[9:-2].split(",")]
    assert coords[0] == coords[-1], "ring must be closed"
    # lon first: all x in [0,2], all y in [1,3]
    assert all(0 <= float(x) <= 2 and 1 <= float(y) <= 3 for x, y in coords)


def test_filter_pins_collection_product_type_and_window():
    f = build_filter(AOI, dt(2026, 4, 1), dt(2026, 11, 1))
    assert "Collection/Name eq 'SENTINEL-1'" in f
    assert "'IW_GRDH_1S'" in f
    assert "ContentDate/Start ge 2026-04-01T00:00:00.000Z" in f
    assert "ContentDate/Start lt 2026-11-01T00:00:00.000Z" in f
    assert "OData.CSC.Intersects" in f


def test_filter_uses_the_nested_attribute_syntax():
    # the short form (a/Value) silently matches nothing on CDSE
    f = build_filter(AOI, dt(2026, 1, 1), dt(2027, 1, 1))
    assert "a/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S'" in f


def test_optional_filters_are_absent_unless_asked_for():
    f = build_filter(AOI, dt(2026, 1, 1), dt(2027, 1, 1))
    assert "orbitDirection" not in f
    assert "relativeOrbitNumber" not in f

    f2 = build_filter(AOI, dt(2026, 1, 1), dt(2027, 1, 1),
                      orbit_direction="ascending", relative_orbit=30)
    assert "a/OData.CSC.StringAttribute/Value eq 'ASCENDING'" in f2
    assert "a/OData.CSC.IntegerAttribute/Value eq 30" in f2


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def test_parse_attributes_keeps_only_wanted_keys():
    raw = [
        {"Name": "relativeOrbitNumber", "Value": 30},
        {"Name": "orbitDirection", "Value": "ASCENDING"},
        {"Name": "somethingElse", "Value": "ignore me"},
    ]
    out = parse_attributes(raw)
    assert out == {"relativeOrbitNumber": 30, "orbitDirection": "ASCENDING"}


def test_parse_attributes_tolerates_empty():
    assert parse_attributes([]) == {}
    assert parse_attributes(None) == {}


@pytest.mark.parametrize("name,expected", [
    ("S1A_IW_GRDH_1SDV_20260615T182345_...SAFE", "S1A"),
    ("S1C_IW_GRDH_1SDV_20260715T182345_...SAFE", "S1C"),
    ("S1D_IW_GRDH_1SDV_20260815T182345_...SAFE", "S1D"),
    ("garbage", "UNKNOWN"),
])
def test_platform_from_name(name, expected):
    assert platform_from_name(name) == expected


def test_container_detects_cog_safe():
    assert container_from_name("S1A_IW_GRDH_1SDV_2024_COG.SAFE") == "COG_SAFE"
    assert container_from_name("S1D_IW_GRDH_1SDV_2026.SAFE") == "SAFE"


# --------------------------------------------------------------------------
# coverage geometry
# --------------------------------------------------------------------------

def test_full_containment_scores_one():
    footprint = box(-8, 52, -6, 54)
    frac, margin = coverage_stats(footprint, AOI)
    assert frac == pytest.approx(1.0)
    assert margin > 0


def test_half_coverage_scores_half():
    # footprint covers the western half of the AOI only
    mid = (-7.2155 + -6.6126) / 2
    footprint = box(-8, 52, mid, 54)
    frac, _ = coverage_stats(footprint, AOI)
    assert frac == pytest.approx(0.5, abs=0.01)


def test_no_overlap_scores_zero():
    frac, margin = coverage_stats(box(0, 0, 1, 1), AOI)
    assert frac == 0.0
    assert margin == 0.0


def test_centroid_outside_footprint_gives_zero_margin():
    # AOI centroid not inside -> margin is meaningless, must not be positive
    mid = (-7.2155 + -6.6126) / 2
    footprint = box(-8, 52, mid - 0.2, 54)
    _, margin = coverage_stats(footprint, AOI)
    assert margin == 0.0


def test_multipolygon_footprint_is_handled():
    """A pass whose GRD slices do not touch unions to a MultiPolygon, which
    has no .exterior. Regression: this crashed the first slice-merge build."""
    disjoint = MultiPolygon([box(-9, 51, -7.0, 54), box(-6.8, 51, -5, 54)])
    frac, margin = coverage_stats(disjoint, AOI)
    assert 0.0 < frac < 1.0
    assert margin == 0.0          # centroid falls in the hole between slices


def test_multipolygon_containing_the_centroid_gives_a_margin():
    disjoint = MultiPolygon([box(-9, 51, -6.5, 54), box(-6.0, 51, -5, 54)])
    _, margin = coverage_stats(disjoint, AOI)
    assert margin > 0


def test_margin_is_larger_for_a_more_central_aoi():
    tight = box(-8, 52.4, -6, 53.4)
    wide = box(-12, 50, -2, 56)
    _, m_tight = coverage_stats(tight, AOI)
    _, m_wide = coverage_stats(wide, AOI)
    assert m_wide > m_tight


# --------------------------------------------------------------------------
# gaps
# --------------------------------------------------------------------------

def test_max_gap_of_regular_series():
    dates = [dt(2026, 4, 1), dt(2026, 4, 7), dt(2026, 4, 13)]
    assert max_gap_days(dates) == 6


def test_max_gap_finds_the_hole():
    dates = [dt(2026, 4, 1), dt(2026, 4, 7), dt(2026, 6, 1)]
    assert max_gap_days(dates) == 55


def test_max_gap_counts_calendar_days_not_elapsed_time():
    """Regression: passes on the same orbit drift a second or two earlier
    each cycle, so an elapsed-timedelta gap truncates 24 days to 23."""
    a = datetime(2024, 6, 26, 18, 14, 56, tzinfo=timezone.utc)
    b = datetime(2024, 7, 20, 18, 14, 55, tzinfo=timezone.utc)
    assert (b - a).days == 23          # what the naive version reported
    assert max_gap_days([a, b]) == 24  # calendar truth


def test_max_gap_is_order_independent():
    a = [dt(2026, 6, 1), dt(2026, 4, 1), dt(2026, 4, 7)]
    b = [dt(2026, 4, 1), dt(2026, 4, 7), dt(2026, 6, 1)]
    assert max_gap_days(a) == max_gap_days(b)


@pytest.mark.parametrize("dates", [[], [dt(2026, 4, 1)]])
def test_max_gap_degenerate_cases(dates):
    assert max_gap_days(dates) == 0


# --------------------------------------------------------------------------
# product -> Scene
# --------------------------------------------------------------------------

def _product(name="S1C_IW_GRDH_1SDV_20260715T182345_x.SAFE",
             rel=30, direction="ASCENDING", start="2026-07-15T18:23:45.000Z",
             geom=None):
    return {
        "Id": "abc-123",
        "Name": name,
        "ContentDate": {"Start": start},
        "ContentLength": 1_700_000_000,
        "Online": True,
        "GeoFootprint": geom or {
            "type": "Polygon",
            "coordinates": [[[-9, 51], [-5, 51], [-5, 54], [-9, 54], [-9, 51]]],
        },
        "Attributes": [
            {"Name": "productType", "Value": "IW_GRDH_1S"},
            {"Name": "operationalMode", "Value": "IW"},
            {"Name": "orbitDirection", "Value": direction},
            {"Name": "relativeOrbitNumber", "Value": rel},
            {"Name": "orbitNumber", "Value": 54321},
            {"Name": "polarisationChannels", "Value": "VV&VH"},
        ],
    }


def test_scene_from_product_extracts_the_key_fields():
    sc = scene_from_product(_product(), AOI)
    assert sc is not None
    assert sc.platform == "S1C"
    assert sc.relative_orbit == 30
    assert sc.orbit_direction == "ASCENDING"
    assert sc.polarisation == "VV&VH"
    assert sc.aoi_coverage == pytest.approx(1.0)
    assert sc.date == "2026-07-15"


def test_scene_from_product_rejects_missing_footprint():
    p = _product()
    del p["GeoFootprint"]
    assert scene_from_product(p, AOI) is None


def test_scene_from_product_rejects_missing_relative_orbit():
    p = _product()
    p["Attributes"] = [a for a in p["Attributes"]
                       if a["Name"] != "relativeOrbitNumber"]
    assert scene_from_product(p, AOI) is None


# --------------------------------------------------------------------------
# slice merging -- GRD arrives sliced along-track
# --------------------------------------------------------------------------

WEST = box(-9, 51, -6.92, 54)     # covers the western ~half of the AOI
EAST = box(-6.94, 51, -5, 54)     # covers the eastern ~half, small overlap
WHOLE = box(-9, 51, -5, 54)


def _scene(rel, direction, when, footprint=WHOLE, platform="S1A",
           container="SAFE", aoi=AOI):
    frac, margin = coverage_stats(footprint, aoi)
    return Scene(
        product_id="x", name=f"{platform}_IW_GRDH_1SDV", start=when,
        platform=platform, product_type="IW_GRDH_1S", mode="IW",
        orbit_direction=direction, relative_orbit=rel, absolute_orbit=1,
        polarisation="VV&VH", size_bytes=1_700_000_000, container=container,
        aoi_coverage=round(frac, 4), min_edge_dist_km=round(margin, 1),
        online=True, footprint_wkt=footprint.wkt,
    )


def test_two_slices_on_one_date_become_one_acquisition():
    when = dt(2026, 7, 15)
    scenes = [_scene(30, "ASCENDING", when, WEST),
              _scene(30, "ASCENDING", when, EAST)]
    acqs = merge_slices(scenes, AOI)
    assert len(acqs) == 1
    assert acqs[0].n_slices == 2


def test_union_of_slices_recovers_full_coverage():
    """The regression this whole layer exists for.

    Neither slice covers the AOI alone -- judged per product the orbit looks
    unusable. Their union covers it completely.
    """
    when = dt(2026, 7, 15)
    west = _scene(30, "ASCENDING", when, WEST)
    east = _scene(30, "ASCENDING", when, EAST)
    assert west.aoi_coverage < 0.9 and east.aoi_coverage < 0.9

    acq, = merge_slices([west, east], AOI)
    assert acq.coverage == pytest.approx(1.0, abs=0.001)


def test_non_contiguous_slices_do_not_crash_and_report_partial():
    """Slices with a gap between them union to a MultiPolygon. The merge must
    survive it and report honestly partial coverage, not fail."""
    when = dt(2026, 7, 15)
    far_west = box(-9, 51, -7.10, 54)
    far_east = box(-6.70, 51, -5, 54)
    scenes = [_scene(30, "ASCENDING", when, far_west),
              _scene(30, "ASCENDING", when, far_east)]
    acq, = merge_slices(scenes, AOI)
    assert acq.n_slices == 2
    assert 0.0 < acq.coverage < 0.99


def test_contiguous_slices_report_one_part():
    when = dt(2026, 7, 15)
    acq, = merge_slices([_scene(30, "ASCENDING", when, WEST),
                         _scene(30, "ASCENDING", when, EAST)], AOI)
    assert acq.n_parts == 1


def test_non_contiguous_slices_report_two_parts():
    when = dt(2026, 7, 15)
    acq, = merge_slices([_scene(30, "ASCENDING", when, box(-9, 51, -7.10, 54)),
                         _scene(30, "ASCENDING", when, box(-6.70, 51, -5, 54))],
                        AOI)
    assert acq.n_parts == 2


def test_different_dates_stay_separate():
    scenes = [_scene(30, "ASCENDING", dt(2026, 7, 15)),
              _scene(30, "ASCENDING", dt(2026, 7, 21))]
    assert len(merge_slices(scenes, AOI)) == 2


def test_same_date_different_orbits_stay_separate():
    when = dt(2026, 7, 15)
    scenes = [_scene(30, "ASCENDING", when), _scene(103, "ASCENDING", when)]
    assert len(merge_slices(scenes, AOI)) == 2


def test_same_date_opposite_directions_stay_separate():
    when = dt(2026, 7, 15)
    scenes = [_scene(30, "ASCENDING", when), _scene(30, "DESCENDING", when)]
    assert len(merge_slices(scenes, AOI)) == 2


def test_merge_records_platforms_and_size():
    when = dt(2026, 7, 15)
    scenes = [_scene(30, "ASCENDING", when, WEST, platform="S1C"),
              _scene(30, "ASCENDING", when, EAST, platform="S1C")]
    acq, = merge_slices(scenes, AOI)
    assert acq.platforms == "S1C"
    assert acq.size_gb == pytest.approx(3.4, abs=0.01)


def test_merge_falls_back_to_best_slice_without_geometry():
    """A CSV round-trip loses the footprint; the union is then bounded below
    by the best single slice rather than silently reported as zero."""
    when = dt(2026, 7, 15)
    s = _scene(30, "ASCENDING", when, WHOLE)
    stripped = Scene(**{**asdict_compat(s), "footprint_wkt": ""})
    acq, = merge_slices([stripped], AOI)
    assert acq.coverage == pytest.approx(s.aoi_coverage)


def asdict_compat(scene):
    from dataclasses import asdict
    return asdict(scene)


# --------------------------------------------------------------------------
# summarising and ranking -- the part that actually picks the orbit
# --------------------------------------------------------------------------

def _acq(rel, direction, when, coverage=1.0, platforms="S1A", margin=90.0,
         n_slices=1):
    return Acquisition(
        relative_orbit=rel, orbit_direction=direction,
        date=when.date().isoformat(), n_slices=n_slices, n_parts=1,
        coverage=coverage, min_edge_dist_km=margin, platforms=platforms,
        size_gb=1.7, when=when,
    )


def _season(rel, direction, years, step=6, **kw):
    """A regular 6-day series of acquisitions across Apr-Oct of each year."""
    out = []
    for y in years:
        d = dt(y, 4, 1)
        while d < dt(y, 11, 1):
            out.append(_acq(rel, direction, d, **kw))
            d += timedelta(days=step)
    return out


YEARS = [2024, 2025, 2026]


def test_complete_orbit_is_viable():
    s = summarise(_season(30, "ASCENDING", YEARS), YEARS)
    assert len(s) == 1
    assert s[0].verdict == "VIABLE"
    assert s[0].n_years == 3


def test_partial_coverage_is_rejected():
    s = summarise(_season(31, "ASCENDING", YEARS, coverage=0.62), YEARS)
    assert s[0].verdict == "partial coverage"


def test_missing_year_is_named():
    s = summarise(_season(32, "ASCENDING", [2024, 2025]), YEARS)
    assert s[0].verdict == "missing 2026"


def test_off_season_between_years_is_not_a_gap():
    """Apr-Oct sampling leaves a ~5 month winter hole. That is the season
    boundary, not a coverage failure -- gaps are measured within a season."""
    s = summarise(_season(30, "ASCENDING", YEARS), YEARS)
    assert s[0].max_gap_days <= 7
    assert s[0].verdict == "VIABLE"


def test_long_gap_is_flagged():
    acqs = (_season(33, "ASCENDING", YEARS)
            + [_acq(33, "ASCENDING", dt(2025, 12, 20))])
    s = summarise(acqs, YEARS)
    assert s[0].verdict.startswith("gap")


def test_viable_orbit_ranks_above_broken_ones():
    acqs = (_season(31, "ASCENDING", YEARS, coverage=0.62)
            + _season(32, "DESCENDING", [2024, 2025])
            + _season(30, "ASCENDING", YEARS))
    s = summarise(acqs, YEARS)
    assert s[0].relative_orbit == 30
    assert s[0].verdict == "VIABLE"


def test_ascending_and_descending_are_separate_candidates():
    acqs = _season(30, "ASCENDING", YEARS) + _season(30, "DESCENDING", YEARS)
    s = summarise(acqs, YEARS)
    assert len(s) == 2
    assert {o.orbit_direction for o in s} == {"ASCENDING", "DESCENDING"}


def test_platform_handover_is_recorded_not_hidden():
    """REQ-09: the S1A -> S1C/S1D transition must be visible in the summary."""
    acqs = (_season(30, "ASCENDING", [2024, 2025], platforms="S1A")
            + _season(30, "ASCENDING", [2026], platforms="S1D"))
    s = summarise(acqs, YEARS)
    assert s[0].platforms == "S1A,S1D"


def test_interleaved_platforms_are_all_listed():
    """2025-26 interleaves S1A, S1C and S1D on the same orbit."""
    acqs = (_season(30, "ASCENDING", [2024], platforms="S1A")
            + _season(30, "ASCENDING", [2025], platforms="S1A,S1C")
            + _season(30, "ASCENDING", [2026], platforms="S1C,S1D"))
    s = summarise(acqs, YEARS)
    assert s[0].platforms == "S1A,S1C,S1D"


def test_sliced_acquisitions_are_counted():
    acqs = (_season(30, "ASCENDING", [2024])
            + _season(30, "ASCENDING", [2025, 2026], n_slices=2))
    s = summarise(acqs, YEARS)
    assert s[0].n_sliced == len([a for a in acqs if a.n_slices > 1])


def test_per_year_counts_are_reported_for_every_required_year():
    s = summarise(_season(30, "ASCENDING", [2024, 2026]), YEARS)
    assert "2025:0" in s[0].years


# --------------------------------------------------------------------------
# windows
# --------------------------------------------------------------------------

def test_year_windows_respect_the_month_range():
    (start, end), = year_windows([2026], (4, 10))
    assert start == dt(2026, 4, 1)
    assert end == dt(2026, 11, 1)


def test_year_windows_handle_december_rollover():
    (start, end), = year_windows([2026], (4, 12))
    assert end == dt(2027, 1, 1)


def test_year_windows_full_year_when_months_none():
    (start, end), = year_windows([2026], None)
    assert (start, end) == (dt(2026, 1, 1), dt(2027, 1, 1))


def test_one_window_per_year():
    assert len(year_windows(YEARS, (4, 10))) == 3
