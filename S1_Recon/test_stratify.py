"""Tests for the stratified difference-in-differences (phase 3)."""

from __future__ import annotations

import numpy as np
import pytest

from stratify import (
    build_masks,
    compare_slopes,
    contrast,
    did,
    erode,
    slope_per_month,
    stratum_stats,
)

CODES = {"Improved Grassland": 17, "Cultivated Land": 11,
         "Coniferous Forest": 10, "Mixed Forest": 19,
         "Broadleaved Forest and Woodland": 7}
STRATA = {"grassland": ["Improved Grassland"],
          "forest": ["Coniferous Forest", "Broadleaved Forest and Woodland",
                     "Mixed Forest"]}


# --- masks -----------------------------------------------------------------

def test_mask_selects_one_class():
    r = np.array([[17, 11], [10, 17]], dtype="uint8")
    m = build_masks(r, CODES, STRATA)
    assert m["grassland"].sum() == 2
    assert m["grassland"][0, 0] and m["grassland"][1, 1]


def test_forest_pools_its_three_classes():
    r = np.array([[10, 19], [7, 17]], dtype="uint8")
    m = build_masks(r, CODES, STRATA)
    assert m["forest"].sum() == 3
    assert not m["forest"][1, 1]


def test_strata_do_not_overlap():
    rng = np.random.default_rng(0)
    r = rng.choice([17, 11, 10, 19, 7], size=(40, 40)).astype("uint8")
    m = build_masks(r, CODES, STRATA)
    assert not (m["grassland"] & m["forest"]).any()


def test_unknown_class_raises_rather_than_returning_empty():
    # An empty mask would propagate as NaN and look like missing data, not a
    # configuration error.
    with pytest.raises(KeyError):
        build_masks(np.zeros((2, 2), "uint8"), CODES,
                    {"x": ["Not A Real Class"]})


# --- erosion ---------------------------------------------------------------

def test_erode_zero_is_a_no_op():
    m = np.ones((10, 10), bool)
    assert (erode(m, 0) == m).all()


def test_erode_removes_the_boundary_ring():
    m = np.zeros((11, 11), bool)
    m[2:9, 2:9] = True                  # a 7x7 block
    assert erode(m, 1).sum() == 25      # 5x5
    assert erode(m, 2).sum() == 9       # 3x3


def test_erode_destroys_a_parcel_thinner_than_the_kernel():
    # A hedge-width sliver should vanish rather than contribute mixed pixels.
    m = np.zeros((20, 20), bool)
    m[10, 2:18] = True                  # one pixel wide
    assert erode(m, 1).sum() == 0


def test_erode_treats_the_array_edge_as_outside():
    # Without border_value=0 a stratum touching the window edge keeps its
    # boundary pixels and quietly reintroduces the mixing erosion removes.
    m = np.ones((6, 6), bool)
    assert erode(m, 1).sum() == 16      # 4x4 interior


def test_erode_keeps_a_large_field_mostly_intact():
    m = np.zeros((60, 60), bool)
    m[5:55, 5:55] = True                # 50x50 px = 25 ha
    assert erode(m, 2).sum() / m.sum() > 0.84


# --- per-stratum statistics ------------------------------------------------

def arrs(vv=0.05, vh=0.005, shape=(20, 20)):
    return np.full(shape, vv), np.full(shape, vh)


def test_stratum_stats_on_a_uniform_patch():
    vv, vh = arrs()
    s = stratum_stats(vv, vh, np.ones(vv.shape, bool))
    assert s["n_px"] == 400
    assert s["vv_db"] == pytest.approx(-13.0103, abs=1e-3)
    assert s["cr_db"] == pytest.approx(-10.0, abs=1e-6)


def test_stratum_stats_respects_the_mask():
    vv, vh = arrs()
    vv[:10] = 0.5
    m = np.zeros(vv.shape, bool); m[10:] = True
    assert stratum_stats(vv, vh, m)["vv_db"] == pytest.approx(-13.0103, abs=1e-3)


