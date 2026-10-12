#!/usr/bin/env python3
"""Collapse the processed stack into one row per acquisition (REQ-18).

This is where the project stops being plumbing and starts being science. Every
line of code before this one existed to make 82 rasters trustworthy; this one
asks whether the drought is actually in them.

What it produces
----------------
One CSV row per acquisition: AOI-mean sigma0 in both polarisations, the
cross-ratio, dual-pol RVI, distribution percentiles, incidence angle, and the
valid-pixel fraction. Everything is averaged in LINEAR POWER and converted to
dB once at the end (REQ-06) -- averaging dB gives the wrong mean, and the error
is invisible once made.

The precondition it enforces
----------------------------
Before computing anything it checks that all scenes share one pixel lattice.
A "stack" whose members sit on different grids is not a stack, and every
per-pixel operation downstream would silently resample. NCR-12 was exactly
this, caught on four scenes; this is the same check at full scale. If it
fails, nothing is written -- a half-built series is worse than none, because
it looks finished.

What it deliberately does NOT do
--------------------------------
No land-cover stratification. The National Land Cover Map is not fetched yet,
so this is the whole-AOI aggregate: grassland, tillage, forest, bog and town
averaged together. That dilutes the signal -- bog and forest barely respond to
drought and will drag the mean toward no-change. Read a NULL result here as
"not visible in the aggregate", never as "not there".

Usage
-----
    python build_series.py C:\\sar\\proc --aoi aoi_oakpark.geojson \\
        --csv ../results/phase2/series.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.ops import transform as shp_transform

from crosscal import parse_stem, to_db
from verify_scene import band_files, data_dir, load_aoi

PIXEL_M = 10.0
BANDS = ("Sigma0_VV", "Sigma0_VH", "projectedLocalIncidenceAngle")
MIN_VALID_FRACTION = 0.99      # below this the acquisition is flagged, not used


def grid_key(crs, transform, px: float = PIXEL_M) -> tuple:
    """Identity of the pixel lattice a raster sits on.

    Two rasters sharing this key align on integer pixel offsets, so a window
    read from each addresses the same ground. Differing keys mean resampling
    is required, which for sigma0 is a lossy operation nobody should perform
    82 times by accident.

    Origins are reduced modulo the pixel size: absolute extent differs between
    scenes (footprints differ) and that is fine. Only the phase matters.
    """
    return (str(crs),
            round(abs(transform.a), 4),
            round(abs(transform.e), 4),
            round(transform.c % px, 3),
            round(abs(transform.f) % px, 3))


def stack_problems(keys: dict[str, tuple]) -> list[str]:
    """Complaints about a set of {stem: grid_key}. Empty means stackable."""
    if not keys:
        return ["no scenes found"]
    counts: dict[tuple, list[str]] = {}
    for stem, k in keys.items():
        counts.setdefault(k, []).append(stem)
    if len(counts) == 1:
        return []
    # Name the minority grids: with alignToStandardGrid left false on a few
    # scenes, the odd ones out are the ones reprocessed with the wrong graph.
    groups = sorted(counts.items(), key=lambda kv: -len(kv[1]))
    out = [f"{len(groups)} different pixel lattices in this stack:"]
    for k, stems in groups:
        shown = ", ".join(sorted(stems)[:4])
        more = f" (+{len(stems) - 4} more)" if len(stems) > 4 else ""
        out.append(f"  {len(stems):>3} scene(s) on grid {k}: {shown}{more}")
    return out


def rvi(vv: float, vh: float) -> float:
    """Dual-pol Radar Vegetation Index, 4*VH / (VV + VH), linear power.

    Rises with volume scattering, so denser canopy means higher RVI. Insensitive
    to a gain error common to both channels for the same reason the cross-ratio
    is -- a shared factor cancels top and bottom.
    """
    denom = vv + vh
    if not np.isfinite(denom) or denom <= 0:
        return float("nan")
    return 4.0 * vh / denom


def cross_ratio_db(vv: float, vh: float) -> float:
    """VH - VV in dB. The drought metric: both the measurement with the
    smallest inter-platform term (0.011 dB agreement, REQ-09) and the one most
    directly tied to canopy structure rather than soil moisture."""
    if vv <= 0 or vh <= 0:
        return float("nan")
    return to_db(vh) - to_db(vv)


def pctiles(v: np.ndarray) -> dict:
    if v.size == 0:
        return {k: float("nan") for k in ("p05", "p25", "median", "p75", "p95")}
    q = np.percentile(v, [5, 25, 50, 75, 95])
    return dict(zip(("p05", "p25", "median", "p75", "p95"), map(float, q)))


def aoi_stats(vv: np.ndarray, vh: np.ndarray, inc: np.ndarray,
              mask: np.ndarray) -> dict:
    """Everything the series needs from one acquisition.

    Validity is decided jointly: a pixel counts only where BOTH polarisations
    carry data, so the VV and VH means are over the identical pixel set and
    their ratio is a ratio of like for like. Computing them over different
    masks would put a spurious term straight into the cross-ratio, which is
    the one number this project most needs to be clean.
    """
    valid = (mask & np.isfinite(vv) & np.isfinite(vh)
             & (vv != 0.0) & (vh != 0.0))
    n_aoi = int(mask.sum())
    n = int(valid.sum())
    out = {
        "n_px_aoi": n_aoi,
        "n_px_valid": n,
        "valid_fraction": n / n_aoi if n_aoi else 0.0,
    }
    if n == 0:
        return out | {k: float("nan") for k in (
            "sigma0_vv_lin", "sigma0_vh_lin", "sigma0_vv_db", "sigma0_vh_db",
            "cross_ratio_db", "rvi", "incidence_deg", "neg_fraction_vh",
            *(f"vv_{p}_db" for p in ("p05", "p25", "median", "p75", "p95")),
            *(f"vh_{p}_db" for p in ("p05", "p25", "median", "p75", "p95")))}

    a, b = vv[valid], vh[valid]
    mean_vv, mean_vh = float(a.mean()), float(b.mean())
    out |= {
        "sigma0_vv_lin": mean_vv,
        "sigma0_vh_lin": mean_vh,
        "sigma0_vv_db": to_db(mean_vv),
        "sigma0_vh_db": to_db(mean_vh),
        "cross_ratio_db": cross_ratio_db(mean_vv, mean_vh),
        "rvi": rvi(mean_vv, mean_vh),
        "incidence_deg": float(inc[valid].mean()),
        # Tracked per acquisition rather than assumed constant: the negative
        # fraction is a proxy for how close VH sits to the noise floor, and a
        # scene where it jumps is a scene to look at before trusting its mean.
        "neg_fraction_vh": float((b < 0).sum()) / n,
    }
    for prefix, arr in (("vv", a), ("vh", b)):
        for k, v in pctiles(arr[arr > 0]).items():
            out[f"{prefix}_{k}_db"] = to_db(v)
    return out


def read_windowed(proc: Path, stem: str, aoi_p):
    """Read the three bands over the AOI window only.

    The AOI is roughly a third of each raster; reading the rest to average a
    third of it would triple the I/O for nothing. 82 scenes makes that the
    difference between a coffee and a lunch.
    """
    d = data_dir(proc / f"{stem}.dim")
    files = band_files(d)
    missing = [b for b in BANDS if b not in files]
    if missing:
        raise ValueError(f"missing band(s): {', '.join(missing)}")

    with rasterio.open(files["Sigma0_VV"]) as src:
        win = from_bounds(*aoi_p.bounds, transform=src.transform)
        win = win.round_offsets().round_lengths()
        win = win.intersection(
            rasterio.windows.Window(0, 0, src.width, src.height))
        wt = src.window_transform(win)
        key = grid_key(src.crs, src.transform)

    arrs = {}
    for name in BANDS:
        with rasterio.open(files[name]) as src:
            arrs[name] = src.read(1, window=win).astype("float64")

    mask = ~geometry_mask([aoi_p], out_shape=arrs[BANDS[0]].shape,
                          transform=wt, invert=False)
    return arrs, mask, key


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("proc", type=Path)
    p.add_argument("--aoi", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--skip-grid-check", action="store_true",
                   help="proceed despite mixed lattices (records it in the CSV)")
    args = p.parse_args(argv)

    stems = sorted(f.stem for f in args.proc.glob("*.dim"))
    if not stems:
        print(f"no .dim products in {args.proc}")
        return 1
    print(f"found {len(stems)} products in {args.proc}")

    aoi = load_aoi(args.aoi)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)
    aoi_p = shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi)

    rows, keys, failures = [], {}, []
    for i, stem in enumerate(stems, 1):
        try:
            d, plat = parse_stem(stem)
            arrs, mask, key = read_windowed(args.proc, stem, aoi_p)
        except (ValueError, SystemExit, rasterio.RasterioIOError) as exc:
            failures.append((stem, str(exc)))
            print(f"[{i:>3}/{len(stems)}] {stem}  FAILED: {exc}")
            continue
        keys[stem] = key
        s = aoi_stats(arrs["Sigma0_VV"], arrs["Sigma0_VH"],
                      arrs["projectedLocalIncidenceAngle"], mask)
        rows.append({"date": d.isoformat(), "year": d.year,
                     "doy": d.timetuple().tm_yday, "platform": plat,
                     "stem": stem, **s})
        flag = "" if s["valid_fraction"] >= MIN_VALID_FRACTION else "  <-- LOW COVERAGE"
        print(f"[{i:>3}/{len(stems)}] {stem}  "
              f"VV {s['sigma0_vv_db']:+6.2f}  VH {s['sigma0_vh_db']:+6.2f}  "
              f"CR {s['cross_ratio_db']:+6.2f} dB  "
              f"valid {100 * s['valid_fraction']:5.1f}%{flag}")

    # --- the precondition ---------------------------------------------------
    problems = stack_problems(keys)
    print()
    if problems:
        for line in problems:
            print(line)
        if not args.skip_grid_check:
            print("\nNothing written. These scenes are not one stack: per-pixel\n"
                  "work across them would resample silently. Reprocess the\n"
                  "minority grids with graph v3, or pass --skip-grid-check if\n"
                  "you only want the AOI aggregates, which do not depend on it.")
            return 1
        print("\nproceeding anyway (--skip-grid-check): AOI aggregates are\n"
              "unaffected, but do NOT build per-pixel products from this set.")
    else:
        print(f"grid: all {len(keys)} scenes share one lattice {next(iter(keys.values()))}")

    low = [r for r in rows if r["valid_fraction"] < MIN_VALID_FRACTION]
    if low:
        print(f"\n{len(low)} acquisition(s) below {100 * MIN_VALID_FRACTION:.0f}% "
              f"AOI coverage: {', '.join(r['stem'] for r in low)}")
        print("Kept in the CSV with their coverage recorded. Decide explicitly\n"
              "whether they enter the analysis; do not let them in by default.")
    if failures:
        print(f"\n{len(failures)} product(s) could not be read:")
        for stem, why in failures:
            print(f"  {stem}: {why}")

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["date"]))
    print(f"\nwrote {args.csv}  ({len(rows)} acquisitions)")

    # --- the first look -----------------------------------------------------
    print("\nmean cross-ratio by year, July-August (the drought window):")
    for yr in sorted({r["year"] for r in rows}):
        sel = [r["cross_ratio_db"] for r in rows
               if r["year"] == yr and 182 <= r["doy"] <= 243
               and np.isfinite(r["cross_ratio_db"])]
        if sel:
            print(f"  {yr}:  {np.mean(sel):+6.3f} dB   (n={len(sel)})")
    print("\nThis is the whole-AOI aggregate across all land cover. Treat it as\n"
          "a smoke test, not a result -- the stratified series is the analysis.")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
