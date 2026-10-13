"""Acceptance test for GRD slice assembly.

Assembly introduces one new processing path into a record whose whole value
rests on every scene being measured the same way. Two things have to be true
before the 2018 confirmatory run is worth starting, and neither can be settled
by reading code.

1. THE LATTICE. An assembled scene must land on the same 10 m grid as the 158
   single-slice scenes: ('EPSG:2157', 10.0, 10.0, 5.0, 5.0). If it does not,
   pixel n is no longer the same patch of Carlow in every scene, which is
   NCR-12 returning by a different door. `build_series.py` refuses a mixed
   stack, so this is also checked there -- but after a ten-hour batch, which
   is a poor place to find out.

2. THE RADIOMETRY. SliceAssembly concatenates two products whose thermal-noise
   lookup tables are indexed by azimuth line. If it re-bases those indices
   correctly, noise removal after assembly is right. If it does not, one half
   of the scene is corrected against the wrong vectors -- and the error lands
   on VH over dry bare soil, which is where backscatter approaches the noise
   floor and is exactly the signal this project measures. A quiet failure here
   would sit on top of the drought effect and look like physics.

The test for (2) is to process each slice on its own through v3, then compare
the assembled scene against each one over the ground that slice covers. On
relative orbit 1 in 2018 the two slices hold 0.8232 and 0.1766 of the AOI, so
between them both halves of the assembly are independently checked and no
assumption about where the seam falls is needed.

The threshold is not invented for this test. REQ-09 measured inter-platform
agreement on consecutive-day pairs at 0.171 dB in the worst channel and
0.011 dB in the cross-ratio. Two processings of the SAME acquisition over the
SAME ground should agree better than two different satellites a day apart, so
0.171 dB is a generous bound: passing it is necessary, not sufficient.

Usage
-----
    python check_assembly.py C:/sar/validation/20180704_S1A_assembled.dim \\
        --against C:/sar/validation/20180704_S1A_north.dim \\
                  C:/sar/validation/20180704_S1A_south.dim \\
        --aoi aoi_oakpark.geojson
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from shapely.ops import transform as shp_transform

from build_series import grid_key
from crosscal import aligned_windows, cross_ratio_offset, offset_db
from verify_scene import band_files, data_dir, load_aoi

BANDS = ("Sigma0_VV", "Sigma0_VH")

# The lattice every scene in the record shares. See NCR-12.
REFERENCE_GRID = ("EPSG:2157", 10.0, 10.0, 5.0, 5.0)

# REQ-09's worst-channel inter-platform agreement.
TOLERANCE_DB = 0.171

# Below this the overlap is too small to mean anything. The smaller slice
# covers 0.1766 of a 40x40 km AOI at 10 m, which is of order 2.8 million
# pixels, so a few tens of thousands indicates something has gone wrong with
# the masking rather than a genuinely small overlap.
MIN_VALID_PX = 50_000


def scene_grid(dim: Path) -> tuple:
    """The lattice key of a processed scene, as build_series computes it."""
    files = band_files(data_dir(dim))
    with rasterio.open(files[BANDS[0]]) as src:
        return grid_key(src.crs, src.transform)


def aoi_in_itm(aoi_path: Path):
    aoi = load_aoi(aoi_path)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)
    return shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi)


def compare(dim_a: Path, dim_b: Path, aoi_path: Path) -> dict:
    """sigma0 offsets of a relative to b over the ground both cover.

    Deliberately not crosscal.read_pair: that enforces consecutive days and
    differing platforms, which is right for calibration pairs and wrong here,
    where the point is to compare two processings of one acquisition.
    """
    fa, fb = band_files(data_dir(dim_a)), band_files(data_dir(dim_b))
    missing = [n for n in BANDS if n not in fa or n not in fb]
    if missing:
        return {"error": f"missing band(s): {', '.join(missing)}"}

    with rasterio.open(fa[BANDS[0]]) as ra, rasterio.open(fb[BANDS[0]]) as rb:
        win = aligned_windows(ra.transform, ra.bounds, rb.transform, rb.bounds)
        if win is None:
            return {"error": "the two products do not overlap"}
        wa, wb, _, frac = win
        ta = ra.window_transform(wa)

    aoi_mask = ~geometry_mask([aoi_in_itm(aoi_path)],
                              out_shape=(int(wa.height), int(wa.width)),
                              transform=ta, invert=False)

    def read(path, win):
        with rasterio.open(path) as src:
            return src.read(1, window=win).astype("float64")

    out = {"frac_px": frac, "bands": {}}
    for name in BANDS:
        arr_a, arr_b = read(fa[name], wa), read(fb[name], wb)
        # 0.0 is SNAP's post-terrain-correction no-data. For this test that is
        # a feature: the single-slice product is no-data over the 17.68% its
        # slice never saw, so the comparison restricts itself to that slice's
        # own ground without any geometry being specified.
        valid = (aoi_mask & np.isfinite(arr_a) & np.isfinite(arr_b)
                 & (arr_a != 0.0) & (arr_b != 0.0))
        out["bands"][name] = offset_db(arr_a, arr_b, valid)
    out["cross_ratio_db"] = cross_ratio_offset(out["bands"])
    return out


def report(assembled: Path, others: list[Path], aoi: Path) -> bool:
    ok = True

    print("=" * 72)
    print("LATTICE")
    print("=" * 72)
    print(f"reference  {REFERENCE_GRID}")
    for dim in [assembled, *others]:
        try:
            key = scene_grid(dim)
        except Exception as exc:                        # noqa: BLE001
            print(f"  {dim.stem:<34} UNREADABLE — {exc}")
            ok = False
            continue
        match = key == REFERENCE_GRID
        print(f"  {dim.stem:<34} {key}  {'ok' if match else 'MISMATCH'}")
        if not match:
            ok = False
    if not ok:
        print("\nA mismatch here is decisive: build_series.py will refuse the")
        print("stack, and no amount of radiometric agreement compensates.")

    print()
    print("=" * 72)
    print(f"RADIOMETRY  (threshold {TOLERANCE_DB} dB, from REQ-09)")
    print("=" * 72)

    for dim in others:
        print(f"\n{assembled.stem}  vs  {dim.stem}")
        res = compare(assembled, dim, aoi)
        if "error" in res:
            print(f"  ERROR: {res['error']}")
            ok = False
            continue
        print(f"  sub-pixel misalignment: {res['frac_px']:.3f} px")
        for name, b in res["bands"].items():
            n = b["n_px"]
            mean = b["mean_db"]
            # NaN means the comparison could not be computed at all -- no
            # valid pixels, or a non-positive mean. It is a failure, not a
            # small number, so it is named rather than left to compare False.
            if not np.isfinite(mean):
                flag = "NOT COMPUTED"
            elif abs(mean) <= TOLERANCE_DB:
                flag = "ok"
            else:
                flag = "OVER"
            print(f"  {name:<12} mean {mean:+.4f} dB   "
                  f"median {b['median_db']:+.4f} dB   "
                  f"iqr {b['iqr_db']:.2f} dB   n={n:,}   {flag}")
            if flag != "ok":
                ok = False
            if n < MIN_VALID_PX:
                print(f"               only {n:,} valid pixels — below "
                      f"{MIN_VALID_PX:,}, treat the number as unproven")
                ok = False
        cr = res["cross_ratio_db"]
        cr_flag = ("NOT COMPUTED" if not np.isfinite(cr)
                   else "ok" if abs(cr) <= TOLERANCE_DB else "OVER")
        print(f"  cross-ratio  {cr:+.4f} dB  {cr_flag}")
        if cr_flag != "ok":
            ok = False

    print()
    print("=" * 72)
    if ok:
        print("PASS — assembly agrees with per-slice processing on the same")
        print("ground, and lands on the record's lattice. The 2018 run can")
        print("proceed. Record these numbers; they are the evidence that the")
        print("assembled scenes are measured like the other 158.")
    else:
        print("FAIL — do not start the batch. Something above is outside the")
        print("bound REQ-09 set, which means assembled scenes are not")
        print("interchangeable with single-slice ones and the drought test")
        print("would be comparing two different measurements.")
    print("=" * 72)
    return ok


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("assembled", type=Path,
                   help="the .dim produced via SliceAssembly + graph v4")
    p.add_argument("--against", type=Path, nargs="+", required=True,
                   help="one .dim per individual slice, each processed alone "
                        "through graph v3")
    p.add_argument("--aoi", type=Path, required=True)
    args = p.parse_args(argv)

    for path in [args.assembled, *args.against]:
        if not path.is_file():
            raise SystemExit(f"not found: {path}")
    if not args.aoi.is_file():
        raise SystemExit(f"not found: {args.aoi}")

    return 0 if report(args.assembled, list(args.against), args.aoi) else 1


if __name__ == "__main__":
    sys.exit(main())