def test_stratum_validity_is_joint():
    vv, vh = arrs()
    vv[0] = 0.0          # no-data in VV
    vh[0] = 1.0          # bright VH there must not be counted
    s = stratum_stats(vv, vh, np.ones(vv.shape, bool))
    assert s["n_px"] == 380
    assert s["cr_db"] == pytest.approx(-10.0, abs=1e-6)


def test_empty_stratum_returns_none_not_a_crash():
    vv, vh = arrs()
    assert stratum_stats(vv, vh, np.zeros(vv.shape, bool)) is None


# --- the contrast ----------------------------------------------------------

def test_contrast_subtracts_control_from_treatment():
    assert contrast({"cr_db": -6.0}, {"cr_db": -4.0}) == pytest.approx(-2.0)


def test_contrast_with_a_missing_stratum_is_nan():
    assert np.isnan(contrast(None, {"cr_db": -4.0}))
    assert np.isnan(contrast({"cr_db": -6.0}, None))


def test_a_common_gain_cancels_in_the_contrast():
    # The design's central claim: whatever calibration offset a platform
    # applies, both strata come from the SAME image and it cancels exactly.
    bias = 0.23
    plain = contrast({"cr_db": -6.0}, {"cr_db": -4.0})
    biased = contrast({"cr_db": -6.0 + bias}, {"cr_db": -4.0 + bias})
    assert biased == pytest.approx(plain)


def test_weather_common_to_both_strata_cancels():
    # A wet morning lifts grass and forest together; the contrast is unmoved.
    wet = 0.8
    assert contrast({"cr_db": -6.0 + wet}, {"cr_db": -4.0 + wet}) == \
        pytest.approx(contrast({"cr_db": -6.0}, {"cr_db": -4.0}))


# --- difference-in-differences --------------------------------------------

def test_did_recovers_a_known_shift():
    rng = np.random.default_rng(1)
    base = rng.normal(-2.0, 0.10, 10)
    treat = rng.normal(-2.0 - 0.5, 0.10, 10)
    d = did(treat, base)
    assert d["estimate"] == pytest.approx(-0.5, abs=0.12)
    assert d["p"] < 0.001
    assert d["ci_lo"] < -0.5 < d["ci_hi"]


def test_did_of_no_effect_is_not_significant():
    rng = np.random.default_rng(2)
    d = did(rng.normal(-2.0, 0.3, 10), rng.normal(-2.0, 0.3, 10))
    assert d["p"] > 0.05
    assert d["ci_lo"] < 0 < d["ci_hi"]


def test_did_interval_brackets_the_estimate():
    d = did([-2.4, -2.5, -2.3, -2.6, -2.5], [-2.0, -2.1, -1.9, -2.0, -2.1])
    assert d["ci_lo"] < d["estimate"] < d["ci_hi"]


def test_did_ignores_nan_acquisitions():
    d = did([-2.5, np.nan, -2.4, -2.6, -2.5], [-2.0, -2.1, -1.9, -2.0])
    assert d["n_treat"] == 4 and d["n_base"] == 4


def test_did_refuses_to_report_on_too_few_points():
    d = did([-2.5, -2.4], [-2.0, -2.1, -1.9, -2.0])
    assert np.isnan(d["estimate"])


# --- slopes ----------------------------------------------------------------

def test_slope_of_a_clean_decline():
    doys = [182, 194, 206, 218, 230, 242]
    vals = [-2.0 - 0.01 * (d - 182) for d in doys]
    s = slope_per_month(doys, vals)
    assert s["slope"] == pytest.approx(-0.3, abs=1e-6)   # 0.01 dB/day
    assert s["r2"] == pytest.approx(1.0)


def test_slope_needs_four_points():
    s = slope_per_month([182, 194, 206], [-2.0, -2.1, -2.2])
    assert np.isnan(s["slope"])


