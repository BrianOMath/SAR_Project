#!/usr/bin/env python3
"""Sentinel-1 acquisition reconnaissance for a fixed AOI.

Phase 0 of the SAR drought project (REQ-02, REQ-03). Queries the Copernicus
Data Space Ecosystem OData catalogue for Sentinel-1 IW GRDH products
intersecting an AOI, and answers one question:

    Which single relative orbit and pass direction gives complete, unbroken
    coverage of the AOI across every season in the study?

Search needs no authentication; only downloading does. So this runs against a
cold CDSE account.

Outputs
-------
<out>/scenes.csv        one row per catalogue product
<out>/acquisitions.csv  one row per pass, with same-date GRD slices merged
<out>/orbits.csv        one row per (relative orbit, direction) candidate, with
                        per-year counts, coverage, largest gap and verdict

Sentinel-1 GRD is sliced along-track, so one pass over the AOI can arrive as
two products that each clip only part of it. Coverage is therefore judged on
the union of a date's slices, never on a single product.

Design note
-----------
Every function that computes something is pure and takes plain data; all HTTP
lives in `fetch_products`. That split is what makes `test_s1_recon.py`
possible without touching the network (cf. the B-Raspi analysis refactor).

Note on incidence angle
-----------------------
Incidence angle is NOT exposed as a catalogue attribute -- it lives in the
product annotation and needs the downloaded scene. What this script gives you
instead is `min_edge_dist_km`: how far the AOI sits inside the footprint. Use
it to avoid picking an orbit that puts the AOI near the swath edge. True
incidence angle is a Phase 1 measurement once you have a scene in hand.

Usage
-----
    python s1_recon.py --aoi aoi_oakpark.geojson --years 2024 2025 2026
    python s1_recon.py --aoi aoi_oakpark.geojson --years 2026 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import requests
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
from shapely.errors import ShapelyError
from shapely.wkt import loads as wkt_loads

ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PAGE_SIZE = 1000
DEFAULT_PRODUCT_TYPE = "IW_GRDH_1S"

# Attributes we lift out of the $expand=Attributes payload.
WANTED_ATTRS = (
    "productType",
    "orbitDirection",
    "relativeOrbitNumber",
    "orbitNumber",
    "polarisationChannels",
    "operationalMode",
    "swathIdentifier",
    "platformSerialIdentifier",
    "processingLevel",
)


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Scene:
    """One catalogue product, flattened to the fields Phase 0 cares about."""

    product_id: str
    name: str
    start: datetime
    platform: str            # S1A / S1C / S1D, from the product name
    product_type: str
    mode: str
    orbit_direction: str     # ASCENDING / DESCENDING
    relative_orbit: int
    absolute_orbit: int
    polarisation: str        # e.g. "VV&VH"
    size_bytes: int
    container: str           # SAFE / COG_SAFE, inferred from the name
    aoi_coverage: float      # 0..1 fraction of the AOI inside THIS product
    min_edge_dist_km: float  # AOI centroid to nearest footprint edge
    online: bool
    footprint_wkt: str       # kept so same-date slices can be unioned

    @property
    def date(self) -> str:
        return self.start.date().isoformat()


# --------------------------------------------------------------------------
# pure: query construction
# --------------------------------------------------------------------------

def polygon_to_wkt(poly: Polygon) -> str:
    """Exterior ring as an OData-friendly WKT POLYGON, lon lat, closed."""
    ring = list(poly.exterior.coords)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    inner = ",".join(f"{x:.6f} {y:.6f}" for x, y in ring)
    return f"POLYGON(({inner}))"


def _str_attr(name: str, value: str) -> str:
    return (
        f"Attributes/OData.CSC.StringAttribute/any("
        f"a:a/Name eq '{name}' and a/OData.CSC.StringAttribute/Value eq '{value}')"
    )


def _int_attr(name: str, value: int) -> str:
    return (
        f"Attributes/OData.CSC.IntegerAttribute/any("
        f"a:a/Name eq '{name}' and a/OData.CSC.IntegerAttribute/Value eq {value})"
    )


def build_filter(
    aoi: Polygon,
    start: datetime,
    end: datetime,
    product_type: str = DEFAULT_PRODUCT_TYPE,
    orbit_direction: str | None = None,
    relative_orbit: int | None = None,
) -> str:
    """Build the OData $filter for one time window.

    CDSE performs badly on wide date ranges, so the caller is expected to
    split the study period into one window per year.
    """
    clauses = [
        "Collection/Name eq 'SENTINEL-1'",
        _str_attr("productType", product_type),
        f"ContentDate/Start ge {_odata_time(start)}",
        f"ContentDate/Start lt {_odata_time(end)}",
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon_to_wkt(aoi)}')",
    ]
    if orbit_direction:
        clauses.append(_str_attr("orbitDirection", orbit_direction.upper()))
    if relative_orbit is not None:
        clauses.append(_int_attr("relativeOrbitNumber", relative_orbit))
    return " and ".join(clauses)


def _odata_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# --------------------------------------------------------------------------
# pure: response parsing
# --------------------------------------------------------------------------

def parse_attributes(raw: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Flatten the OData Attributes array to {name: value}."""
    return {
        a["Name"]: a.get("Value")
        for a in raw or []
        if a.get("Name") in WANTED_ATTRS
    }


