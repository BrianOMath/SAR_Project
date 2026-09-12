#!/usr/bin/env python3
"""Verify one terrain-corrected Sentinel-1 scene before trusting the pipeline.
 
Phase 1 of the SAR drought project. Checks the things that fail SILENTLY --
a chain that runs clean and produces the wrong thing has already happened
three times on this project (see the plan's nonconformance log).
 
Checks
------
  bands       all three expected bands present (REQ: VV, VH, incidence angle)
  crs         EPSG:2157, 10 m pixels, north-up
  extent      the AOI is inside the raster AND inside the valid-data mask
              (these are different things: a terrain-corrected subset is a
              rotated quadrilateral inside a north-up bounding box, so a
              bounds check alone can pass while part of the AOI has no data)
  values      sigma0 in linear power, in a physically plausible range
  linearity   data is NOT already in dB (REQ-06 -- averaging dB is wrong)
  negatives   counted, not hidden (clipNegativeValues is off by design)
  incidence   reported at the AOI centroid -- the REQ-09 datum per platform
 
Usage
-----
    python verify_scene.py C:\\sar\\proc\\20260717_S1D.dim --aoi aoi_oakpark.geojson
    python verify_scene.py C:\\sar\\proc\\20260717_S1D.data --aoi aoi_oakpark.geojson
 
Exit code 0 if every hard check passes, 1 otherwise, so it can gate a batch.
"""
 
from __future__ import annotations
 
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
 
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
 
EXPECTED_CRS = "EPSG:2157"
EXPECTED_PIXEL_M = 10.0
EXPECTED_BANDS = ("Sigma0_VV", "Sigma0_VH", "projectedLocalIncidenceAngle")
 
# Physically plausible ranges over Irish farmland, linear power.
# Wide on purpose: these catch "wrong by an order of magnitude", not fine detail.
PLAUSIBLE = {
    "Sigma0_VV": (0.005, 1.0),      # roughly -23 .. 0 dB
    "Sigma0_VH": (0.0005, 0.3),     # roughly -33 .. -5 dB
    "projectedLocalIncidenceAngle": (15.0, 60.0),   # IW spans ~29-46 deg
}
 
 
@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    hard: bool = True
 
 
def data_dir(path: Path) -> Path:
    """Accept either the .dim header or the .data directory."""
    if path.is_dir():
        return path
    if path.suffix.lower() == ".dim":
        d = path.with_suffix(".data")
        if not d.is_dir():
            raise SystemExit(f"no .data directory beside {path}")
        return d
    raise SystemExit(f"expected a .dim file or .data directory, got {path}")
 
 
def band_files(d: Path) -> dict[str, Path]:
    return {p.stem: p for p in sorted(d.glob("*.img"))}
 
 
def load_aoi(path: Path):
    data = json.loads(path.read_text())
    feats = data["features"] if data.get("type") == "FeatureCollection" else [data]
    for f in feats:
        geom = f.get("geometry", f)
        if geom.get("type") == "Polygon":
            return shape(geom)
    raise SystemExit(f"no polygon in {path}")
 
 
def to_db(x: float) -> float:
    return 10.0 * np.log10(x) if x > 0 else float("nan")
 
 