def test_compare_slopes_detects_a_steeper_decline():
    doys = [182, 194, 206, 218, 230, 242, 254, 266]
    rng = np.random.default_rng(3)
    slow = [-2.0 - 0.008 * (d - 182) + rng.normal(0, 0.02) for d in doys]
    fast = [-2.0 - 0.020 * (d - 182) + rng.normal(0, 0.02) for d in doys]
    c = compare_slopes(slope_per_month(doys, fast), slope_per_month(doys, slow))
    assert c["delta"] == pytest.approx(-0.36, abs=0.06)
    assert c["p"] < 0.001


def test_compare_identical_slopes_is_not_significant():
    doys = [182, 194, 206, 218, 230, 242, 254, 266]
    rng = np.random.default_rng(4)
    a = [-2.0 - 0.01 * (d - 182) + rng.normal(0, 0.15) for d in doys]
    b = [-2.0 - 0.01 * (d - 182) + rng.normal(0, 0.15) for d in doys]
    assert compare_slopes(slope_per_month(doys, a),
                          slope_per_month(doys, b))["p"] > 0.05


def test_compare_slopes_propagates_nan():
    good = slope_per_month([182, 194, 206, 218], [-2.0, -2.1, -2.2, -2.3])
    bad = slope_per_month([182, 194], [-2.0, -2.1])
    assert np.isnan(compare_slopes(good, bad)["p"])


# --- the baseline distribution ---------------------------------------------

from stratify import (baseline_z, loo_calibration, pooled_baseline,   # noqa: E402
                      tau_squared)


def test_tau_is_zero_when_scatter_is_only_fitting_error():
    # Five years whose estimates differ by less than their own error bars.
    # The honest between-year variance is zero, not a small positive number.
    est = [-0.20, -0.21, -0.19, -0.20, -0.21]
    se = [0.10] * 5
    assert tau_squared(est, se) == pytest.approx(0.0, abs=1e-9)


def test_tau_detects_real_between_year_spread():
    est = [-0.10, -0.30, -0.50, -0.20, -0.40]
    se = [0.02] * 5
    assert np.sqrt(tau_squared(est, se)) == pytest.approx(0.14, abs=0.03)


def test_tau_needs_two_years():
    assert np.isnan(tau_squared([-0.2], [0.05]))


def test_pooled_mean_downweights_the_imprecise_year():
    # 2022-2024 carry 6-8 limb points against 15 for 2021 and 2025. Counting
    # them equally would let the weakest fits steer the baseline.
    est = [-0.20, -0.20, -0.20, -0.20, -1.00]
    se = [0.02, 0.02, 0.02, 0.02, 0.50]
    p = pooled_baseline(est, se)
    assert p["mean"] == pytest.approx(-0.20, abs=0.02)
    assert p["k"] == 5


def test_pooled_mean_is_the_plain_mean_when_precision_is_equal():
    est = [-0.10, -0.20, -0.30]
    p = pooled_baseline(est, [0.05] * 3)
    assert p["mean"] == pytest.approx(-0.20, abs=1e-6)


def test_pooled_ignores_unusable_years():
    p = pooled_baseline([-0.2, np.nan, -0.3], [0.05, 0.05, 0.05])
    assert p["k"] == 2


def test_a_normal_year_lands_inside_the_prediction_interval():
    est = [-0.18, -0.22, -0.20, -0.19, -0.21]
    se = [0.04] * 5
    r = baseline_z(-0.21, 0.04, est, se)
    assert r["pi_lo"] <= -0.21 <= r["pi_hi"]
    assert r["p"] > 0.05


def test_a_clear_outlier_lands_outside():
    est = [-0.18, -0.22, -0.20, -0.19, -0.21]
    se = [0.02] * 5
    r = baseline_z(-0.60, 0.02, est, se)
    assert r["z"] < -3
    assert not (r["pi_lo"] <= -0.60 <= r["pi_hi"])
    assert r["p"] < 0.05


