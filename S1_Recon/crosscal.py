#!/usr/bin/env python3
"""Inter-platform cross-calibration from consecutive-day pairs (REQ-09).

Sentinel-1A terminated on 29 June 2026, so the 2024-2026 time series is not
one instrument -- it is S1A, then S1C and S1D interleaved on the same relative
orbit. If their absolute calibration differs by more than a few tenths of a dB,
that step lands in the middle of the drought season and masquerades as signal.

The design
----------
Relative orbit 1 offers two consecutive-day, different-platform pairs:

    2026-04-23 S1C  /  2026-04-24 S1D
    2026-06-28 S1A  /  2026-06-29 S1C   (S1A's last pass on this orbit)

Both pairs share S1C, so the two measurements triangulate: S1D-S1C from April
and S1A-S1C from June, referenced to a common platform.

What this measures, honestly
----------------------------
One day of real geophysical change sits inside every number here. Rain between
the two overpasses moves soil moisture and therefore sigma0, in the same
direction for both polarisations and by considerably more than any plausible
calibration difference. So a LARGE offset proves nothing on its own -- check
the Oak Park rainfall for those dates before concluding anything. A SMALL
offset in both pairs is the useful result: it bounds the calibration step at
a level below the signal, which is all REQ-09 actually needs.

Linear, not dB
--------------
Calibration error is a multiplicative gain on POWER. So the offset that matters
is the ratio of AOI mean linear sigma0, converted to dB once at the end
(REQ-06). Negative pixels are KEPT in that mean: after thermal noise removal
the noise-subtracted power is unbiased but noisy, and discarding the negative
tail biases every mean upward. The per-pixel median ratio is reported beside
it as a robustness check -- it can only use strictly positive pixels, so the
two answering alike is evidence neither is being driven by the tail.

Usage
-----
    python crosscal.py C:\\sar\\proc --aoi aoi_oakpark.geojson
    python crosscal.py C:\\sar\\proc --aoi aoi_oakpark.geojson --csv crosscal.csv

Exit 0 if every pair was measured, 1 if a pair could not be formed or read.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from pyproj import Transformer
from shapely.ops import transform as shp_transform

from verify_scene import band_files, data_dir, load_aoi

PIXEL_M = 10.0
STEM_RE = re.compile(r"^(\d{8})_(S1[ABCD])$")

# Two pairs, both within a day, both crossing platforms. Frozen here rather
# than discovered, because "any two scenes a day apart" would silently pick up
# a pair from the same platform, which measures nothing.
PAIRS = [
    ("20260424_S1D", "20260423_S1C"),
    ("20260628_S1A", "20260629_S1C"),
]


def parse_stem(stem: str) -> tuple[date, str]:
    """'20260423_S1C' -> (date(2026, 4, 23), 'S1C')."""
    m = STEM_RE.match(stem)
    if not m:
        raise ValueError(f"not a scene stem: {stem!r}")
    return datetime.strptime(m.group(1), "%Y%m%d").date(), m.group(2)


def is_valid_pair(stem_a: str, stem_b: str) -> tuple[bool, str]:
    """Consecutive calendar days, different platforms. Reason if not."""
    try:
        da, pa = parse_stem(stem_a)
        db, pb = parse_stem(stem_b)
    except ValueError as exc:
        return False, str(exc)
    gap = abs((da - db).days)
    if gap > 1:
        return False, f"{gap} days apart; a day is already too much change"
    if pa == pb:
        return False, f"both {pa}; a pair must cross platforms"
    return True, f"{pa} vs {pb}, {gap} day apart"


def intersect_bounds(a: tuple, b: tuple) -> tuple | None:
    """Overlap of two (left, bottom, right, top) boxes, or None."""
    left, bottom = max(a[0], b[0]), max(a[1], b[1])
    right, top = min(a[2], b[2]), min(a[3], b[3])
    if right <= left or top <= bottom:
        return None
    return (left, bottom, right, top)


def grid_offset(ta, tb, px: float = PIXEL_M) -> tuple[float, float]:
    """Origin of b relative to a, in pixels (col, row).

    Whole numbers mean the two rasters share a lattice and a window read
    aligns them exactly. Fractions mean they do not, and every per-pixel
    comparison is smeared by that fraction of a pixel -- which is why
    Terrain-Correction should run with alignToStandardGrid=true.
    """
    return (tb.c - ta.c) / px, (ta.f - tb.f) / px


def frac_misalignment(ta, tb, px: float = PIXEL_M) -> float:
    """How far off-lattice, in pixels: 0.0 aligned, 0.5 worst case."""
    dc, dr = grid_offset(ta, tb, px)
    return max(abs(dc - round(dc)), abs(dr - round(dr)))


def aligned_windows(ta, ba, tb, bb, px: float = PIXEL_M):
    """Integer windows into a and b covering their common extent.

    Returns (win_a, win_b, bounds, frac) or None if they do not overlap.
    Sub-pixel offsets are rounded away -- `frac` says how much was rounded
    so the caller can decide whether that is acceptable.
    """
    isect = intersect_bounds(ba, bb)
    if isect is None:
        return None
    wa = from_bounds(*isect, transform=ta)
    wb = from_bounds(*isect, transform=tb)
    w = int(min(round(wa.width), round(wb.width)))
    h = int(min(round(wa.height), round(wb.height)))
    if w <= 0 or h <= 0:
        return None
    return (
        Window(int(round(wa.col_off)), int(round(wa.row_off)), w, h),
        Window(int(round(wb.col_off)), int(round(wb.row_off)), w, h),
        isect,
        frac_misalignment(ta, tb, px),
    )


def to_db(x: float) -> float:
    return 10.0 * np.log10(x) if x > 0 else float("nan")


def offset_db(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> dict:
    """sigma0 offset of a relative to b, in dB, two independent ways.

    mean_db    ratio of AOI mean linear power. The calibration-relevant
               number: a gain error is multiplicative on power, and the mean
               is what the seasonal analysis will average anyway. Negatives
               included -- see the module docstring.
    median_db  median of the per-pixel ratio. Immune to the tail, but only
               defined where both scenes are strictly positive. For equally
               multi-looked speckle the ratio's median is 1 when the means
               match, so this is unbiased too, by a different route.
    iqr_db     spread of the per-pixel ratio. This is speckle and one day of
               change, NOT calibration uncertainty; it should be several dB
               even for a perfect pair. It is here to catch a pair that has
               decorrelated completely (heavy rain, a grid mismatch).
    """
    av, bv = a[valid], b[valid]
    n = int(valid.sum())
    out = {
        "n_px": n,
        "mean_a": float(av.mean()) if n else float("nan"),
        "mean_b": float(bv.mean()) if n else float("nan"),
    }
    out["mean_db"] = (
        to_db(out["mean_a"] / out["mean_b"])
        if n and out["mean_b"] > 0 and out["mean_a"] > 0
        else float("nan")
    )

    both_pos = valid & (a > 0) & (b > 0)
    n_pos = int(both_pos.sum())
    out["n_px_positive"] = n_pos
    if n_pos:
        r = 10.0 * np.log10(a[both_pos] / b[both_pos])
        out["median_db"] = float(np.median(r))
        out["iqr_db"] = float(np.percentile(r, 75) - np.percentile(r, 25))
    else:
        out["median_db"] = float("nan")
        out["iqr_db"] = float("nan")
    return out


def bin_by_angle(a: np.ndarray, b: np.ndarray, inc: np.ndarray,
                 valid: np.ndarray, edges) -> list[dict]:
    """Offset per incidence-angle bin.

    If the offset is calibration it is flat across the bins. If it slopes,
    something geometric is left in it and the pair is not measuring what the
    requirement says it measures.
    """
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = valid & (inc >= lo) & (inc < hi)
        n = int(sel.sum())
        if n < 1000:          # too few to say anything; report and move on
            rows.append({"lo": lo, "hi": hi, "n_px": n, "mean_db": float("nan")})
            continue
        s = offset_db(a, b, sel)
        rows.append({"lo": lo, "hi": hi, "n_px": n, "mean_db": s["mean_db"]})
    return rows


def bin_trend(rows: list[dict]) -> tuple[float, bool]:
    """(spread in dB, is it monotonic in angle?) across usable bins.

    Spread alone was too blunt a test. A genuine geometric residual rises or
    falls with incidence angle -- that is what "geometric" means. A spread
    that goes up then sharply down is the thin tail bins being thin: the AOI's
    incidence distribution is peaked near 37 deg, so the 34-36 and 40-42 bins
    hold a small, land-cover-skewed sample and wander accordingly.

    So: flag only a spread that is BOTH large and monotonic.
    """
    usable = [r for r in rows if np.isfinite(r["mean_db"])]
    if len(usable) < 2:
        return float("nan"), False
    vals = [r["mean_db"] for r in usable]
    spread = max(vals) - min(vals)
    diffs = [b - a for a, b in zip(vals[:-1], vals[1:])]
    monotonic = all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)
    return spread, monotonic


def cross_ratio_offset(bands: dict) -> float:
    """Platform offset in the cross-ratio (VH - VV, dB) -- the drought metric.

    This is the number the analysis actually inherits, and it is not the same
    as either channel's. A gain error common to both polarisations cancels
    exactly in a ratio, so the cross-ratio can be far better calibrated across
    platforms than VV or VH alone. Worth computing explicitly rather than
    assuming the worst single-channel offset propagates.
    """
    vv, vh = bands.get("Sigma0_VV"), bands.get("Sigma0_VH")
    if not vv or not vh:
        return float("nan")
    return vh["mean_db"] - vv["mean_db"]


@dataclass
class PairResult:
    stem_a: str
    stem_b: str
    note: str
    frac_px: float = 0.0
    bands: dict = field(default_factory=dict)
    angle_bins: dict = field(default_factory=dict)
    error: str = ""

    @property
    def cross_ratio_db(self) -> float:
        return cross_ratio_offset(self.bands)


def read_pair(proc: Path, stem_a: str, stem_b: str, aoi_path: Path,
              bands=("Sigma0_VV", "Sigma0_VH")) -> PairResult:
    ok, note = is_valid_pair(stem_a, stem_b)
    res = PairResult(stem_a, stem_b, note)
    if not ok:
        res.error = note
        return res

    try:
        da = data_dir(proc / f"{stem_a}.dim")
        db = data_dir(proc / f"{stem_b}.dim")
    except SystemExit as exc:
        res.error = str(exc)
        return res

    fa, fb = band_files(da), band_files(db)
    missing = [n for n in (*bands, "projectedLocalIncidenceAngle")
               if n not in fa or n not in fb]
    if missing:
        res.error = f"missing band(s): {', '.join(missing)}"
        return res

    with rasterio.open(fa[bands[0]]) as ra, rasterio.open(fb[bands[0]]) as rb:
        win = aligned_windows(ra.transform, ra.bounds, rb.transform, rb.bounds)
        if win is None:
            res.error = "the two scenes do not overlap"
            return res
        wa, wb, isect, frac = win
        ta = ra.window_transform(wa)
    res.frac_px = frac

    aoi = load_aoi(aoi_path)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)
    aoi_p = shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi)
    aoi_mask = ~geometry_mask([aoi_p], out_shape=(wa.height, wa.width),
                              transform=ta, invert=False)

    def read(path, win):
        with rasterio.open(path) as src:
            return src.read(1, window=win).astype("float64")

    inc = read(fa["projectedLocalIncidenceAngle"], wa)

    for name in bands:
        arr_a, arr_b = read(fa[name], wa), read(fb[name], wb)
        # 0.0 is SNAP's post-TC no-data; a real zero is indistinguishable
        # from it and there is nothing to be done about that.
        valid = (aoi_mask & np.isfinite(arr_a) & np.isfinite(arr_b)
                 & (arr_a != 0.0) & (arr_b != 0.0))
        res.bands[name] = offset_db(arr_a, arr_b, valid)
        res.angle_bins[name] = bin_by_angle(
            arr_a, arr_b, inc, valid, np.arange(34.0, 42.1, 2.0))
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("proc", type=Path, help="directory holding the .dim scenes")
    p.add_argument("--aoi", type=Path, required=True)
    p.add_argument("--csv", type=Path, help="write the offsets here")
    p.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"),
                   help="override the built-in pairs (stem stem)")
    args = p.parse_args(argv)

    pairs = [tuple(x) for x in (args.pair or PAIRS)]
    results = [read_pair(args.proc, a, b, args.aoi) for a, b in pairs]

    worst_frac = 0.0
    for r in results:
        print(f"\n{'=' * 68}\n{r.stem_a}  vs  {r.stem_b}   ({r.note})\n{'=' * 68}")
        if r.error:
            print(f"  cannot measure: {r.error}")
            continue
        worst_frac = max(worst_frac, r.frac_px)
        print(f"grid offset : {r.frac_px:.3f} px off-lattice", end="  ")
        print("(aligned)" if r.frac_px < 0.01 else "<-- SEE THE NOTE BELOW")

        print(f"\n{'band':<14}{'offset dB':>11}{'median dB':>11}"
              f"{'IQR dB':>9}{'px':>12}")
        print("-" * 57)
        for name, s in r.bands.items():
            print(f"{name:<14}{s['mean_db']:>+11.3f}{s['median_db']:>+11.3f}"
                  f"{s['iqr_db']:>9.2f}{s['n_px']:>12,}")

        print(f"\ncross-ratio (VH-VV) offset : {r.cross_ratio_db:+.3f} dB")

        for name, rows in r.angle_bins.items():
            usable = [x for x in rows if np.isfinite(x["mean_db"])]
            if len(usable) < 2:
                continue
            spread, monotonic = bin_trend(rows)
            # Print the pixel count with each bin. Without it the tail bins
            # look as authoritative as the middle ones, and they are not.
            cells = "  ".join(
                f"{x['lo']:.0f}-{x['hi']:.0f}:{x['mean_db']:+.2f}"
                f"({x['n_px'] / 1e6:.1f}M)" for x in usable)
            print(f"\n{name} by incidence angle:\n  {cells}")
            print(f"  spread {spread:.3f} dB, "
                  f"{'monotonic' if monotonic else 'not monotonic'}", end="  ")
            if spread >= 0.15 and monotonic:
                print("<-- sloping with angle; a geometric term is still in this")
            elif spread >= 0.15:
                print("(scatter, not a slope -- thin tail bins)")
            else:
                print("(flat -> radiometric, as required)")

    measured = [r for r in results if not r.error]
    print(f"\n{'=' * 68}")
    if not measured:
        print("No pair could be measured. REQ-09 is not closed.")
        return 1

    worst = max(abs(s["mean_db"]) for r in measured for s in r.bands.values()
                if np.isfinite(s["mean_db"]))
    crs = [r.cross_ratio_db for r in measured if np.isfinite(r.cross_ratio_db)]
    print(f"largest single-channel offset : {worst:.3f} dB")
    if crs:
        print(f"cross-ratio offset           : "
              f"{', '.join(f'{c:+.3f}' for c in crs)} dB")
    if len(crs) > 1:
        agree = max(crs) - min(crs)
        print(f"  the pairs agree to {agree:.3f} dB", end="  ")
        print("-- two independent measurements, so this is a real number,\n"
              "     not one pair's weather" if agree < 0.05 else
              "-- they disagree; one pair has weather in it")
    if worst < 0.3:
        print("\nBelow the drought signal by roughly an order of magnitude.\n"
              "REQ-09 is satisfied: treat S1A, S1C and S1D as one instrument,\n"
              "and record these numbers in the plan as the basis for doing so.")
    else:
        print("\nLarge enough to matter. Before attributing it to calibration,\n"
              "check Oak Park rainfall between the two overpass dates -- one\n"
              "wet night moves sigma0 by more than any plausible gain error.")

    if worst_frac >= 0.01:
        print(f"\nGRID: the paired scenes sit {worst_frac:.3f} px off a common\n"
              f"lattice, because Terrain-Correction ran with\n"
              f"alignToStandardGrid=false. Harmless for these AOI means, fatal\n"
              f"for a per-pixel time series: 82 scenes would land on 82 grids.\n"
              f"Set it true and reprocess BEFORE the batch, not after.")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["scene_a", "scene_b", "band", "offset_db", "median_db",
                        "iqr_db", "n_px", "frac_px_misalignment"])
            for r in measured:
                for name, s in r.bands.items():
                    w.writerow([r.stem_a, r.stem_b, name,
                                f"{s['mean_db']:.4f}", f"{s['median_db']:.4f}",
                                f"{s['iqr_db']:.3f}", s["n_px"],
                                f"{r.frac_px:.4f}"])
                w.writerow([r.stem_a, r.stem_b, "CrossRatio_VH_VV",
                            f"{r.cross_ratio_db:.4f}", "", "",
                            r.bands["Sigma0_VV"]["n_px"], f"{r.frac_px:.4f}"])
        print(f"\nwrote {args.csv}")

    return 0 if len(measured) == len(pairs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