def stats(arr: np.ndarray, where: np.ndarray | None = None) -> dict:
    """Stats over valid pixels, optionally restricted to a mask.
 
    SNAP writes exact 0.0 as no-data after terrain correction, so zeros are
    excluded -- leaving them in drags every mean toward zero.
    """
    if where is not None:
        arr = arr[where]
    finite = np.isfinite(arr)
    valid = finite & (arr != 0.0)
    v = arr[valid]
    return {
        "n_total": arr.size,
        "n_valid": int(valid.sum()),
        "n_zero": int((finite & (arr == 0.0)).sum()),
        "n_nan": int((~finite).sum()),
        "n_negative": int((v < 0).sum()) if v.size else 0,
        "min": float(v.min()) if v.size else float("nan"),
        "p05": float(np.percentile(v, 5)) if v.size else float("nan"),
        "median": float(np.median(v)) if v.size else float("nan"),
        "mean": float(v.mean()) if v.size else float("nan"),
        "p95": float(np.percentile(v, 95)) if v.size else float("nan"),
        "max": float(v.max()) if v.size else float("nan"),
    }
 
 
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("scene", type=Path, help=".dim file or .data directory")
    p.add_argument("--aoi", type=Path, required=True, help="AOI GeoJSON (WGS84)")
    args = p.parse_args(argv)
 
    d = data_dir(args.scene)
    found = band_files(d)
    checks: list[Check] = []
 
    print(f"scene : {d}")
    print(f"bands : {', '.join(found) or '(none)'}\n")
 
    # --- bands present -----------------------------------------------------
    missing = [b for b in EXPECTED_BANDS if b not in found]
    checks.append(Check(
        "bands present", not missing,
        "all three found" if not missing else f"MISSING {', '.join(missing)}"))
 
    if "Sigma0_VV" not in found:
        print("Sigma0_VV is absent -- the polarisation setting did not take. "
              "Fix that before reading anything else.\n")
 
    if not found:
        print("no .img bands at all; nothing to check")
        return 1
 
    ref = rasterio.open(next(iter(found.values())))
 
    # --- CRS and grid ------------------------------------------------------
    crs_ok = ref.crs is not None and ref.crs == CRS.from_string(EXPECTED_CRS)
    checks.append(Check("CRS", crs_ok,
                        f"{ref.crs.to_string() if ref.crs else 'none'} "
                        f"(want {EXPECTED_CRS})"))
 
    px, py = abs(ref.transform.a), abs(ref.transform.e)
    px_ok = abs(px - EXPECTED_PIXEL_M) < 0.01 and abs(py - EXPECTED_PIXEL_M) < 0.01
    checks.append(Check("pixel size", px_ok, f"{px:.3f} x {py:.3f} m"))
 
    north_up = ref.transform.b == 0 and ref.transform.d == 0 and ref.transform.e < 0
    checks.append(Check("north-up grid", north_up, f"{ref.width} x {ref.height} px"))
 
    # --- AOI containment ---------------------------------------------------
    aoi = load_aoi(args.aoi)
    tf = Transformer.from_crs("EPSG:4326", ref.crs.to_string(), always_xy=True)
    aoi_p = shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi)
    l, b, r, t = ref.bounds
    ax0, ay0, ax1, ay1 = aoi_p.bounds
    margins = [ax0 - l, ay0 - b, r - ax1, t - ay1]
    contained = min(margins) > 0
    checks.append(Check(
        "AOI inside raster bounds", contained,
        f"margins W/S/E/N = {', '.join(f'{m/1000:.1f}' for m in margins)} km"))
 
    # Bounds containment is NOT coverage. The terrain-corrected valid region is
    # a rotated quadrilateral inside a north-up bounding box, so the AOI can sit
    # comfortably inside the raster while part of it has no backscatter at all.
    aoi_mask = ~geometry_mask([aoi_p], out_shape=(ref.height, ref.width),
                              transform=ref.transform, invert=False)
    n_aoi = int(aoi_mask.sum())
    # px*py is m2 per pixel; /1e6 gives km2. (Was 1e-4, which over-reported
    # the AOI by 100x -- the mask was right, the printed unit was not.)
    print(f"AOI covers {n_aoi:,} pixels ({n_aoi * px * py / 1e6:,.0f} km2)\n")
 
    # --- per-band values ---------------------------------------------------
    print(f"{'band':<32}{'scene%':>8}{'AOI%':>8}{'median':>12}{'mean':>12}"
          f"{'p05':>12}{'p95':>12}{'neg':>10}")
    print("-" * 106)
 
    band_stats = {}       # over the AOI -- what the analysis actually uses
    scene_stats = {}      # over the whole raster, for context
    for name, path in found.items():
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float64")
        sc = stats(arr)
        s = stats(arr, where=aoi_mask)
        band_stats[name] = s
        scene_stats[name] = sc
        scene_pct = 100.0 * sc["n_valid"] / sc["n_total"] if sc["n_total"] else 0
        aoi_pct = 100.0 * s["n_valid"] / s["n_total"] if s["n_total"] else 0
        print(f"{name:<32}{scene_pct:>7.1f}%{aoi_pct:>7.1f}%"
              f"{s['median']:>12.5g}{s['mean']:>12.5g}"
              f"{s['p05']:>12.5g}{s['p95']:>12.5g}{s['n_negative']:>10}")
 
        lo, hi = PLAUSIBLE.get(name, (-np.inf, np.inf))
        in_range = lo <= s["median"] <= hi
        checks.append(Check(f"{name} plausible", in_range,
                            f"AOI median {s['median']:.5g}, expected {lo}..{hi}"))
 
        # The check that a bounds test cannot make.
        if name in ("Sigma0_VV", "Sigma0_VH", "projectedLocalIncidenceAngle"):
            checks.append(Check(
                f"{name} covers the AOI", aoi_pct >= 99.0,
                f"{aoi_pct:.2f}% of AOI pixels carry data"
                + ("" if aoi_pct >= 99.0 else "  <-- HOLE IN THE AOI")))
 
    print()
 
    # --- linear, not dB (REQ-06) -------------------------------------------
    for name in ("Sigma0_VV", "Sigma0_VH"):
        s = band_stats.get(name)
        if not s:
            continue
        looks_db = s["median"] < 0 or s["p95"] < 0
        checks.append(Check(
            f"{name} is linear power", not looks_db,
            "median > 0, consistent with linear power" if not looks_db
            else "NEGATIVE MEDIAN -- this looks like dB. Averaging dB is wrong."))
        if s["n_negative"]:
            frac = 100.0 * s["n_negative"] / max(s["n_valid"], 1)
            checks.append(Check(
                f"{name} negatives", frac < 5.0,
                f"{s['n_negative']} px ({frac:.2f}%) below zero after noise "
                f"removal -- expected, clipping is off by design; "
                f"decide how the analysis handles them",
                hard=False))
 
    # --- dB summary, for eyeballing against the literature ------------------
    for name in ("Sigma0_VV", "Sigma0_VH"):
        s = band_stats.get(name)
        if s and s["median"] > 0:
            print(f"{name:<32} median {to_db(s['median']):+7.2f} dB   "
                  f"p05 {to_db(max(s['p05'], 1e-12)):+7.2f} dB   "
                  f"p95 {to_db(s['p95']):+7.2f} dB")
 
    # --- incidence angle at the AOI centroid (the REQ-09 datum) -------------
    inc = "projectedLocalIncidenceAngle"
    if inc in found:
        c = aoi_p.centroid
        with rasterio.open(found[inc]) as src:
            try:
                val = float(next(src.sample([(c.x, c.y)]))[0])
            except (StopIteration, IndexError):
                val = float("nan")
        s = band_stats[inc]          # AOI-restricted (was whole-raster: wrong label)
        sc = scene_stats[inc]
        spread = s["p95"] - s["p05"]
        print(f"\nincidence angle at Oak Park : {val:.2f} deg")
        print(f"across the AOI              : {s['p05']:.2f} .. {s['p95']:.2f} deg "
              f"(median {s['median']:.2f}, p05-p95 spread {spread:.2f} deg)")
        print(f"across the whole scene      : {sc['p05']:.2f} .. {sc['p95']:.2f} deg")
        print("record this per platform (S1A / S1C / S1D) for REQ-09")
        if spread > 6.0:
            print(f"NOTE: {spread:.1f} deg of incidence variation across the AOI is "
                  f"~{0.15 * spread:.1f} dB of purely geometric backscatter\n"
                  f"      variation. Harmless between dates on one orbit, but the\n"
                  f"      grassland and arable samples must span the same incidence\n"
                  f"      distribution in every season or the class comparison\n"
                  f"      inherits a geometry term.")
 
    # --- verdict -----------------------------------------------------------
    print("\n" + "=" * 60)
    hard_fail = [c for c in checks if c.hard and not c.ok]
    for c in checks:
        mark = "PASS" if c.ok else ("FAIL" if c.hard else "NOTE")
        print(f"  [{mark}] {c.name:<34} {c.detail}")
    print("=" * 60)
 
    if hard_fail:
        print(f"\n{len(hard_fail)} hard check(s) failed. Do not scale this "
              f"pipeline until they pass.")
        return 1
    print("\nAll hard checks passed. Record the runtime and the incidence "
          "angle, then this scene is your reference for the batch.")
    return 0
 
 
if __name__ == "__main__":
    raise SystemExit(main())
 