def test_prediction_interval_is_wider_than_the_mean_interval():
    # The distinction the whole test rests on: asking whether 2026 COULD BE a
    # normal year must include the spread of normal years, not just the
    # uncertainty in where their centre sits.
    est = [-0.10, -0.30, -0.20, -0.35, -0.15]
    se = [0.02] * 5
    p = pooled_baseline(est, se)
    r = baseline_z(-0.20, 0.02, est, se)
    assert (r["pi_hi"] - r["pi_lo"]) > 4 * p["se"]


def test_wide_baselines_refuse_to_call_anything_unusual():
    # Noisy baseline years must produce a wide interval, so a moderately
    # extreme drought year is correctly reported as inconclusive.
    est = [-0.05, -0.45, -0.15, -0.40, -0.25]
    se = [0.05] * 5
    r = baseline_z(-0.55, 0.05, est, se)
    assert r["p"] > 0.05


def test_baseline_z_needs_at_least_two_years():
    r = baseline_z(-0.5, 0.05, [-0.2], [0.05])
    assert np.isnan(r["z"])


def test_loo_reports_every_baseline_year():
    yrs = [2021, 2022, 2023, 2024, 2025]
    est = [-0.18, -0.22, -0.20, -0.19, -0.21]
    cal = loo_calibration(yrs, est, [0.04] * 5)
    assert [c["year"] for c in cal] == yrs
    assert all(abs(c["z"]) < 2 for c in cal)


def test_loo_exposes_an_interval_that_is_too_narrow():
    # One baseline year far from the rest: leave-one-out should flag it, which
    # is the signal that a similar z for the drought year means nothing.
    yrs = [2021, 2022, 2023, 2024, 2025]
    est = [-0.20, -0.20, -0.20, -0.20, -0.80]
    cal = loo_calibration(yrs, est, [0.03] * 5)
    worst = max(cal, key=lambda c: abs(c["z"]))
    assert worst["year"] == 2025
    assert abs(worst["z"]) > 3


def test_loo_excludes_the_year_under_test():
    yrs = [2021, 2022, 2023]
    est = [-0.20, -0.21, -0.19]
    cal = loo_calibration(yrs, est, [0.05] * 3)
    # With the year itself included every z would be shrunk toward zero.
    assert all(np.isfinite(c["z"]) for c in cal)


# --- the observable the contrast is taken on ------------------------------

from stratify import METRIC_NAME                                 # noqa: E402


def test_contrast_can_be_taken_on_a_single_channel():
    a = {"cr_db": -6.0, "vv_db": -10.5, "vh_db": -16.5}
    b = {"cr_db": -4.0, "vv_db": -11.0, "vh_db": -15.0}
    assert contrast(a, b, "cr_db") == pytest.approx(-2.0)
    assert contrast(a, b, "vv_db") == pytest.approx(+0.5)
    assert contrast(a, b, "vh_db") == pytest.approx(-1.5)


def test_cross_ratio_hides_a_common_mode_drop():
    # The reason --metric exists. A drought that dims BOTH channels equally
    # leaves the cross-ratio untouched, so a cross-ratio-only analysis would
    # report nothing while VV and VH each moved by a full dB.
    normal = {"cr_db": -6.0, "vv_db": -10.0, "vh_db": -16.0}
    drought = {"cr_db": -6.0, "vv_db": -11.0, "vh_db": -17.0}
    ctrl = {"cr_db": -4.0, "vv_db": -11.5, "vh_db": -15.5}
    assert contrast(drought, ctrl, "cr_db") == contrast(normal, ctrl, "cr_db")
    assert contrast(drought, ctrl, "vv_db") != contrast(normal, ctrl, "vv_db")


def test_metric_names_cover_every_choice():
    assert set(METRIC_NAME) == {"cr_db", "vv_db", "vh_db"}


