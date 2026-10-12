"""Tests for the land cover fetch and rasterisation (phase 3)."""

from __future__ import annotations

import numpy as np
import pytest

from fetch_landcover import (
    PAGE,
    area_table,
    assign_group,
    class_codes,
    page_params,
)

BOUNDS = (653044.2, 659462.2, 693044.2, 699462.2)


# --- class grouping --------------------------------------------------------
# Written against the 29 Level-2 names the service actually returned over the
# Oak Park AOI, not against guessed strings.

@pytest.mark.parametrize("name", [
    "Improved Grassland", "Cultivated Land", "Dry Grassland", "Wet Grassland",
])
def test_classes_that_respond_to_drought(name):
    assert assign_group(name) == "RESPONSE"


@pytest.mark.parametrize("name", [
    "Coniferous Forest", "Broadleaved Forest and Woodland", "Mixed Forest",
])
def test_the_control_is_closed_canopy_forest_only(name):
    assert assign_group(name) == "CONTROL"


def test_transitional_forest_is_not_a_control():
    # Clearfell and young replanting. A 2018 transitional stand is eight years
    # older by 2026, so it carries a large systematic trend of its own -- and at
    # 53.7 km2 it would have dominated a 170 km2 control group.
    assert assign_group("Transitional Forest") == "EXCLUDE"


@pytest.mark.parametrize("name", ["Hedgerows", "Treelines", "Ways",
                                  "Rivers and Streams"])
def test_linear_features_are_excluded(name):
    # At 10 m nearly every pixel of a hedge straddles a boundary, so the class
    # measures a mixture rather than a cover type.
    assert assign_group(name) == "EXCLUDE"


def test_amenity_grassland_is_not_farmed_grass():
    assert assign_group("Amenity Grassland") == "EXCLUDE"


@pytest.mark.parametrize("name", ["Buildings", "Other Artificial Surfaces",
                                  "Lakes and Ponds", "Bare Soil and Disturbed "
                                  "Ground", "Swamp", "Scrub", "Bracken",
                                  "Raised Bog", "Cutover Bog", "Wet Heath"])
def test_remaining_classes_are_excluded(name):
    assert assign_group(name) == "EXCLUDE"


def test_every_class_the_service_returned_is_mapped():
    # The guard that matters: if the AOI or the map version changes and a new
    # class appears, this fails rather than the class vanishing into UNASSIGNED
    # unnoticed in a long printout.
    observed = [
        "Improved Grassland", "Cultivated Land", "Coniferous Forest",
        "Transitional Forest", "Hedgerows", "Wet Grassland",
        "Broadleaved Forest and Woodland", "Amenity Grassland", "Ways",
        "Other Artificial Surfaces", "Treelines", "Dry Grassland", "Buildings",
        "Scrub", "Mixed Forest", "Rivers and Streams",
        "Bare Soil and Disturbed Ground", "Exposed Rock and Sediments",
        "Bracken", "Lakes and Ponds", "Wet Heath", "Bare Peat", "Cutover Bog",
        "Artificial Waterbodies", "Dry Heath", "Raised Bog", "Blanket Bog",
        "Swamp", "Coastal Sediments",
    ]
    assert len(observed) == 29
    unmapped = [n for n in observed if assign_group(n) == "UNASSIGNED"]
    assert unmapped == [], f"unmapped classes: {unmapped}"


def test_unknown_class_is_flagged_not_guessed():
    assert assign_group("Transitional Something") == "UNASSIGNED"
    assert assign_group("") == "UNASSIGNED"
    assert assign_group(None) == "UNASSIGNED"


def test_grouping_tolerates_case_and_spacing():
    assert assign_group("IMPROVED  GRASSLAND") == "RESPONSE"
    assert assign_group("  coniferous forest ") == "CONTROL"


def test_no_partial_match():
    # "Grassland" alone is not a published class; matching it loosely is how
    # Amenity Grassland would sneak into RESPONSE.
    assert assign_group("Grassland") == "UNASSIGNED"


# --- stable codes ----------------------------------------------------------