def platform_from_name(name: str) -> str:
    """S1A_IW_GRDH_1SDV_2026... -> 'S1A'. Robust to the COG_SAFE suffix."""
    head = name.split("_", 1)[0]
    return head if head.startswith("S1") else "UNKNOWN"


def container_from_name(name: str) -> str:
    """CDSE re-encodes the older archive as COG_SAFE; recent scenes are SAFE.

    Matters because the two may not be equally readable by SNAP -- see the
    Phase 1 compatibility check.
    """
    upper = name.upper()
    if "COG" in upper:
        return "COG_SAFE"
    return "SAFE"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def coverage_stats(footprint: Polygon, aoi: Polygon) -> tuple[float, float]:
    """Fraction of the AOI inside the footprint, and centroid edge margin (km).

    `footprint` may be a Polygon or, when a pass arrives as non-contiguous
    GRD slices, a MultiPolygon. Both are handled.

    Both AOI and footprint are small relative to the globe, so a planar
    calculation in degrees is adequate: the area ratio is dimensionless and
    the margin is converted with a local degrees-to-km scaling.
    """
    if aoi.area <= 0:
        return 0.0, 0.0
    inter = footprint.intersection(aoi)
    frac = inter.area / aoi.area

    centroid = aoi.centroid
    if not footprint.contains(centroid):
        return frac, 0.0
    # .boundary, not .exterior: a union of disjoint GRD slices is a
    # MultiPolygon, which has no exterior ring.
    deg = footprint.boundary.distance(centroid)
    lat = math.radians(centroid.y)
    # crude local scaling; good enough for a "is the AOI near the edge" flag
    km_per_deg = 111.32 * math.sqrt((math.cos(lat) ** 2 + 1) / 2)
    return frac, deg * km_per_deg


def scene_from_product(product: dict[str, Any], aoi: Polygon) -> Scene | None:
    """Convert one OData product dict to a Scene. None if unusable."""
    attrs = parse_attributes(product.get("Attributes", []))
    geom = product.get("GeoFootprint")
    if not geom:
        return None
    try:
        footprint = shape(geom)
    except (ValueError, AttributeError):
        return None
    if not footprint.is_valid:
        footprint = footprint.buffer(0)

    frac, margin = coverage_stats(footprint, aoi)
    name = product.get("Name", "")
    rel = attrs.get("relativeOrbitNumber")
    if rel is None:
        return None

    return Scene(
        product_id=product.get("Id", ""),
        name=name,
        start=_parse_time(product["ContentDate"]["Start"]),
        platform=platform_from_name(name),
        product_type=str(attrs.get("productType", "")),
        mode=str(attrs.get("operationalMode", "")),
        orbit_direction=str(attrs.get("orbitDirection", "")).upper(),
        relative_orbit=int(rel),
        absolute_orbit=int(attrs.get("orbitNumber") or 0),
        polarisation=str(attrs.get("polarisationChannels", "")),
        size_bytes=int(product.get("ContentLength") or 0),
        container=container_from_name(name),
        aoi_coverage=round(frac, 4),
        min_edge_dist_km=round(margin, 1),
        online=bool(product.get("Online", True)),
        footprint_wkt=footprint.wkt,
    )


