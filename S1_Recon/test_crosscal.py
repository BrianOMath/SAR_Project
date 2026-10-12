"""Tests for the cross-calibration maths (REQ-09).

Everything here is a pure function. The I/O -- opening .img files, building
the AOI mask -- lives in read_pair() and is exercised by running the thing on
real scenes, not by mocking rasterio.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from rasterio.transform import from_origin

from crosscal import (
    aligned_windows,
    bin_by_angle,
    frac_misalignment,
    grid_offset,
    intersect_bounds,
    is_valid_pair,
    offset_db,
    parse_stem,
    to_db,
)

# A plausible EPSG:2157 origin for the Oak Park AOI, on the 10 m lattice.
ORIGIN_X, ORIGIN_Y = 653000.0, 699000.0


def tr(x=ORIGIN_X, y=ORIGIN_Y, px=10.0):
    return from_origin(x, y, px, px)


# --- stem parsing ----------------------------------------------------------

def test_parse_stem():
    assert parse_stem("20260423_S1C") == (date(2026, 4, 23), "S1C")
    assert parse_stem("20260628_S1A") == (date(2026, 6, 28), "S1A")


@pytest.mark.parametrize("bad", ["2026-04-23_S1C", "20260423_S2A", "20260423",
                                 "20260423_S1C.dim", ""])
def test_parse_stem_rejects_junk(bad):
    with pytest.raises(ValueError):
        parse_stem(bad)


# --- pair validity ---------------------------------------------------------

def test_consecutive_days_different_platforms_is_valid():
    ok, note = is_valid_pair("20260424_S1D", "20260423_S1C")
    assert ok
    assert "S1D" in note and "S1C" in note


def test_same_day_different_platforms_is_valid():
    # Two platforms on the same date would be an even better pair.
    ok, _ = is_valid_pair("20260423_S1D", "20260423_S1C")
    assert ok


def test_same_platform_is_not_a_pair():
    ok, note = is_valid_pair("20260424_S1C", "20260423_S1C")
    assert not ok
    assert "cross platforms" in note


def test_two_days_apart_is_rejected():
    ok, note = is_valid_pair("20260425_S1D", "20260423_S1C")
    assert not ok
    assert "2 days apart" in note


def test_month_boundary_counts_correctly():
    # 30 April -> 1 May is one day, not a jump backwards of 29.
    ok, _ = is_valid_pair("20260501_S1D", "20260430_S1C")
    assert ok


def test_unparseable_stem_is_not_a_pair():
    ok, note = is_valid_pair("rubbish", "20260423_S1C")
    assert not ok
    assert "not a scene stem" in note


# --- geometry --------------------------------------------------------------

def test_intersect_bounds_overlap():
    a = (0.0, 0.0, 100.0, 100.0)
    b = (50.0, 50.0, 200.0, 200.0)
    assert intersect_bounds(a, b) == (50.0, 50.0, 100.0, 100.0)


def test_intersect_bounds_disjoint():
    assert intersect_bounds((0, 0, 10, 10), (20, 20, 30, 30)) is None


def test_intersect_bounds_touching_is_not_overlap():
    # Sharing an edge gives a zero-area intersection: no pixels, no comparison.
    assert intersect_bounds((0, 0, 10, 10), (10, 0, 20, 10)) is None


def test_grid_offset_identical_transforms():
    assert grid_offset(tr(), tr()) == (0.0, 0.0)


def test_grid_offset_whole_pixels():
    dc, dr = grid_offset(tr(), tr(ORIGIN_X + 30.0, ORIGIN_Y - 50.0))
    assert dc == pytest.approx(3.0)
    assert dr == pytest.approx(5.0)          # y decreases as rows increase


def test_frac_misalignment_on_lattice_is_zero():
    assert frac_misalignment(tr(), tr(ORIGIN_X + 120.0)) == pytest.approx(0.0)


def test_frac_misalignment_detects_half_pixel():
    # This is exactly what alignToStandardGrid=false produces: an origin
    # taken from the footprint rather than snapped to the grid.
    assert frac_misalignment(tr(), tr(ORIGIN_X + 125.0)) == pytest.approx(0.5)


def test_frac_misalignment_takes_the_worse_axis():
    f = frac_misalignment(tr(), tr(ORIGIN_X + 121.0, ORIGIN_Y - 123.0))
    assert f == pytest.approx(0.3)


def test_aligned_windows_identical_rasters():
    out = aligned_windows(tr(), (0, 0, 1000, 1000), tr(), (0, 0, 1000, 1000))
    wa, wb, _, frac = out
    assert (wa.col_off, wa.row_off) == (wb.col_off, wb.row_off)
    assert wa.width == wb.width and wa.height == wb.height
    assert frac == pytest.approx(0.0)


def test_aligned_windows_same_shape_when_offset():
    # Offset origins must still yield windows of identical shape, or the
    # arrays cannot be compared element-wise at all.
    ta, tb = tr(), tr(ORIGIN_X + 100.0, ORIGIN_Y - 100.0)
    ba = (ORIGIN_X, ORIGIN_Y - 5000.0, ORIGIN_X + 5000.0, ORIGIN_Y)
    bb = (ORIGIN_X + 100.0, ORIGIN_Y - 5100.0,
          ORIGIN_X + 5100.0, ORIGIN_Y - 100.0)
    wa, wb, _, frac = aligned_windows(ta, ba, tb, bb)
    assert (wa.width, wa.height) == (wb.width, wb.height)
    assert frac == pytest.approx(0.0)


def test_aligned_windows_reports_subpixel_offset():
    ta, tb = tr(), tr(ORIGIN_X + 3.7, ORIGIN_Y - 3.7)
    ba = (ORIGIN_X, ORIGIN_Y - 5000.0, ORIGIN_X + 5000.0, ORIGIN_Y)
    bb = (ORIGIN_X + 3.7, ORIGIN_Y - 5003.7,
          ORIGIN_X + 5003.7, ORIGIN_Y - 3.7)
    wa, wb, _, frac = aligned_windows(ta, ba, tb, bb)
    assert (wa.width, wa.height) == (wb.width, wb.height)
    assert frac == pytest.approx(0.37, abs=1e-6)


def test_aligned_windows_disjoint_is_none():
    ta, tb = tr(), tr(ORIGIN_X + 1e6)
    assert aligned_windows(ta, (0, 0, 10, 10), tb, (1e6, 0, 1e6 + 10, 10)) is None


# --- dB --------------------------------------------------------------------

def test_to_db_round_numbers():
    assert to_db(1.0) == pytest.approx(0.0)
    assert to_db(2.0) == pytest.approx(3.0103, abs=1e-4)
    assert to_db(0.01) == pytest.approx(-20.0)


def test_to_db_of_non_positive_is_nan():
    assert np.isnan(to_db(0.0))
    assert np.isnan(to_db(-0.5))


# --- the offset itself -----------------------------------------------------

def test_identical_scenes_give_zero_offset():
    a = np.full((50, 50), 0.05)
    s = offset_db(a, a.copy(), np.ones_like(a, dtype=bool))
    assert s["mean_db"] == pytest.approx(0.0, abs=1e-9)
    assert s["median_db"] == pytest.approx(0.0, abs=1e-9)
    assert s["n_px"] == 2500


def test_a_doubled_gives_three_db():
    b = np.full((40, 40), 0.03)
    s = offset_db(b * 2.0, b, np.ones_like(b, dtype=bool))
    assert s["mean_db"] == pytest.approx(3.0103, abs=1e-4)
    assert s["median_db"] == pytest.approx(3.0103, abs=1e-4)


def test_offset_is_antisymmetric():
    rng = np.random.default_rng(0)
    b = rng.gamma(4.0, 0.01, size=(60, 60))
    a = b * 1.1
    v = np.ones_like(b, dtype=bool)
    assert offset_db(a, b, v)["mean_db"] == \
        pytest.approx(-offset_db(b, a, v)["mean_db"], abs=1e-9)


def test_mask_restricts_the_comparison():
    a = np.full((10, 10), 0.02)
    b = np.full((10, 10), 0.02)
    a[:5, :] = 0.2           # a wildly different half, masked out
    valid = np.zeros_like(a, dtype=bool)
    valid[5:, :] = True
    s = offset_db(a, b, valid)
    assert s["n_px"] == 50
    assert s["mean_db"] == pytest.approx(0.0, abs=1e-9)


def test_negatives_are_kept_in_the_mean():
    # The whole point of clipNegativeValues=false: the noise-subtracted mean
    # is unbiased only if the negative tail stays in it.
    a = np.array([[-0.001, 0.02, 0.03, 0.04]])
    b = np.full_like(a, 0.02)
    s = offset_db(a, b, np.ones_like(a, dtype=bool))
    assert s["mean_a"] == pytest.approx(a.mean())
    assert s["n_px"] == 4


def test_negatives_are_excluded_from_the_median_ratio():
    a = np.array([[-0.001, 0.02, 0.02, 0.02]])
    b = np.full_like(a, 0.02)
    s = offset_db(a, b, np.ones_like(a, dtype=bool))
    assert s["n_px"] == 4
    assert s["n_px_positive"] == 3
    assert s["median_db"] == pytest.approx(0.0, abs=1e-9)


def test_median_survives_an_outlier_the_mean_does_not():
    rng = np.random.default_rng(1)
    b = rng.gamma(4.0, 0.01, size=(100, 100))
    a = b.copy()
    a[0, 0] = 1e6                      # one corner reflector, or one bad pixel
    v = np.ones_like(b, dtype=bool)
    s = offset_db(a, b, v)
    assert s["median_db"] == pytest.approx(0.0, abs=1e-9)
    assert s["mean_db"] > 1.0          # the mean is wrecked, visibly


def test_empty_mask_is_nan_not_a_crash():
    a = np.full((5, 5), 0.02)
    s = offset_db(a, a.copy(), np.zeros_like(a, dtype=bool))
    assert s["n_px"] == 0
    assert np.isnan(s["mean_db"])
    assert np.isnan(s["median_db"])


def test_speckle_does_not_bias_the_offset():
    # Two independent 4-look speckle fields with the same underlying mean
    # must come out at 0 dB, or the estimator itself has a bias and every
    # number this script prints is suspect.
    rng = np.random.default_rng(42)
    truth = 0.05
    a = rng.gamma(4.0, truth / 4.0, size=(400, 400))
    b = rng.gamma(4.0, truth / 4.0, size=(400, 400))
    s = offset_db(a, b, np.ones_like(a, dtype=bool))
    assert s["mean_db"] == pytest.approx(0.0, abs=0.05)
    assert s["median_db"] == pytest.approx(0.0, abs=0.05)
    assert s["iqr_db"] > 2.0           # per-pixel spread is large; that is fine


# --- incidence-angle stratification ---------------------------------------

def test_flat_offset_is_flat_across_angle_bins():
    inc = np.repeat(np.linspace(34.0, 41.9, 80), 80).reshape(80, 80)
    b = np.full((80, 80), 0.04)
    a = b * 1.05
    rows = bin_by_angle(a, b, inc, np.ones_like(b, dtype=bool),
                        np.arange(34.0, 42.1, 2.0))
    usable = [r for r in rows if np.isfinite(r["mean_db"])]
    assert len(usable) == 4
    spread = max(r["mean_db"] for r in usable) - \
        min(r["mean_db"] for r in usable)
    assert spread == pytest.approx(0.0, abs=1e-9)


def test_angle_dependent_offset_shows_up_as_a_slope():
    inc = np.repeat(np.linspace(34.0, 41.9, 80), 80).reshape(80, 80)
    b = np.full((80, 80), 0.04)
    a = b * 10 ** ((0.1 * (inc - 34.0)) / 10.0)     # 0.1 dB per degree
    rows = bin_by_angle(a, b, inc, np.ones_like(b, dtype=bool),
                        np.arange(34.0, 42.1, 2.0))
    usable = [r for r in rows if np.isfinite(r["mean_db"])]
    spread = max(r["mean_db"] for r in usable) - \
        min(r["mean_db"] for r in usable)
    assert spread == pytest.approx(0.6, abs=0.05)


def test_thin_angle_bins_are_reported_not_guessed():
    # A bin with a handful of pixels gets NaN rather than a number nobody
    # should trust.
    inc = np.full((20, 20), 35.0)
    inc[0, 0] = 41.0
    b = np.full((20, 20), 0.04)
    rows = bin_by_angle(b * 1.1, b, inc, np.ones_like(b, dtype=bool),
                        np.arange(34.0, 42.1, 2.0))
    last = rows[-1]
    assert last["n_px"] == 1
    assert np.isnan(last["mean_db"])


# --- cross-ratio -----------------------------------------------------------

from crosscal import bin_trend, cross_ratio_offset          # noqa: E402


def test_cross_ratio_is_the_difference_of_the_two_channels():
    bands = {"Sigma0_VV": {"mean_db": 0.1472},
             "Sigma0_VH": {"mean_db": 0.0349}}
    assert cross_ratio_offset(bands) == pytest.approx(-0.1123, abs=1e-6)


def test_common_mode_gain_cancels_in_the_cross_ratio():
    # A platform running 0.5 dB hot in BOTH channels has no cross-ratio bias
    # at all. This is the whole reason the metric is worth measuring apart
    # from the individual channels.
    bands = {"Sigma0_VV": {"mean_db": 0.5}, "Sigma0_VH": {"mean_db": 0.5}}
    assert cross_ratio_offset(bands) == pytest.approx(0.0)


def test_cross_ratio_needs_both_channels():
    assert np.isnan(cross_ratio_offset({"Sigma0_VV": {"mean_db": 0.1}}))
    assert np.isnan(cross_ratio_offset({}))


def test_cross_ratio_can_exceed_either_channel():
    # Opposite-sign channel errors add in the ratio rather than cancelling.
    bands = {"Sigma0_VV": {"mean_db": 0.2}, "Sigma0_VH": {"mean_db": -0.2}}
    assert cross_ratio_offset(bands) == pytest.approx(-0.4)


# --- bin trend -------------------------------------------------------------

def rows(*vals, n=2_000_000):
    return [{"lo": 34.0 + 2 * i, "hi": 36.0 + 2 * i, "n_px": n, "mean_db": v}
            for i, v in enumerate(vals)]


def test_bin_trend_rising_is_monotonic():
    spread, mono = bin_trend(rows(0.12, 0.20, 0.25, 0.31))
    assert spread == pytest.approx(0.19, abs=1e-9)
    assert mono


def test_bin_trend_falling_is_monotonic():
    _, mono = bin_trend(rows(0.31, 0.25, 0.20, 0.12))
    assert mono


def test_bin_trend_flat_is_monotonic_and_tiny():
    spread, mono = bin_trend(rows(0.1, 0.1, 0.1, 0.1))
    assert spread == pytest.approx(0.0)
    assert mono


def test_the_real_june_vv_bins_are_not_monotonic():
    # The measured case: rises across three bins, then drops in the thin
    # 40-42 tail. That shape is scatter, not a geometric slope, and the
    # spread-only test called it a slope.
    spread, mono = bin_trend(rows(0.12, 0.20, 0.25, 0.08))
    assert spread == pytest.approx(0.17, abs=1e-9)
    assert not mono


def test_bin_trend_ignores_nan_bins():
    r = rows(0.1, 0.2)
    r.append({"lo": 38.0, "hi": 40.0, "n_px": 3, "mean_db": float("nan")})
    spread, mono = bin_trend(r)
    assert spread == pytest.approx(0.1, abs=1e-9)
    assert mono


def test_bin_trend_needs_two_usable_bins():
    spread, mono = bin_trend(rows(0.1))
    assert np.isnan(spread)
    assert not mono
