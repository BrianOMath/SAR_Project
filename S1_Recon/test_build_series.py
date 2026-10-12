"""Tests for the time-series maths (phase 2, REQ-18)."""

from __future__ import annotations

import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin

from build_series import (
    aoi_stats,
    cross_ratio_db,
    grid_key,
    pctiles,
    rvi,
    stack_problems,
)

CRS_2157 = CRS.from_epsg(2157)


def tr(x=653000.0, y=699000.0, px=10.0):
    return from_origin(x, y, px, px)


# --- grid identity ---------------------------------------------------------

def test_identical_rasters_share_a_grid_key():
    assert grid_key(CRS_2157, tr()) == grid_key(CRS_2157, tr())


def test_different_extents_on_the_same_lattice_share_a_key():
    # Scenes have different footprints. That is normal and must not be
    # mistaken for a grid mismatch -- only the phase modulo the pixel matters.
    assert grid_key(CRS_2157, tr(653000.0, 699000.0)) == \
        grid_key(CRS_2157, tr(661230.0, 684560.0))


def test_subpixel_offset_breaks_the_key():
    # This is NCR-12: alignToStandardGrid=false puts the origin at the
    # footprint corner, an arbitrary real number.
    assert grid_key(CRS_2157, tr(653000.0)) != grid_key(CRS_2157, tr(653004.21))


def test_different_pixel_size_breaks_the_key():
    assert grid_key(CRS_2157, tr(px=10.0)) != grid_key(CRS_2157, tr(px=20.0), px=10.0)


def test_different_crs_breaks_the_key():
    assert grid_key(CRS_2157, tr()) != grid_key(CRS.from_epsg(4326), tr())


def test_one_lattice_is_no_problem():
    keys = {f"s{i}": grid_key(CRS_2157, tr(653000.0 + 10 * i)) for i in range(5)}
    assert stack_problems(keys) == []


def test_mixed_lattices_are_reported_with_the_minority_named():
    keys = {f"ok{i}": grid_key(CRS_2157, tr(653000.0 + 10 * i)) for i in range(6)}
    keys["odd_one_out"] = grid_key(CRS_2157, tr(653004.21))
    out = stack_problems(keys)
    assert out, "a mixed stack must be reported"
    assert "2 different pixel lattices" in out[0]
    assert any("odd_one_out" in line for line in out)
    # The majority grid is listed first, so the minority is visibly the minority.
    assert "6 scene(s)" in out[1]


def test_many_odd_scenes_are_summarised_not_dumped():
    keys = {f"a{i}": grid_key(CRS_2157, tr(653000.0)) for i in range(3)}
    keys |= {f"b{i}": grid_key(CRS_2157, tr(653004.21)) for i in range(9)}
    out = "\n".join(stack_problems(keys))
    assert "+5 more" in out


def test_empty_stack_is_a_problem():
    assert stack_problems({}) == ["no scenes found"]


# --- indices ---------------------------------------------------------------

def test_rvi_of_equal_channels():
    # VV == VH means 4*x/(2x) == 2
    assert rvi(0.05, 0.05) == pytest.approx(2.0)


def test_rvi_rises_with_depolarisation():
    # More volume scattering -> more VH relative to VV -> higher RVI.
    assert rvi(0.05, 0.004) < rvi(0.05, 0.010) < rvi(0.05, 0.020)


def test_rvi_is_immune_to_common_mode_gain():
    # A platform 10% hot in both channels gives the identical RVI, which is
    # why this index and the cross-ratio are the ones worth trusting across
    # S1A / S1C / S1D.
    assert rvi(0.05 * 1.1, 0.008 * 1.1) == pytest.approx(rvi(0.05, 0.008))


def test_rvi_of_non_positive_sum_is_nan():
    assert np.isnan(rvi(0.0, 0.0))
    assert np.isnan(rvi(-0.05, 0.01))


def test_cross_ratio_is_vh_minus_vv():
    # 0.05 -> -13.01 dB, 0.005 -> -23.01 dB
    assert cross_ratio_db(0.05, 0.005) == pytest.approx(-10.0, abs=1e-9)


def test_cross_ratio_immune_to_common_mode_gain():
    assert cross_ratio_db(0.05 * 1.2, 0.005 * 1.2) == \
        pytest.approx(cross_ratio_db(0.05, 0.005), abs=1e-9)


def test_cross_ratio_of_non_positive_is_nan():
    assert np.isnan(cross_ratio_db(-0.01, 0.005))
    assert np.isnan(cross_ratio_db(0.05, 0.0))


# --- percentiles -----------------------------------------------------------