# --------------------------------------------------------------------------
# pure: summarising
# --------------------------------------------------------------------------

def max_gap_days(dates: Sequence[datetime]) -> int:
    """Largest interval between consecutive acquisitions, in calendar days.

    Measured on the calendar date, not the elapsed timedelta. Sentinel-1
    acquisitions on the same relative orbit drift by a second or two between
    passes, so `(b - a).days` truncates a 24-calendar-day gap to 23 whenever
    the later pass falls a fraction earlier in the day.
    """
    if len(dates) < 2:
        return 0
    ordered = sorted(d.date() for d in dates)
    return max((b - a).days for a, b in zip(ordered, ordered[1:]))


@dataclass(frozen=True)
class Acquisition:
    """All products of one relative orbit on one date, merged.

    Sentinel-1 GRD is sliced along-track, so a single pass over the AOI can
    arrive as two products that each clip only part of it. Coverage must be
    judged on the union of a date's slices, never on one product -- otherwise
    a perfectly good orbit is rejected because of an edge slice.
    """

    relative_orbit: int
    orbit_direction: str
    date: str
    n_slices: int
    n_parts: int          # polygons in the union; >1 means slices don't join
    coverage: float
    min_edge_dist_km: float
    platforms: str
    size_gb: float
    when: datetime


def merge_slices(scenes: Iterable[Scene], aoi: Polygon) -> list[Acquisition]:
    """Collapse products into one Acquisition per (relative orbit, direction, date)."""
    groups: dict[tuple[int, str, str], list[Scene]] = defaultdict(list)
    for s in scenes:
        groups[(s.relative_orbit, s.orbit_direction, s.date)].append(s)

    out: list[Acquisition] = []
    for (rel, direction, date), items in groups.items():
        shapes = []
        for s in items:
            if s.footprint_wkt:
                try:
                    shapes.append(wkt_loads(s.footprint_wkt))
                except ShapelyError:
                    # unparseable geometry is bad data; let anything else
                    # (a missing import, a wrong type) fail loudly
                    pass
        if shapes:
            union = unary_union(shapes)
            n_parts = len(getattr(union, "geoms", [union]))
            frac, margin = coverage_stats(union, aoi)
        else:
            # no geometry retained (e.g. a CSV round-trip): the union is at
            # least the best single slice, so fall back to that lower bound
            n_parts = 0
            frac = max(s.aoi_coverage for s in items)
            margin = max(s.min_edge_dist_km for s in items)
        out.append(Acquisition(
            relative_orbit=rel, orbit_direction=direction, date=date,
            n_slices=len(items), n_parts=n_parts, coverage=round(frac, 4),
            min_edge_dist_km=round(margin, 1),
            platforms=",".join(sorted({s.platform for s in items})),
            size_gb=round(sum(s.size_bytes for s in items) / 1e9, 2),
            when=min(s.start for s in items),
        ))
    out.sort(key=lambda a: (a.relative_orbit, a.orbit_direction, a.when))
    return out


@dataclass(frozen=True)
class OrbitSummary:
    relative_orbit: int
    orbit_direction: str
    n_total: int
    years: str            # "2024:31 2025:30 2026:29"
    n_years: int
    min_coverage: float
    mean_coverage: float
    min_edge_dist_km: float
    max_gap_days: int
    n_sliced: int         # acquisitions that arrived as >1 GRD slice
    platforms: str
    total_gb: float
    verdict: str