def test_codes_are_one_based():
    assert 0 not in class_codes(["a", "b", "c"]).values()


def test_codes_are_stable_regardless_of_input_order():
    # A code that shifted between runs would silently relabel every result.
    a = class_codes(["Forest", "Grassland", "Bog"])
    b = class_codes(["Bog", "Grassland", "Forest", "Grassland"])
    assert a == b


def test_codes_deduplicate():
    assert len(class_codes(["x", "x", "y"])) == 2


# --- query paging ----------------------------------------------------------

def test_page_params_carry_the_envelope_and_crs():
    p = page_params(BOUNDS, 0)
    assert p["geometry"] == "653044.2,659462.2,693044.2,699462.2"
    assert p["inSR"] == 2157 and p["outSR"] == 2157
    assert p["spatialRel"] == "esriSpatialRelIntersects"
    assert p["f"] == "geojson"


def test_page_params_advance_the_offset():
    assert page_params(BOUNDS, 0)["resultOffset"] == 0
    assert page_params(BOUNDS, PAGE)["resultOffset"] == PAGE


def test_page_params_request_the_fields_the_analysis_needs():
    assert "LEVEL_2_VALUE" in page_params(BOUNDS, 0)["outFields"]
    assert page_params(BOUNDS, 0)["returnGeometry"] == "true"


# --- area accounting -------------------------------------------------------

def codes3():
    return {"Improved Grassland": 1, "Coniferous Forest": 2, "Lakes and Ponds": 3}


def test_area_table_counts_only_aoi_pixels():
    r = np.zeros((10, 10), dtype="uint8")
    r[:, :] = 1
    mask = np.zeros((10, 10), dtype=bool)
    mask[:5, :] = True                      # half the raster is in the AOI
    rows = area_table(r, mask, codes3(), 100.0)
    grass = next(x for x in rows if x["level_2"] == "Improved Grassland")
    assert grass["n_px"] == 50
    assert grass["aoi_fraction"] == pytest.approx(1.0)


def test_area_table_converts_to_km2():
    r = np.ones((100, 100), dtype="uint8")
    rows = area_table(r, np.ones((100, 100), bool), codes3(), 100.0)
    grass = next(x for x in rows if x["code"] == 1)
    assert grass["area_km2"] == pytest.approx(10_000 * 100.0 / 1e6)


def test_unmapped_pixels_are_reported_not_dropped():
    # Gaps between polygons are real and must show up, or the class fractions
    # silently fail to sum to the AOI.
    r = np.zeros((10, 10), dtype="uint8")
    r[:4, :] = 1
    rows = area_table(r, np.ones((10, 10), bool), codes3(), 100.0)
    nopoly = next(x for x in rows if x["level_2"] == "(no polygon)")
    assert nopoly["n_px"] == 60
    assert sum(x["aoi_fraction"] for x in rows) == pytest.approx(1.0)


def test_fractions_sum_to_one_over_a_full_partition():
    rng = np.random.default_rng(0)
    r = rng.integers(1, 4, size=(50, 50)).astype("uint8")
    rows = area_table(r, np.ones((50, 50), bool), codes3(), 100.0)
    assert sum(x["aoi_fraction"] for x in rows) == pytest.approx(1.0)
    assert all(x["n_px"] > 0 for x in rows if x["code"] > 0)


def test_area_table_carries_the_group_through():
    r = np.ones((5, 5), dtype="uint8")
    rows = area_table(r, np.ones((5, 5), bool), codes3(), 100.0)
    by_name = {x["level_2"]: x["group"] for x in rows}
    assert by_name["Improved Grassland"] == "RESPONSE"
    assert by_name["Coniferous Forest"] == "CONTROL"
    assert by_name["Lakes and Ponds"] == "EXCLUDE"


def test_empty_aoi_does_not_divide_by_zero():
    r = np.ones((5, 5), dtype="uint8")
    rows = area_table(r, np.zeros((5, 5), bool), codes3(), 100.0)
    assert all(x["aoi_fraction"] == 0.0 for x in rows)