def test_pctiles_of_a_ramp():
    q = pctiles(np.arange(1.0, 101.0))
    assert q["median"] == pytest.approx(50.5)
    assert q["p05"] < q["p25"] < q["median"] < q["p75"] < q["p95"]


def test_pctiles_of_empty_is_all_nan():
    q = pctiles(np.array([]))
    assert all(np.isnan(v) for v in q.values())


# --- the per-acquisition statistics ----------------------------------------

def arrays(vv_val=0.05, vh_val=0.005, inc_val=37.7, shape=(20, 20)):
    return (np.full(shape, vv_val), np.full(shape, vh_val),
            np.full(shape, inc_val))


def test_uniform_scene_gives_the_expected_values():
    vv, vh, inc = arrays()
    s = aoi_stats(vv, vh, inc, np.ones(vv.shape, dtype=bool))
    assert s["valid_fraction"] == pytest.approx(1.0)
    assert s["sigma0_vv_lin"] == pytest.approx(0.05)
    assert s["sigma0_vv_db"] == pytest.approx(-13.0103, abs=1e-3)
    assert s["cross_ratio_db"] == pytest.approx(-10.0, abs=1e-6)
    assert s["incidence_deg"] == pytest.approx(37.7)


def test_mask_restricts_the_average():
    vv, vh, inc = arrays()
    vv[:10, :] = 0.5                      # a bright half, outside the AOI
    mask = np.zeros(vv.shape, dtype=bool)
    mask[10:, :] = True
    s = aoi_stats(vv, vh, inc, mask)
    assert s["n_px_aoi"] == 200
    assert s["sigma0_vv_lin"] == pytest.approx(0.05)


def test_zero_is_treated_as_nodata():
    vv, vh, inc = arrays()
    vv[0, :] = 0.0                        # SNAP's post-TC no-data
    s = aoi_stats(vv, vh, inc, np.ones(vv.shape, dtype=bool))
    assert s["n_px_valid"] == 380
    assert s["valid_fraction"] == pytest.approx(0.95)
    assert s["sigma0_vv_lin"] == pytest.approx(0.05)


def test_validity_is_joint_across_polarisations():
    # The critical one. If VV and VH were averaged over different pixel sets,
    # their ratio would carry a spurious term -- and the cross-ratio is the
    # project's primary metric.
    vv, vh, inc = arrays()
    vv[0, :] = 0.0                        # VV missing on row 0
    vh[0, :] = 1.0                        # VH bright there; must NOT be counted
    s = aoi_stats(vv, vh, inc, np.ones(vv.shape, dtype=bool))
    assert s["n_px_valid"] == 380
    assert s["sigma0_vh_lin"] == pytest.approx(0.005)
    assert s["cross_ratio_db"] == pytest.approx(-10.0, abs=1e-6)


def test_nan_pixels_are_excluded():
    vv, vh, inc = arrays()
    vv[0, 0] = np.nan
    s = aoi_stats(vv, vh, inc, np.ones(vv.shape, dtype=bool))
    assert s["n_px_valid"] == 399
    assert np.isfinite(s["sigma0_vv_lin"])


def test_negatives_are_kept_in_the_mean_and_counted():
    vv, vh, inc = arrays()
    vh[0, :] = -0.0005                    # noise-floor pixels, clipping is off
    s = aoi_stats(vv, vh, inc, np.ones(vv.shape, dtype=bool))
    assert s["n_px_valid"] == 400
    assert s["neg_fraction_vh"] == pytest.approx(0.05)
    assert s["sigma0_vh_lin"] < 0.005     # the tail pulls the mean down, correctly


def test_fully_masked_scene_returns_nans_not_a_crash():
    vv, vh, inc = arrays()
    s = aoi_stats(vv, vh, inc, np.zeros(vv.shape, dtype=bool))
    assert s["n_px_valid"] == 0
    assert s["valid_fraction"] == 0.0
    assert np.isnan(s["cross_ratio_db"])
    assert np.isnan(s["rvi"])


def test_linear_mean_differs_from_the_db_mean():
    # The REQ-06 trap, demonstrated. A scene of half bright and half dim
    # pixels has a linear mean whose dB value is NOT the mean of the dB values
    # -- averaging in dB understates the bright half every time.
    vv = np.concatenate([np.full(200, 0.1), np.full(200, 0.01)])
    vh = np.full(400, 0.005)
    inc = np.full(400, 37.7)
    s = aoi_stats(vv, vh, inc, np.ones(400, dtype=bool))
    db_of_mean = s["sigma0_vv_db"]
    mean_of_db = float(np.mean(10 * np.log10(vv)))
    assert db_of_mean == pytest.approx(-12.6, abs=0.1)
    assert mean_of_db == pytest.approx(-15.0, abs=0.1)
    assert db_of_mean > mean_of_db + 2.0