def summarise(acquisitions: Iterable[Acquisition],
              required_years: Sequence[int]) -> list[OrbitSummary]:
    """Group ACQUISITIONS (not products) by orbit and direction, and rank them.

    A candidate is VIABLE when every acquisition covers the AOI essentially
    completely, every required year is present, and no in-season gap exceeds
    a month. Gaps are measured within a season: an Apr-Oct window leaves a
    ~5 month winter hole that is the season boundary, not a coverage failure.
    """
    groups: dict[tuple[int, str], list[Acquisition]] = defaultdict(list)
    for a in acquisitions:
        groups[(a.relative_orbit, a.orbit_direction)].append(a)

    out: list[OrbitSummary] = []
    for (rel, direction), items in groups.items():
        by_year: dict[int, list[Acquisition]] = defaultdict(list)
        for a in items:
            by_year[a.when.year].append(a)

        covs = [a.coverage for a in items]
        gap = max((max_gap_days([a.when for a in yr]) for yr in by_year.values()),
                  default=0)
        present = [y for y in required_years if by_year.get(y)]

        min_cov = min(covs)
        if min_cov < 0.99:
            verdict = "partial coverage"
        elif len(present) < len(required_years):
            missing = ",".join(str(y) for y in required_years if y not in present)
            verdict = f"missing {missing}"
        elif gap > 31:
            verdict = f"gap {gap}d"
        else:
            verdict = "VIABLE"

        out.append(OrbitSummary(
            relative_orbit=rel,
            orbit_direction=direction,
            n_total=len(items),
            years=" ".join(f"{y}:{len(by_year.get(y, []))}" for y in required_years),
            n_years=len(present),
            min_coverage=round(min_cov, 4),
            mean_coverage=round(sum(covs) / len(covs), 4),
            min_edge_dist_km=round(min(a.min_edge_dist_km for a in items), 1),
            max_gap_days=gap,
            n_sliced=sum(1 for a in items if a.n_slices > 1),
            platforms=",".join(sorted({p for a in items
                                       for p in a.platforms.split(",")})),
            total_gb=round(sum(a.size_gb for a in items), 1),
            verdict=verdict,
        ))

    out.sort(key=lambda o: (
        o.verdict != "VIABLE",
        -o.n_years,
        o.max_gap_days,
        -o.min_edge_dist_km,
    ))
    return out


# --------------------------------------------------------------------------
# I/O: the only part that touches the network
# --------------------------------------------------------------------------

def fetch_products(
    odata_filter: str,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE,
    max_retries: int = 4,
) -> Iterator[dict[str, Any]]:
    """Yield every product matching the filter, following OData pagination."""
    session = session or requests.Session()
    url: str | None = ODATA_URL
    params: dict[str, Any] | None = {
        "$filter": odata_filter,
        "$expand": "Attributes",
        "$orderby": "ContentDate/Start asc",
        "$top": page_size,
    }

    while url:
        for attempt in range(max_retries):
            try:
                resp = session.get(url, params=params, timeout=120)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"  retry {attempt + 1}/{max_retries} in {wait}s ({exc})",
                      file=sys.stderr)
                time.sleep(wait)

        payload = resp.json()
        yield from payload.get("value", [])
        # nextLink already carries the query string
        url = payload.get("@odata.nextLink")
        params = None


# --------------------------------------------------------------------------
# glue
# --------------------------------------------------------------------------

def load_aoi(path: Path) -> Polygon:
    """Read the AOI polygon from a GeoJSON Feature, FeatureCollection or geometry."""
    data = json.loads(path.read_text())
    if data.get("type") == "FeatureCollection":
        polys = [
            shape(f["geometry"]) for f in data["features"]
            if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
        ]
        if not polys:
            raise ValueError(f"no polygon feature in {path}")
        geom = unary_union(polys)
    elif data.get("type") == "Feature":
        geom = shape(data["geometry"])
    else:
        geom = shape(data)
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def year_windows(years: Sequence[int], months: tuple[int, int] | None) -> list[tuple[datetime, datetime]]:
    """One (start, end) window per year, optionally narrowed to a month range."""
    windows = []
    for y in years:
        if months:
            m0, m1 = months
            start = datetime(y, m0, 1, tzinfo=timezone.utc)
            end = (datetime(y + 1, 1, 1, tzinfo=timezone.utc) if m1 == 12
                   else datetime(y, m1 + 1, 1, tzinfo=timezone.utc))
        else:
            start = datetime(y, 1, 1, tzinfo=timezone.utc)
            end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
        windows.append((start, end))
    return windows


