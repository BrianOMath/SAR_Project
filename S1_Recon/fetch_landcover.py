#!/usr/bin/env python3
"""Fetch the National Land Cover Map over the AOI and burn it onto the stack grid.

Phase 3 dependency. The whole-AOI aggregate could not resolve the 2026 drought
(see the plan): day-to-day soil moisture scatter is 0.63 dB and the detection
floor sits near 0.4 dB. The way past that is not a better average, it is a
CONTROL -- land cover classes that see the same weather on the same day but do
not respond to drought the way grass and tillage do.

Source
------
National Land Cover Map of Ireland 2018, EPA and Tailte Eireann, served as an
ArcGIS feature service in EPSG:2157 -- the same CRS the stack is already in, so
no vector reprojection enters the chain. Only polygons intersecting the AOI are
requested; the national dataset is ~1.2 M polygons and we need a few thousand.

Licence: Creative Commons Attribution 4.0. The report must credit the EPA and
Tailte Eireann, and the fetched GeoJSON is kept as the provenance record.

The vintage problem, stated plainly
-----------------------------------
The map is 2018. The SAR is 2024-2026. Forest, peatland, water and built
surfaces are effectively static over that gap and make sound CONTROLS. Improved
grassland in Ireland largely stays grassland. TILLAGE ROTATES -- a parcel that
was cultivated in 2018 may be in grass now, and vice versa. So the tillage
class is the one carrying real label error, and any result resting on it needs
either a purity filter derived from the SAR itself or an explicit caveat. This
script does not hide that: it reports tillage area separately so the dilution
is visible rather than assumed away.

Grid alignment
--------------
The class raster is burned onto the exact grid of a reference scene and the
lattice is verified against it. That is what NCR-12's fix bought: a class
raster and 83 sigma0 rasters addressing the same ground pixel for pixel, with
no resampling anywhere.

Usage
-----
    python fetch_landcover.py --aoi aoi_oakpark.geojson \\
        --reference C:/sar/proc/20260717_S1D.dim \\
        --out ../data/landcover --csv ../results/phase3/landcover_areas.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.features import geometry_mask, rasterize
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

from build_series import grid_key
from verify_scene import band_files, data_dir, load_aoi

SERVICE = ("https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/"
           "services/MapGenieNationalLandCover2018ITM/FeatureServer/0/query")
PAGE = 2000            # the service's own maxRecordCount
EPSG = 2157
TIMEOUT = 60

# Explicit mapping, written against the 29 Level-2 classes the service actually
# returned over this AOI. Keyword matching was the placeholder; names are now
# known, so guessing has no place here -- a class absent from this table reports
# as UNASSIGNED rather than defaulting into a group and contaminating a result.
#
# RESPONSE strata are kept SEPARATE rather than lumped. Wet and dry grassland
# sit at opposite ends of a drainage gradient, so they carry an internal
# prediction: under drought, dry grassland should fall further than wet. That is
# a second test, independent of the forest control, and free.
STRATA = {
    # --- responds to drought ------------------------------------------------
    "Improved Grassland":              "RESPONSE",
    "Cultivated Land":                 "RESPONSE",
    "Dry Grassland":                   "RESPONSE",
    "Wet Grassland":                   "RESPONSE",

    # --- the control: closed canopy, C-band saturates, roots reach water ----
    "Coniferous Forest":               "CONTROL",
    "Broadleaved Forest and Woodland": "CONTROL",
    "Mixed Forest":                    "CONTROL",

    # --- excluded, with the reason ------------------------------------------
    # Transitional Forest is clearfell and young replanting. A 2018 "transitional"
    # stand is eight years older now, so its backscatter has a large systematic
    # trend of its own -- the single worst thing to put in a control group, and
    # at 53.7 km2 it would have dominated one.
    "Transitional Forest":             "EXCLUDE",
    # Linear features: at 10 m almost every pixel straddles a boundary, so these
    # measure a mixture, not a cover type.
    "Hedgerows":                       "EXCLUDE",
    "Treelines":                       "EXCLUDE",
    "Ways":                            "EXCLUDE",
    "Rivers and Streams":              "EXCLUDE",
    # Managed, mown and often irrigated -- parkland and sports pitches do not
    # behave like farmed grass.
    "Amenity Grassland":               "EXCLUDE",
    # Shallow-rooted, so it responds; too small (0.7 km2) to be its own stratum.
    "Scrub":                           "EXCLUDE",
    "Bracken":                         "EXCLUDE",
    # Peatland would have been an excellent second control, but Carlow is not
    # bog country: all five classes together come to ~1.5 km2, under 0.1% of the
    # AOI. Recorded, not used.
    "Wet Heath":                       "EXCLUDE",
    "Dry Heath":                       "EXCLUDE",
    "Raised Bog":                      "EXCLUDE",
    "Blanket Bog":                     "EXCLUDE",
    "Cutover Bog":                     "EXCLUDE",
    "Bare Peat":                       "EXCLUDE",
    # Not vegetation.
    "Buildings":                       "EXCLUDE",
    "Other Artificial Surfaces":       "EXCLUDE",
    "Bare Soil and Disturbed Ground":  "EXCLUDE",
    "Exposed Rock and Sediments":      "EXCLUDE",
    "Coastal Sediments":               "EXCLUDE",
    "Lakes and Ponds":                 "EXCLUDE",
    "Artificial Waterbodies":          "EXCLUDE",
    "Swamp":                           "EXCLUDE",
    "(no polygon)":                    "EXCLUDE",
}


def assign_group(level2: str) -> str:
    """Which analysis group a Level-2 class belongs to.

    Exact match on the published class name, case- and whitespace-insensitive.
    Anything not in STRATA is UNASSIGNED and is reported, never assumed.
    """
    if not level2:
        return "UNASSIGNED"
    want = " ".join(level2.split()).casefold()
    for name, grp in STRATA.items():
        if " ".join(name.split()).casefold() == want:
            return grp
    return "UNASSIGNED"


def bbox_2157(aoi_wgs84):
    """AOI bounds in EPSG:2157, which is what the service speaks natively."""
    tf = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG}", always_xy=True)
    return shp_transform(lambda x, y, z=None: tf.transform(x, y), aoi_wgs84)


def page_params(bounds, offset: int, count: int = PAGE) -> dict:
    """Query parameters for one page of an envelope intersection."""
    left, bottom, right, top = bounds
    return {
        "where": "1=1",
        "geometry": f"{left},{bottom},{right},{top}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": EPSG,
        "outSR": EPSG,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "LEVEL_1_VALUE,LEVEL_2_VALUE",
        "returnGeometry": "true",
        "resultOffset": offset,
        "resultRecordCount": count,
        "f": "geojson",
    }


def fetch_features(bounds, session=None, sleep: float = 0.3) -> list[dict]:
    """All NLCM polygons intersecting the AOI envelope, paginated.

    The service caps a response at 2000 records and signals more with
    exceededTransferLimit. Trusting a single response would quietly truncate
    the map -- and a land cover layer missing its last few thousand polygons
    looks entirely plausible, which is the dangerous kind of wrong.
    """
    s = session or requests.Session()
    out, offset = [], 0
    while True:
        r = s.get(SERVICE, params=page_params(bounds, offset), timeout=TIMEOUT)
        r.raise_for_status()
        doc = r.json()
        if "error" in doc:
            raise RuntimeError(f"service error: {doc['error']}")
        feats = doc.get("features", [])
        out.extend(feats)
        print(f"  fetched {len(out):>6} polygons", end="\r", flush=True)
        more = doc.get("properties", {}).get("exceededTransferLimit") or \
            doc.get("exceededTransferLimit")
        if not more or not feats:
            break
        offset += len(feats)
        time.sleep(sleep)
    print()
    return out


def class_codes(values) -> dict[str, int]:
    """Stable class -> integer code, 1-based (0 is reserved for no-class).

    Sorted so the mapping is reproducible across runs: a code that shifts
    between runs would silently relabel every stratified result.
    """
    return {v: i for i, v in enumerate(sorted(set(values)), start=1)}


def reference_grid(scene: Path):
    """Transform, shape, CRS and lattice key of the scene to align to."""
    d = data_dir(scene)
    files = band_files(d)
    if "Sigma0_VV" not in files:
        raise SystemExit(f"no Sigma0_VV in {d}")
    with rasterio.open(files["Sigma0_VV"]) as src:
        return (src.transform, (src.height, src.width), src.crs,
                grid_key(src.crs, src.transform))


def area_table(code_raster: np.ndarray, aoi_mask: np.ndarray,
               codes: dict[str, int], px_m2: float) -> list[dict]:
    """Area and AOI share per class, over AOI pixels only."""
    inside = code_raster[aoi_mask]
    n_aoi = int(aoi_mask.sum())
    rows = []
    for name, code in sorted(codes.items(), key=lambda kv: kv[1]):
        n = int((inside == code).sum())
        rows.append({
            "level_2": name,
            "code": code,
            "group": assign_group(name),
            "n_px": n,
            "area_km2": n * px_m2 / 1e6,
            "aoi_fraction": n / n_aoi if n_aoi else 0.0,
        })
    unclassed = int((inside == 0).sum())
    if unclassed:
        rows.append({"level_2": "(no polygon)", "code": 0, "group": "EXCLUDE",
                     "n_px": unclassed, "area_km2": unclassed * px_m2 / 1e6,
                     "aoi_fraction": unclassed / n_aoi})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True,
                   help="a processed .dim whose grid the class raster adopts")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--csv", type=Path, required=True)
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    aoi = load_aoi(args.aoi)
    aoi_p = bbox_2157(aoi)
    print(f"AOI bounds (EPSG:{EPSG}): "
          f"{', '.join(f'{v:,.0f}' for v in aoi_p.bounds)}")

    print("querying the National Land Cover Map service...")
    try:
        feats = fetch_features(aoi_p.bounds)
    except (requests.RequestException, RuntimeError) as exc:
        print(f"\nfetch failed: {exc}\n\n"
              "If the service is unreachable, the same data is downloadable as\n"
              "a national shapefile from the EPA; point a local read at it\n"
              "rather than retrying this.")
        return 1
    if not feats:
        print("no polygons returned -- check the AOI bounds")
        return 1

    raw = args.out / "nlcm_2018_aoi.geojson"
    raw.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"wrote {raw}  ({len(feats):,} polygons, the provenance record)")

    level2 = [f["properties"].get("LEVEL_2_VALUE") or "(null)" for f in feats]
    codes = class_codes(level2)
    print(f"{len(codes)} distinct Level-2 classes in the AOI")

    transform, shape_hw, crs, key = reference_grid(args.reference)
    print(f"reference grid: {shape_hw[1]} x {shape_hw[0]} px, lattice {key}")

    # Burn polygons onto the scene's own grid. Later classes win on overlap,
    # which barely matters -- NLCM polygons are non-overlapping by design.
    pairs = []
    for f, lv2 in zip(feats, level2):
        try:
            pairs.append((shape(f["geometry"]), codes[lv2]))
        except (AttributeError, KeyError, TypeError):
            continue
    print(f"rasterising {len(pairs):,} polygons...")
    code_raster = rasterize(
        pairs, out_shape=shape_hw, transform=transform,
        fill=0, dtype="uint8" if len(codes) < 255 else "uint16",
        all_touched=False)

    aoi_mask = ~geometry_mask([aoi_p], out_shape=shape_hw,
                              transform=transform, invert=False)
    px_m2 = abs(transform.a) * abs(transform.e)
    rows = area_table(code_raster, aoi_mask, codes, px_m2)

    tif = args.out / "nlcm_2018_classes.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=shape_hw[0],
                       width=shape_hw[1], count=1, dtype=code_raster.dtype,
                       crs=crs, transform=transform, compress="deflate") as dst:
        dst.write(code_raster, 1)
        dst.update_tags(**{v: str(k) for k, v in
                           ((n, f"class_{c}") for n, c in codes.items())})
    print(f"wrote {tif}  (aligned to the stack, no resampling)")

    print(f"\n{'Level-2 class':<44}{'group':>11}{'km2':>9}{'% AOI':>8}")
    print("-" * 72)
    for r in sorted(rows, key=lambda r: -r["n_px"]):
        if r["aoi_fraction"] < 0.0005:
            continue
        print(f"{r['level_2'][:43]:<44}{r['group']:>11}"
              f"{r['area_km2']:>9.1f}{100 * r['aoi_fraction']:>7.2f}%")

    print("\n" + "-" * 72)
    for grp in ("RESPONSE", "CONTROL", "EXCLUDE", "UNASSIGNED"):
        sel = [r for r in rows if r["group"] == grp]
        frac = sum(r["aoi_fraction"] for r in sel)
        print(f"{grp:<12}{sum(r['area_km2'] for r in sel):>9.1f} km2"
              f"{100 * frac:>8.2f}%   ({len(sel)} classes)")

    bad = [r for r in rows if r["group"] == "UNASSIGNED" and r["n_px"]]
    if bad:
        print("\nUNASSIGNED classes -- the keyword grouping did not recognise "
              "these.\nThey are in the raster but in no analysis group. Name "
              "them explicitly\nbefore running the stratified comparison:")
        for r in sorted(bad, key=lambda r: -r["n_px"]):
            print(f"  {r['level_2']}  ({r['area_km2']:.1f} km2)")

    ctrl = sum(r["aoi_fraction"] for r in rows if r["group"] == "CONTROL")
    if ctrl < 0.05:
        print(f"\nWARNING: control classes cover only {100 * ctrl:.1f}% of the "
              f"AOI.\nThe difference-in-differences design needs enough "
              f"drought-insensitive\nground to form a stable reference. Below "
              f"~5% the control mean is\nnoisier than the signal it is meant "
              f"to stabilise.")

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: -r["n_px"]))
    print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
