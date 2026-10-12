#!/usr/bin/env python3
"""Stratified difference-in-differences: did the 2026 drought show up? (phase 3)

The whole-AOI aggregate could not answer this. Day-to-day soil moisture moves
sigma0 by 0.63 dB between matched acquisitions, and that is larger than any
plausible drought effect, so the test read weather plus drought and could not
separate them.

The design
----------
Stop asking "how dark is the AOI" and ask "how dark is the grass compared with
the wood beside it".

    effect = (grass - forest)_2026  -  (grass - forest)_2025

The INNER subtraction removes the weather. A forest and the field next to it
get the same rain on the same night, are imaged in the same pass by the same
satellite at the same incidence angle. Every nuisance term is common to both
and cancels. Closed-canopy forest barely responds to summer drought -- C-band
saturates on a full canopy and tree roots reach water that grass roots cannot --
so the gap between them is almost free of weather and still carries the signal.

The OUTER subtraction removes everything permanent. Forest is darker than grass
in VH every day of every year for structural reasons that have nothing to do
with 2026. Subtracting a normal year leaves only what changed.

Platform calibration cancels too, for free: both strata come from the SAME
image, so whatever gain S1A or S1D applies, it applies to both. REQ-09 remains
necessary for the absolute series; the contrasts here do not depend on it. That
is worth stating in the report rather than quietly benefiting from.

The tests, in the order they were decided
-----------------------------------------
PRIMARY, stated before this script existed (see the plan): the post-peak
senescence slope. 2026's whole-AOI cross-ratio fell 40% faster than 2024 or
2025 from July to September -- p = 0.081, which after ~28 exploratory tests is
nothing. Here it is tested once, on a contrast the earlier work never touched.

SECONDARY: level difference-in-differences over a stated window.

INTERNAL: dry grassland versus wet grassland. They sit at opposite ends of a
drainage gradient, so drought should hit dry harder. No forest involved, so it
fails or succeeds independently of whether forest is a good control.

Erosion
-------
197,134 polygons over 1,600 km2 is a mean parcel of 0.8 ha, and Irish fields are
hedge-bounded. At 10 m a large share of pixels straddle a boundary and measure a
mixture. Each stratum mask is therefore eroded inward before sampling, so only
parcel interiors contribute. It costs sample size; the script reports how much.

Usage
-----
    python stratify.py C:\\sar\\proc --aoi aoi_oakpark.geojson \\
        --classes ../data/landcover/nlcm_2018_classes.tif \\
        --areas ../results/phase3/landcover_areas.csv \\
        --erode 2 --out ../results/phase3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from scipy import stats
from scipy.ndimage import binary_erosion
from shapely.ops import transform as shp_transform

from build_series import grid_key, to_db
from crosscal import parse_stem
from verify_scene import band_files, data_dir, load_aoi

# Analysis strata, composed from the published Level-2 classes. Forest is
# pooled because no single forest type has enough area alone; the three are
# all closed canopy and behave alike for this purpose.
STRATA = {
    "grassland": ["Improved Grassland"],
    "tillage":   ["Cultivated Land"],
    "dry_grass": ["Dry Grassland"],
    "wet_grass": ["Wet Grassland"],
    "forest":    ["Coniferous Forest", "Broadleaved Forest and Woodland",
                  "Mixed Forest"],
}

# (treatment, control). The third pair carries no forest, so it is an
# independent check on the first two rather than a restatement of them.
CONTRASTS = [("grassland", "forest"),
             ("tillage", "forest"),
             ("dry_grass", "wet_grass")]

METRIC_NAME = {"cr_db": "cross-ratio (VH - VV)",
               "vv_db": "sigma0 VV",
               "vh_db": "sigma0 VH"}

MIN_PX = 20_000          # below this a stratum mean is too noisy to use
PEAK_DOY, END_DOY = 182, 273      # 1 July - 30 September, the senescence limb
# 15 August: inside every year's sampling window and within 6 days of every
# year's mean limb date (2021-2026 means run 221-232), so no year's level is
# extrapolated.
REF_DOY = 227


def load_codes(areas_csv: Path) -> dict[str, int]:
    """Class name -> raster code, from the fetch script's own output.

    Read rather than recomputed: if the two ever disagreed about which integer
    means forest, every number below would be wrong and nothing would complain.
    """
    out = {}
    with areas_csv.open() as fh:
        for row in csv.DictReader(fh):
            out[row["level_2"]] = int(row["code"])
    return out


def build_masks(code_raster: np.ndarray, codes: dict[str, int],
                strata: dict[str, list[str]]) -> dict[str, np.ndarray]:
    """One boolean mask per analysis stratum."""
    masks = {}
    for name, members in strata.items():
        m = np.zeros(code_raster.shape, dtype=bool)
        for cls in members:
            if cls not in codes:
                raise KeyError(f"{cls!r} is not in the class table")
            m |= (code_raster == codes[cls])
        masks[name] = m
    return masks


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    """Shrink a mask inward by `px` pixels.

    Removes the boundary ring where a pixel contains two cover types. A 0.8 ha
    field is about 9x9 pixels, so eroding by 2 leaves roughly a third of it --
    expensive, and the reason the cost is reported rather than buried.
    """
    if px <= 0:
        return mask
    k = 2 * px + 1
    return binary_erosion(mask, structure=np.ones((k, k), dtype=bool),
                          border_value=0)


def aoi_window(src, aoi_p) -> Window:
    """The AOI window in a raster, snapped to whole pixels.

    Every raster here shares one lattice, so the same bounds give windows that
    differ only by an integer offset and cover identical ground.
    """
    w = from_bounds(*aoi_p.bounds, transform=src.transform)
    w = w.round_offsets().round_lengths()
    return w.intersection(Window(0, 0, src.width, src.height))


def stratum_stats(vv: np.ndarray, vh: np.ndarray,
                  mask: np.ndarray) -> dict | None:
    """Linear-power means over one stratum, converted to dB once (REQ-06).

    Validity is joint across polarisations so the two means cover the identical
    pixel set; otherwise their difference -- the cross-ratio -- inherits a term
    from the mismatch.
    """
    valid = (mask & np.isfinite(vv) & np.isfinite(vh)
             & (vv != 0.0) & (vh != 0.0))
    n = int(valid.sum())
    if n == 0:
        return None
    a, b = float(vv[valid].mean()), float(vh[valid].mean())
    if a <= 0 or b <= 0:
        return None
    return {"n_px": n, "vv_db": to_db(a), "vh_db": to_db(b),
            "cr_db": to_db(b) - to_db(a)}


def contrast(stats_a: dict | None, stats_b: dict | None,
             metric: str = "cr_db") -> float:
    """treatment minus control, same date, same image."""
    if not stats_a or not stats_b:
        return float("nan")
    return stats_a[metric] - stats_b[metric]


def did(c_treat: np.ndarray, c_base: np.ndarray) -> dict:
    """Difference-in-differences with a Welch interval.

    c_treat / c_base are per-acquisition contrast values for the drought year
    and the reference year over the same seasonal window.
    """
    c_treat = np.asarray(c_treat, float); c_treat = c_treat[np.isfinite(c_treat)]
    c_base = np.asarray(c_base, float); c_base = c_base[np.isfinite(c_base)]
    if len(c_treat) < 3 or len(c_base) < 3:
        return {"estimate": float("nan"), "n_treat": len(c_treat),
                "n_base": len(c_base), "p": float("nan"),
                "ci_lo": float("nan"), "ci_hi": float("nan")}
    t, p = stats.ttest_ind(c_treat, c_base, equal_var=False)
    est = c_treat.mean() - c_base.mean()
    se = np.hypot(c_treat.std(ddof=1) / np.sqrt(len(c_treat)),
                  c_base.std(ddof=1) / np.sqrt(len(c_base)))
    dfree = len(c_treat) + len(c_base) - 2
    crit = stats.t.ppf(0.975, dfree)
    return {"estimate": est, "n_treat": len(c_treat), "n_base": len(c_base),
            "se": se, "t": float(t), "p": float(p),
            "ci_lo": est - crit * se, "ci_hi": est + crit * se}


def slope_per_month(doys, values) -> dict:
    """Linear trend of a contrast through the senescence limb, dB per month."""
    x = np.asarray(doys, float); y = np.asarray(values, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4:
        return {"slope": float("nan"), "se": float("nan"), "n": int(ok.sum()),
                "r2": float("nan")}
    r = stats.linregress(x[ok], y[ok])
    return {"slope": r.slope * 30, "se": r.stderr * 30, "n": int(ok.sum()),
            "r2": r.rvalue ** 2}


def tau_squared(est, se) -> float:
    """Between-year variance of the TRUE slopes (DerSimonian-Laird).

    A baseline year's slope is uncertain for two separate reasons: the fit has
    error (se), and genuinely normal years differ from one another. Only the
    second belongs in "is 2026 unusual" -- comparing against the scatter of the
    estimates alone would double-count the fitting error and declare every year
    unusual. tau^2 isolates the real year-to-year component.

    Returns 0 when the observed scatter is no larger than the fitting error
    alone would produce, which is the honest answer, not a floor.
    """
    est = np.asarray(est, float); se = np.asarray(se, float)
    ok = np.isfinite(est) & np.isfinite(se) & (se > 0)
    est, se = est[ok], se[ok]
    k = len(est)
    if k < 2:
        return float("nan")
    w = 1.0 / se ** 2
    fe = float((w * est).sum() / w.sum())
    q = float((w * (est - fe) ** 2).sum())
    c = float(w.sum() - (w ** 2).sum() / w.sum())
    if c <= 0:
        return 0.0
    return max(0.0, (q - (k - 1)) / c)


def pooled_baseline(est, se, tau2: float | None = None) -> dict:
    """Random-effects mean of the baseline years.

    Weighted by 1/(se^2 + tau^2), so a thinly sampled year with a wide interval
    counts for less than a densely sampled one -- which matters here, because
    the baseline years carry between 6 and 15 acquisitions in the limb and
    counting them equally would let the weakest fits dominate.
    """
    est = np.asarray(est, float); se = np.asarray(se, float)
    ok = np.isfinite(est) & np.isfinite(se) & (se > 0)
    est, se = est[ok], se[ok]
    if len(est) == 0:
        return {"mean": float("nan"), "se": float("nan"), "tau": float("nan"),
                "k": 0}
    t2 = tau_squared(est, se) if tau2 is None else tau2
    w = 1.0 / (se ** 2 + t2)
    mean = float((w * est).sum() / w.sum())
    return {"mean": mean, "se": float(np.sqrt(1.0 / w.sum())),
            "tau": float(np.sqrt(t2)), "k": len(est)}


def baseline_z(new_est: float, new_se: float, est, se) -> dict:
    """Where does the drought year sit against the baseline distribution?

    This is a PREDICTION interval, not a confidence interval on the mean. The
    question is not "is 2026 different from the average normal year" but "could
    2026 plausibly BE a normal year", so the interval must include the spread
    of normal years (tau^2) and the new year's own fitting error -- not just the
    uncertainty in where the baseline centre lies.
    """
    pool = pooled_baseline(est, se)
    if pool["k"] < 2 or not np.isfinite(new_est):
        return {"z": float("nan"), "p": float("nan"), "pi_lo": float("nan"),
                "pi_hi": float("nan"), **pool}
    var = pool["tau"] ** 2 + new_se ** 2 + pool["se"] ** 2
    sd = float(np.sqrt(var))
    dfree = max(pool["k"] - 1, 1)
    z = (new_est - pool["mean"]) / sd
    crit = stats.t.ppf(0.975, dfree)
    return {"z": float(z), "p": float(2 * stats.t.sf(abs(z), dfree)),
            "pi_lo": pool["mean"] - crit * sd,
            "pi_hi": pool["mean"] + crit * sd, "sd": sd, **pool}


def loo_calibration(years, est, se) -> list[dict]:
    """Leave-one-out: how extreme does each BASELINE year look?

    The check that keeps this honest. Every baseline year is, by assumption,
    normal -- so testing each against the others says what |z| a normal year
    produces. If the baselines routinely land at 2 sigma, a 2-sigma drought
    year proves nothing and the interval is simply too narrow.
    """
    out = []
    years = list(years); est = list(est); se = list(se)
    for i, y in enumerate(years):
        others_e = est[:i] + est[i + 1:]
        others_s = se[:i] + se[i + 1:]
        r = baseline_z(est[i], se[i], others_e, others_s)
        out.append({"year": y, "slope": est[i], "z": r["z"], "p": r["p"]})
    return out


def level_at_ref(doys, values, ref_doy: float = REF_DOY) -> dict:
    """Contrast LEVEL at a common reference day, from each year's own fit.

    Why this exists (NCR-14). The slope test assumes the limb trajectory is a
    straight line. For the cross-ratio that is roughly true (mean r^2 0.51
    across six years); for sigma0 VV and VH it is not (0.34 and 0.21), because
    those channels follow soil moisture, which is strongly curved through
    autumn. Worse, 2024's limb is sampled over 60 days beginning 20 days later
    than every other year -- the 24-day gap sits across 1 July. Fitting a
    straight line to a SHIFTED window of a CURVED trajectory returns a
    different slope, which is exactly why 2024 came out as the extreme outlier
    in all six VV/VH slope tests and why every one of their calibration checks
    failed.

    Evaluating the fit at a fixed day near every year's mean sampling date
    removes that. At x0 = xbar the prediction reduces to the mean level and its
    error to the standard error of the mean, so the estimate barely depends on
    the regression being correct -- it is a sampling-adjusted mean, not a trend.
    """
    x = np.asarray(doys, float)
    y = np.asarray(values, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(x)
    if n < 4:
        return {"level": float("nan"), "se": float("nan"), "n": n}
    r = stats.linregress(x, y)
    fitted = r.intercept + r.slope * x
    s_resid = float(np.sqrt(((y - fitted) ** 2).sum() / (n - 2)))
    sxx = float(((x - x.mean()) ** 2).sum())
    if sxx <= 0:
        return {"level": float("nan"), "se": float("nan"), "n": n}
    return {"level": float(r.intercept + r.slope * ref_doy),
            "se": s_resid * float(np.sqrt(1 / n + (ref_doy - x.mean()) ** 2 / sxx)),
            "n": n}


def compare_slopes(a: dict, b: dict) -> dict:
    """Is slope a different from slope b?"""
    if not np.isfinite(a["slope"]) or not np.isfinite(b["slope"]):
        return {"delta": float("nan"), "p": float("nan")}
    d = a["slope"] - b["slope"]
    se = np.hypot(a["se"], b["se"])
    dfree = a["n"] + b["n"] - 4
    t = d / se if se > 0 else np.nan
    return {"delta": d, "se": se, "t": float(t), "df": dfree,
            "p": float(2 * stats.t.sf(abs(t), dfree)) if np.isfinite(t) else np.nan}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("proc", type=Path)
    p.add_argument("--aoi", type=Path, required=True)
    p.add_argument("--classes", type=Path, required=True)
    p.add_argument("--areas", type=Path, required=True)
    p.add_argument("--erode", type=int, default=2,
                   help="pixels to shrink each stratum inward (default 2 = 20 m)")
    p.add_argument("--window-from", type=Path,
                   help="JSON written by fetch_met.py. Restricts the test to "
                        "the drought window that file defines. That window is "
                        "derived from soil moisture deficit alone -- rainfall "
                        "and evapotranspiration, no radar -- so narrowing to "
                        "it is legitimate. Narrowing to a window chosen by "
                        "looking at the SAR would not be.")
    p.add_argument("--metric", default="cr_db",
                   choices=("cr_db", "vv_db", "vh_db"),
                   help="observable to contrast. cr_db (default) is the "
                        "cross-ratio; vv_db and vh_db are the single channels. "
                        "The cross-ratio is immune to a gain error common to "
                        "both polarisations -- and therefore BLIND to a drought "
                        "that dims both channels together, which is what "
                        "Van Emmerik et al. (2022) report for several crops. "
                        "Run all three before concluding anything from one.")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--treat-year", type=int, default=2026)
    p.add_argument("--base-year", type=int, default=2025,
                   help="single reference year for the pairwise tests")
    p.add_argument("--base-years", type=int, nargs="+",
                   default=[2021, 2022, 2023, 2024, 2025],
                   help="the baseline distribution the drought year is tested "
                        "against")
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    lo_doy, hi_doy, window_tag = PEAK_DOY, END_DOY, ""
    if args.window_from:
        w = json.loads(args.window_from.read_text())
        if not w.get("start_doy"):
            print(f"{args.window_from} defines no window; using the full limb")
        else:
            lo_doy, hi_doy = int(w["start_doy"]), int(w["end_doy"])
            window_tag = "_window"
            print(f"drought window from {args.window_from.name}:")
            print(f"  {w['start']} to {w['end']}  (DOY {lo_doy}-{hi_doy}, "
                  f"{hi_doy - lo_doy + 1} days)")
            print(f"  rule: {w.get('method', '?')}")
            print(f"  derived from: {w.get('derived_from', '?')}")
            print(f"  frozen on: {w.get('derived_on', '?')}\n")
    else:
        print(f"full senescence limb, DOY {lo_doy}-{hi_doy}\n")

    aoi = load_aoi(args.aoi)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)
    aoi_p = shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi)
    codes = load_codes(args.areas)

    with rasterio.open(args.classes) as src:
        cw = aoi_window(src, aoi_p)
        code_raster = src.read(1, window=cw)
        ct = src.window_transform(cw)
        class_key = grid_key(src.crs, src.transform)
    aoi_mask = ~geometry_mask([aoi_p], out_shape=code_raster.shape,
                              transform=ct, invert=False)

    masks = build_masks(code_raster, codes, STRATA)
    print(f"erosion: {args.erode} px ({10 * args.erode} m)\n")
    print(f"{'stratum':<12}{'raw px':>12}{'eroded px':>12}{'kept':>8}{'km2':>9}")
    print("-" * 53)
    for name in STRATA:
        raw = int((masks[name] & aoi_mask).sum())
        masks[name] = erode(masks[name], args.erode) & aoi_mask
        n = int(masks[name].sum())
        print(f"{name:<12}{raw:>12,}{n:>12,}"
              f"{100 * n / raw if raw else 0:>7.1f}%{n / 1e4:>9.1f}")
        if n < MIN_PX:
            print(f"  WARNING: {name} has {n:,} px after erosion, below the "
                  f"{MIN_PX:,} floor")

    stems = sorted(f.stem for f in args.proc.glob("*.dim"))
    print(f"\nreading {len(stems)} scenes...")
    rows = []
    for i, stem in enumerate(stems, 1):
        try:
            d, plat = parse_stem(stem)
            files = band_files(data_dir(args.proc / f"{stem}.dim"))
            with rasterio.open(files["Sigma0_VV"]) as src:
                if grid_key(src.crs, src.transform) != class_key:
                    print(f"  {stem}: lattice differs from the class raster; "
                          f"skipped")
                    continue
                w = aoi_window(src, aoi_p)
                vv = src.read(1, window=w).astype("float64")
            with rasterio.open(files["Sigma0_VH"]) as src:
                vh = src.read(1, window=w).astype("float64")
        except (ValueError, SystemExit, KeyError, rasterio.RasterioIOError) as e:
            print(f"  {stem}: {e}")
            continue
        if vv.shape != code_raster.shape:
            print(f"  {stem}: window {vv.shape} != class {code_raster.shape}; "
                  f"skipped")
            continue
        per = {n: stratum_stats(vv, vh, m) for n, m in masks.items()}
        row = {"date": d.isoformat(), "year": d.year,
               "doy": d.timetuple().tm_yday, "platform": plat}
        for n, s in per.items():
            for m in ("cr_db", "vv_db", "vh_db"):
                row[f"{n}_{m}"] = s[m] if s else float("nan")
            row[f"{n}_n_px"] = s["n_px"] if s else 0
        for a, b in CONTRASTS:
            row[f"{a}_minus_{b}"] = contrast(per[a], per[b], args.metric)
        rows.append(row)
        if i % 10 == 0 or i == len(stems):
            print(f"  {i}/{len(stems)}", end="\r", flush=True)
    print(f"  {len(rows)} scenes used          ")

    # Outputs are named by metric so a VV run cannot silently overwrite the
    # cross-ratio results sitting beside it. cr_db keeps the original names.
    tag = ("" if args.metric == "cr_db"
           else "_" + args.metric.replace("_db", "")) + window_tag
    series = args.out / f"strata_series{tag}.csv"
    with series.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: r["date"]))
    print(f"wrote {series}")

    def limb(year, key):
        sel = [r for r in rows if r["year"] == year
               and lo_doy <= r["doy"] <= hi_doy and np.isfinite(r[key])]
        return ([r["doy"] for r in sel], [r[key] for r in sel])

    out_rows = []
    years_present = sorted({r["year"] for r in rows})
    base_years = [y for y in args.base_years if y in years_present]

    if len(base_years) >= 3:
        print(f"\n{'=' * 70}\nPRIMARY -- {args.treat_year} against the "
              f"{len(base_years)}-year baseline distribution\n"
              f"observable: {METRIC_NAME[args.metric]}\n"
              f"senescence slope, 1 Jul to 30 Sep, dB per month\n{'=' * 70}")
        for a, b in CONTRASTS:
            key = f"{a}_minus_{b}"
            fits = {y: slope_per_month(*limb(y, key))
                    for y in base_years + [args.treat_year]}
            bse = [fits[y] for y in base_years if np.isfinite(fits[y]["slope"])]
            if len(bse) < 3 or not np.isfinite(fits[args.treat_year]["slope"]):
                print(f"\n({a} - {b}): too few usable years")
                continue
            yrs = [y for y in base_years if np.isfinite(fits[y]["slope"])]
            est = [fits[y]["slope"] for y in yrs]
            ses = [fits[y]["se"] for y in yrs]
            t = fits[args.treat_year]

            print(f"\n({a} - {b}):")
            for y in yrs:
                print(f"    {y}  {fits[y]['slope']:+7.3f} +/- "
                      f"{fits[y]['se']:.3f}   (n={fits[y]['n']:>2}, "
                      f"r2={fits[y]['r2']:.2f})")
            r = baseline_z(t["slope"], t["se"], est, ses)
            print(f"    {'-' * 54}")
            print(f"    baseline mean {r['mean']:+.3f}, between-year sd "
                  f"{r['tau']:.3f}  (k={r['k']})")
            print(f"    95% prediction interval for a normal year: "
                  f"[{r['pi_lo']:+.3f}, {r['pi_hi']:+.3f}]")
            print(f"    {args.treat_year}  {t['slope']:+7.3f} +/- "
                  f"{t['se']:.3f}   (n={t['n']})")
            verdict = ("OUTSIDE the interval" if not
                       (r["pi_lo"] <= t["slope"] <= r["pi_hi"])
                       else "inside the interval")
            print(f"    z = {r['z']:+.2f}, p = {r['p']:.4f}   -> {verdict}")

            cal = loo_calibration(yrs, est, ses)
            worst = max((c for c in cal if np.isfinite(c["z"])),
                        key=lambda c: abs(c["z"]), default=None)
            if worst:
                print(f"    calibration: the most extreme BASELINE year is "
                      f"{worst['year']} at z = {worst['z']:+.2f}")
                if abs(worst["z"]) >= abs(r["z"]):
                    print(f"      -> a year assumed normal is as extreme as "
                          f"{args.treat_year}. This interval is too narrow to\n"
                          f"         call {args.treat_year} unusual.")
            out_rows.append({"test": "baseline_z", "contrast": key,
                             "estimate": t["slope"] - r["mean"], "p": r["p"],
                             "ci_lo": r["pi_lo"], "ci_hi": r["pi_hi"],
                             "n_treat": t["n"], "n_base": r["k"]})

    # --- level at a common reference day -----------------------------------
    if len(base_years) >= 3:
        print(f"\n{'=' * 70}\nPRIMARY (level) -- {args.treat_year} against the "
              f"{len(base_years)}-year baseline\n"
              f"observable: {METRIC_NAME[args.metric]}, contrast level on "
              f"day {REF_DOY}\n"
              f"Robust to how each year's limb was sampled, unlike the slope "
              f"(see NCR-14).\n{'=' * 70}")
        for a, b in CONTRASTS:
            key = f"{a}_minus_{b}"
            lv = {y: level_at_ref(*limb(y, key)) for y in base_years + [args.treat_year]}
            yrs = [y for y in base_years if np.isfinite(lv[y]["level"])]
            if len(yrs) < 3 or not np.isfinite(lv[args.treat_year]["level"]):
                continue
            t = lv[args.treat_year]
            r = baseline_z(t["level"], t["se"], [lv[y]["level"] for y in yrs],
                           [lv[y]["se"] for y in yrs])
            print(f"\n({a} - {b}):")
            print("    " + "  ".join(f"{y} {lv[y]['level']:+.3f}" for y in yrs))
            print(f"    baseline {r['mean']:+.3f}  between-year sd {r['tau']:.3f}"
                  f"   95% interval [{r['pi_lo']:+.3f}, {r['pi_hi']:+.3f}]")
            inside = r["pi_lo"] <= t["level"] <= r["pi_hi"]
            print(f"    {args.treat_year} {t['level']:+.3f} +/- {t['se']:.3f}"
                  f"   z = {r['z']:+.2f}, p = {r['p']:.4f}"
                  f"   -> {'inside' if inside else 'OUTSIDE'}")
            cal = loo_calibration(yrs, [lv[y]["level"] for y in yrs],
                                  [lv[y]["se"] for y in yrs])
            worst = max((c for c in cal if np.isfinite(c["z"])),
                        key=lambda c: abs(c["z"]), default=None)
            if worst:
                print(f"    calibration: worst baseline year {worst['year']} "
                      f"at z = {worst['z']:+.2f}")
                # Same guard the slope block carries. Omitting it here was an
                # oversight: a level test whose baseline years scatter further
                # than the drought year has no discriminating power either, and
                # the reader must be told so in both places or not at all.
                if abs(worst["z"]) >= abs(r["z"]):
                    print(f"      -> {worst['year']}, a year assumed normal, "
                          f"sits FURTHER from the baseline than "
                          f"{args.treat_year} does.\n"
                          f"         {args.treat_year} is unremarkable against "
                          f"ordinary year-to-year scatter.")
            out_rows.append({"test": "baseline_level", "contrast": key,
                             "estimate": t["level"] - r["mean"], "p": r["p"],
                             "ci_lo": r["pi_lo"], "ci_hi": r["pi_hi"],
                             "n_treat": t["n"], "n_base": r["k"]})

    print(f"\n{'=' * 70}\nSUPPORTING -- pairwise slope, "
          f"{args.treat_year} vs {args.base_year}\n{'=' * 70}")
    for a, b in CONTRASTS:
        key = f"{a}_minus_{b}"
        print(f"\n({a} - {b}) cross-ratio, dB per month:")
        sl = {}
        for y in sorted({r["year"] for r in rows}):
            sl[y] = slope_per_month(*limb(y, key))
            if np.isfinite(sl[y]["slope"]):
                print(f"  {y}: {sl[y]['slope']:+7.3f}  "
                      f"+/- {sl[y]['se']:.3f}  (n={sl[y]['n']}, "
                      f"r2={sl[y]['r2']:.2f})")
        if args.treat_year in sl and args.base_year in sl:
            c = compare_slopes(sl[args.treat_year], sl[args.base_year])
            print(f"  {args.treat_year} minus {args.base_year}: "
                  f"{c['delta']:+.3f} dB/month, p = {c['p']:.4f}"
                  + ("   <-- significant at 0.05" if c["p"] < 0.05 else ""))
            out_rows.append({"test": "slope", "contrast": key,
                             "estimate": c["delta"], "p": c["p"],
                             "ci_lo": "", "ci_hi": "",
                             "n_treat": sl[args.treat_year]["n"],
                             "n_base": sl[args.base_year]["n"]})

    print(f"\n{'=' * 70}\nSECONDARY -- level difference-in-differences, "
          f"1 Jul to 30 Sep\n{'=' * 70}")
    for a, b in CONTRASTS:
        key = f"{a}_minus_{b}"
        t = [r[key] for r in rows if r["year"] == args.treat_year
             and PEAK_DOY <= r["doy"] <= END_DOY]
        bl = [r[key] for r in rows if r["year"] == args.base_year
              and PEAK_DOY <= r["doy"] <= END_DOY]
        d = did(t, bl)
        if not np.isfinite(d["estimate"]):
            print(f"({a} - {b}): too few acquisitions")
            continue
        print(f"({a} - {b}): {d['estimate']:+.3f} dB  "
              f"[95% CI {d['ci_lo']:+.3f}, {d['ci_hi']:+.3f}]  "
              f"p = {d['p']:.4f}" + ("   <-- significant" if d["p"] < 0.05 else ""))
        out_rows.append({"test": "did_level", "contrast": key,
                         "estimate": d["estimate"], "p": d["p"],
                         "ci_lo": d["ci_lo"], "ci_hi": d["ci_hi"],
                         "n_treat": d["n_treat"], "n_base": d["n_base"]})

    res = args.out / f"did_results{tag}.csv"
    with res.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["test", "contrast", "estimate", "p",
                                           "ci_lo", "ci_hi", "n_treat",
                                           "n_base"])
        w.writeheader(); w.writerows(out_rows)
    print(f"\nwrote {res}")

    print("\nSix tests here: three contrasts x two tests. The primary slope "
          "test on\n(grassland - forest) was stated in advance and stands "
          "alone; the rest are\nsupporting, and a p just under 0.05 among them "
          "is not a discovery.\nA real effect should show as grassland and "
          "tillage moving together\nagainst forest, with dry grassland moving "
          "further than wet. One lone\nsignificant cell with the others flat "
          "is noise wearing a result's clothes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