def write_csv(path: Path, rows: Sequence[Any]) -> None:
    if not rows:
        path.write_text("")
        return
    cols = [f.name for f in fields(rows[0])]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aoi", type=Path, required=True, help="AOI GeoJSON")
    p.add_argument("--years", type=int, nargs="+", default=[2024, 2025, 2026])
    p.add_argument("--months", type=int, nargs=2, metavar=("FIRST", "LAST"),
                   default=[4, 10], help="month range, inclusive (default 4 10)")
    p.add_argument("--all-months", action="store_true", help="ignore --months")
    p.add_argument("--product-type", default=DEFAULT_PRODUCT_TYPE)
    p.add_argument("--orbit-direction", choices=["ASCENDING", "DESCENDING"])
    p.add_argument("--out", type=Path, default=Path("recon_out"))
    p.add_argument("--dry-run", action="store_true", help="print filters, do not query")
    args = p.parse_args(argv)

    aoi = load_aoi(args.aoi)
    months = None if args.all_months else tuple(args.months)
    print(f"AOI: {args.aoi.name}  area={aoi.area:.5f} deg^2  bounds={tuple(round(b,4) for b in aoi.bounds)}")

    scenes: list[Scene] = []
    skipped = 0
    for start, end in year_windows(args.years, months):
        flt = build_filter(aoi, start, end, args.product_type,
                           args.orbit_direction)
        if args.dry_run:
            print(f"\n--- {start:%Y-%m-%d} .. {end:%Y-%m-%d} ---\n{flt}")
            continue
        print(f"querying {start:%Y-%m-%d} .. {end:%Y-%m-%d} ...", end=" ", flush=True)
        n0 = len(scenes)
        for product in fetch_products(flt):
            sc = scene_from_product(product, aoi)
            if sc is None:
                skipped += 1
            else:
                scenes.append(sc)
        print(f"{len(scenes) - n0} scenes")

    if args.dry_run:
        return 0

    if not scenes:
        print("no products returned - check the AOI and date range", file=sys.stderr)
        return 1
    if skipped:
        print(f"({skipped} products skipped: no footprint or no relative orbit)")

    args.out.mkdir(parents=True, exist_ok=True)
    scenes.sort(key=lambda s: s.start)
    write_csv(args.out / "scenes.csv", scenes)

    # GRD is sliced along-track: merge same-orbit, same-date products before
    # judging coverage, or an edge slice sinks an otherwise perfect orbit.
    acqs = merge_slices(scenes, aoi)
    write_csv(args.out / "acquisitions.csv", acqs)

    summary = summarise(acqs, args.years)
    write_csv(args.out / "orbits.csv", summary)

    n_sliced = sum(1 for a in acqs if a.n_slices > 1)
    n_split = sum(1 for a in acqs if a.n_parts > 1)
    print(f"\n{len(scenes)} products -> {args.out/'scenes.csv'}")
    print(f"{len(acqs)} acquisitions after merging slices "
          f"({n_sliced} arrived as multiple slices"
          + (f", {n_split} non-contiguous" if n_split else "")
          + f") -> {args.out/'acquisitions.csv'}")
    print(f"{len(summary)} orbit/direction combinations -> {args.out/'orbits.csv'}\n")

    hdr = f"{'orbit':>6} {'dir':<11} {'n':>4} {'per year':<26} {'minCov':>7} {'edge_km':>8} {'gap':>5} {'sliced':>7} {'platforms':<12} {'GB':>7}  verdict"
    print(hdr)
    print("-" * len(hdr))
    for o in summary[:12]:
        print(f"{o.relative_orbit:>6} {o.orbit_direction:<11} {o.n_total:>4} "
              f"{o.years:<26} {o.min_coverage:>7.3f} {o.min_edge_dist_km:>8.1f} "
              f"{o.max_gap_days:>5} {o.n_sliced:>7} {o.platforms:<12} "
              f"{o.total_gb:>7.1f}  {o.verdict}")

    viable = [o for o in summary if o.verdict == "VIABLE"]
    print()
    if viable:
        best = viable[0]
        print(f"Recommended: relative orbit {best.relative_orbit} "
              f"{best.orbit_direction}, {best.n_total} scenes, {best.total_gb} GB.")
        if len(viable) > 1:
            print(f"({len(viable)} viable; prefer ASCENDING for the ~18:00 local "
                  f"overpass -- less dew on the canopy than the ~06:00 descending pass.)")
        if len({p for p in best.platforms.split(",")}) > 1:
            print(f"NOTE: spans platforms {best.platforms} -- REQ-09 continuity "
                  f"check applies across the handover.")
    else:
        print("No fully viable orbit. Widen --months, relax the coverage rule, "
              "or shift the AOI off the swath edge (see min_coverage above).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