# --- level at a reference day (NCR-14) -------------------------------------

from stratify import REF_DOY, level_at_ref                        # noqa: E402


def test_level_recovers_a_flat_series():
    doys = [186, 198, 210, 222, 234, 246, 258, 270]
    r = level_at_ref(doys, [-2.0] * 8)
    assert r["level"] == pytest.approx(-2.0, abs=1e-9)
    assert r["n"] == 8


def test_level_is_evaluated_at_the_reference_day_not_the_mean():
    doys = [186, 210, 234, 258]
    vals = [-2.0 - 0.01 * (d - 186) for d in doys]   # 0.01 dB per day
    r = level_at_ref(doys, vals, ref_doy=186)
    assert r["level"] == pytest.approx(-2.0, abs=1e-6)
    assert level_at_ref(doys, vals, ref_doy=286)["level"] == \
        pytest.approx(-3.0, abs=1e-6)


# 2026 sigma0 VV, grassland minus forest, through the senescence limb -- the
# real measured series, kept as a fixture because no synthetic curve reproduces
# what this observable actually does: flat and low through the dry midsummer,
# then a 1.4 dB step when the autumn rain arrives in late August.
VV_2026_DOY = [186, 192, 198, 204, 210, 216, 222, 228, 234, 240, 246, 252,
               258, 264, 270]
VV_2026 = [-4.54, -5.13, -5.44, -5.50, -5.04, -4.68, -5.52, -5.67, -5.23,
           -3.82, -3.31, -3.94, -3.56, -4.13, -3.54]


def test_a_shifted_window_breaks_the_slope_but_not_the_level():
    """NCR-14, on the real data that exposed it.

    Restricting the six years to 2024's shorter, later window (2024 carries a
    24-day gap across 1 July) moved the fitted SLOPES by up to 0.50 dB/month,
    sd 0.32 -- against a between-year spread of only 0.26. The artefact was
    larger than the quantity being measured, which is what made every VV and VH
    slope test uninterpretable and put 2024 at |z| up to 4.75.

    The same restriction moves the LEVEL at a common day by at most 0.15 dB,
    sd 0.07, against a between-year spread of 0.54 -- roughly an eighth.
    """
    keep = [(d, v) for d, v in zip(VV_2026_DOY, VV_2026) if 202 <= d <= 262]
    rd, rv = [d for d, _ in keep], [v for _, v in keep]

    d_slope = abs(slope_per_month(rd, rv)["slope"]
                  - slope_per_month(VV_2026_DOY, VV_2026)["slope"])
    d_level = abs(level_at_ref(rd, rv)["level"]
                  - level_at_ref(VV_2026_DOY, VV_2026)["level"])

    assert d_slope > 0.4, "the window shift must move the slope substantially"
    assert d_level < 0.2, "and must barely move the level"
    assert d_slope > 2 * d_level


def test_the_limb_trajectory_is_not_a_straight_line():
    # The premise of NCR-14. If VV were linear through the limb the slope test
    # would be fine and none of this would be needed.
    r2 = slope_per_month(VV_2026_DOY, VV_2026)
    assert r2["r2"] < 0.6, "a straight line does not describe this series"


def test_level_se_is_smallest_at_the_sampling_centroid():
    doys = list(range(186, 272, 6))
    centre = level_at_ref(doys, list(np.random.default_rng(0).normal(-2, .1, len(doys))),
                          ref_doy=float(np.mean(doys)))
    far = level_at_ref(doys, list(np.random.default_rng(0).normal(-2, .1, len(doys))),
                       ref_doy=400.0)
    assert centre["se"] < far["se"]


def test_level_needs_four_points():
    assert np.isnan(level_at_ref([186, 210, 234], [-2.0, -2.1, -2.2])["level"])


def test_reference_day_sits_inside_the_limb():
    from stratify import END_DOY, PEAK_DOY
    assert PEAK_DOY < REF_DOY < END_DOY
